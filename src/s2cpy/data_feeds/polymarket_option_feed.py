import datetime
from typing import List, Union

import pandas as pd
import psycopg

from s2cpy.core.postgresql_tools import PostgresqlInfo
from s2cpy.model.polymarket_option import HitPriceBinaryOption


def _ensure_ts_str(ts: Union[datetime.datetime, str]) -> str:
    if isinstance(ts, datetime.datetime):
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    return str(ts)


class PolyMarketHistoryDataFeed:

    def __init__(self, db_info: PostgresqlInfo):
        self.db_info = db_info

    def _query(
        self, query: str, ts: str
    ) -> tuple[list[str], list[tuple[object, ...]]]:
        connection_kwargs = {
            "host": self.db_info.host,
            "port": self.db_info.port,
            "dbname": self.db_info.dbname,
            "user": self.db_info.user,
            "password": self.db_info.password,
        }

        with psycopg.connect(**connection_kwargs) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (ts,))
                rows = cursor.fetchall()
                columns = [column.name for column in cursor.description]

        return columns, rows

    def query_pm_price(self, ts: Union[datetime.datetime, str]) -> pd.DataFrame:
        query = """
                SELECT i.assert_id, i.assert_slug, i.series_id, i.series_slug,
                       i.market_slug, i.start_ms, i.end_ms, h.price
                FROM polymarket_price_history AS h
                JOIN polymarket_instruments AS i ON h.instrument_id = i.id
                WHERE h.timestamp = %s
                ORDER BY h.timestamp DESC
                """
        ts = _ensure_ts_str(ts)
        columns, rows = self._query(query, ts)
        return pd.DataFrame(rows, columns=columns)

    def query_pm_instruments_at(self, ts: Union[datetime.datetime, str]) -> List[HitPriceBinaryOption]:
        """

        FUTURE:
        1. 当前版本仅返回 HitPriceBinaryOption 类型的标的，其他类型的标的需要扩展。series id 为10016。先hard code
        :param ts:
        :return:
        """
        query = """
                SELECT i.assert_id, i.assert_slug, i.series_id, i.series_slug,
                       i.market_slug, i.start_ms, i.end_ms, h.price
                FROM polymarket_price_history AS h
                JOIN polymarket_instruments AS i ON h.instrument_id = i.id
                WHERE i.series_id = '10016' AND h.timestamp = %s
                """
        ts = _ensure_ts_str(ts)
        res = []
        _, rows = self._query(query, ts)

        for row in rows:
            _, asset_slug, _, _, _, _, expiration_ms, price = row
            option = HitPriceBinaryOption(
                asset_slug=asset_slug,
                expiration_ms=expiration_ms,
                latest_price=float(price) if price is not None else None,
            )
            res.append(option)

        return res
