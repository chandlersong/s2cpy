import psycopg
import io
import datetime
from psycopg import sql

from loguru import logger

from s2cpy.generated import history_data_pb2
from s2cpy.infrastructure.settings import SyncClientSetting


class HistoryDataService:

    def __init__(self, config: SyncClientSetting):
        logger.info(
            f"数据库地址{config.server_address}:{config.port}，数据库名称：{config.db_name},用户名:{config.db_user}")
        conn = psycopg.connect(
            f"host={config.db_host} dbname={config.db_name} user={config.db_user} password={config.db_password} port={config.db_port}"
        )
        with conn.cursor() as cur:
            # use psycopg.sql.Identifier to safely interpolate an SQL identifier
            alter_timezone_sql = sql.SQL("ALTER ROLE {} SET timezone = 'UTC';").format(
                sql.Identifier(config.db_user)
            )
            cur.execute(alter_timezone_sql)
        self._conn = conn

    def get_max_batch_timestamp(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute(sql.SQL("select max(batch_timestamp) from polymarket_history;"))
            res = cur.fetchone()[0]
            if res is None:
                logger.info("polymarket_history没有数据")
                return 0
            else:
                logger.info(f"polymarket history有{res}行数据")
                return res

    def batch_insert(self, history_list: history_data_pb2.PolyMarketHistoryList):
        """
        批量插入数据
        :param history_list:
        :return:
        """

        # No-op if empty
        if not history_list or len(history_list.history_list) == 0:
            logger.info("batch_insert: no history to insert")
            return 0

        # We'll COPY into all columns except `id` (allowing it to be NULL)
        columns = [
            "series_id",
            "series_slug",
            "event_id",
            "event_slug",
            "market_id",
            "market_slug",
            "asset_id",
            "asset_slug",
            "timestamp",
            "price",
            "batch_timestamp",
        ]

        # Prepare text-format (tab-delimited) stream in-memory. We'll write
        # directly to COPY STDIN using PostgreSQL text format. This avoids CSV
        # parsing and is efficient for streaming.
        buf = io.StringIO()

        batch_ts = int(history_list.timestamp) if hasattr(history_list, "timestamp") else 0

        cache = {}
        for h in history_list.history_list:
            # Convert epoch milliseconds (assumed) to RFC3339 timestamp in UTC
            if h.timestamp in cache:
                p = cache[h.timestamp]
                if p != h.price:
                    logger.warning(
                        f"保存polymarket_history发现重复的timestamp {h.timestamp}，但价格不同，之前的价格{p}，新的价格{h.price}，将覆盖之前的价格")
                continue
            cache[h.timestamp] = h.price
            try:
                ts = datetime.datetime.fromtimestamp(h.timestamp, datetime.timezone.utc).isoformat()
            except Exception:
                # Fallback: use raw numeric timestamp
                ts = str(h.timestamp)

            # Build a tab-delimited text line according to PostgreSQL COPY text
            # format. Use \N to represent NULL for numeric fields.
            def esc(s: str) -> str:
                # Escape backslash, tab, newline, carriage return
                return (
                    s.replace("\\", "\\\\")
                    .replace("\t", "\\t")
                    .replace("\n", "\\n")
                    .replace("\r", "\\r")
                )

            def maybe_text_field(value) -> str:
                if value is None:
                    return "\\N"
                # protobuf strings default to "" when unset; keep empty string
                return esc(str(value))

            def maybe_numeric_field(value) -> str:
                if value is None:
                    return "\\N"
                return str(value)

            fields = [
                maybe_text_field(h.series_id if hasattr(h, "series_id") else ""),
                maybe_text_field(h.series_slug if hasattr(h, "series_slug") else ""),
                maybe_text_field(h.event_id if hasattr(h, "event_id") else ""),
                maybe_text_field(h.event_slug if hasattr(h, "event_slug") else ""),
                maybe_text_field(h.market_id if hasattr(h, "market_id") else ""),
                maybe_text_field(h.market_slug if hasattr(h, "market_slug") else ""),
                maybe_text_field(h.asset_id if hasattr(h, "asset_id") else ""),
                maybe_text_field(h.asset_slug if hasattr(h, "asset_slug") else ""),
                maybe_text_field(ts),
                maybe_numeric_field(float(h.price) if hasattr(h, "price") else None),
                maybe_numeric_field(batch_ts),
            ]

            buf.write("\t".join(fields) + "\n")

        buf.seek(0)

        copy_sql = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT text, DELIMITER E'\\t')").format(
            sql.Identifier("polymarket_history"),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
        )

        inserted = 0
        with self._conn.cursor() as cur:
            try:
                # Use psycopg copy context manager to stream CSV data
                with cur.copy(copy_sql) as copy:
                    # copy.write accepts bytes or str; send the full buffer
                    copy.write(buf.read())
                # commit the transaction
                self._conn.commit()
                inserted = len(history_list.history_list)
                logger.info(f"Inserted {inserted} rows into polymarket_history via COPY")
            except Exception as e:
                # Rollback on error and re-raise
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                logger.exception("Failed to COPY polymarket_history")
                raise

        return inserted
