import dataclasses
import os
import datetime
from typing import Union, List

import psycopg

from s2cpy.model.core_model import OptionType
from s2cpy.model.okx_option import OkxOption


@dataclasses.dataclass
class PostgresqlInfo:
    user: str
    password: str
    host: str
    port: int
    dbname: str

    def to_connect_url(self, driver: str = "psycopg2") -> str:
        """构建 SQLAlchemy PostgreSQL 连接字符串"""
        return f"postgresql+{driver}://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"

    @classmethod
    def from_env(cls):
        db_user = os.getenv("DB_USER", "username")
        db_pass = os.getenv("DB_PASS", "password")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = int(os.getenv("DB_PORT", "5432"))
        db_name = os.getenv("DB_NAME", "mydb")
        return PostgresqlInfo(
            user=db_user,
            password=db_pass,
            host=db_host,
            port=db_port,
            dbname=db_name
        )


class OkxOptionRepository:

    def __init__(self, db_info: PostgresqlInfo):
        self.db_info = db_info

    @staticmethod
    def parse_inst_identify(
        inst_identify: str,
    ) -> tuple[str, str, str, float, OptionType]:
        """Parse an OKX option identifier into its five components."""
        parts = inst_identify.split("-")
        if len(parts) != 5 or any(not part for part in parts):
            raise ValueError(f"Unexpected OKX option identifier: {inst_identify!r}")

        underlying, quote_ccy, expiration, strike, option_code = parts
        try:
            strike_price = float(strike)
        except ValueError as exc:
            raise ValueError(
                f"Unexpected OKX option strike in identifier: {inst_identify!r}"
            ) from exc

        option_types = {"C": OptionType.Call, "P": OptionType.Put}
        try:
            option_type = option_types[option_code.upper()]
        except KeyError as exc:
            raise ValueError(
                f"Unexpected OKX option type in identifier: {inst_identify!r}"
            ) from exc

        return underlying, quote_ccy, expiration, strike_price, option_type

    def query_option_kline(self, ts: Union[datetime.datetime, str]) -> List[OkxOption]:
        """
        从 okx_line_history这张表里面读取candle_begin_time为ts的所有option，然后转换成OkxOption对象返回
        okx_instrument.id = okx_line_history.instrument_id.有些数据需要从okx_instrument表里获取。
        okx_instrument.inst_identify的格式为
        <underlying>_USD_<expiration_time>_<strike_price>_<option_type>
        例如
        BTC-USD-260921-73000-C
        条件为。
        1. identify 从okx_instrument.inst_identify
        2. mini_ticker_size 为 1，以后再改
        3. strike为 inst_identify为strike_price
        4. expiration为okx_instrument.exp_time
        5. multiplier为如果<underlying>为BTC，则为0.01，如果为ETH，则为0.1
        6. base_ccy为<underlying>
        7. option_type,<option_type>,如果C的话为call，p的话为put。

        :param ts:
        :return:
        """
        query = """
            SELECT i.inst_identify, i.exp_time, i.base_ccy
            FROM okx_kline_history AS h
            JOIN okx_instruments AS i ON i.id = h.instrument_id
            WHERE h.candle_begin_time = %s
              AND i.inst_type = 'OPTION'
            ORDER BY i.inst_identify
        """
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

        multiplier_by_underlying = {"BTC": 0.01, "ETH": 0.1}
        options = []
        for identify, exp_time, base_ccy in rows:
            underlying, _, _, strike_price, option_type = self.parse_inst_identify(
                identify
            )
            try:
                multiplier = multiplier_by_underlying[underlying.upper()]
            except KeyError as exc:
                raise ValueError(
                    f"Unexpected OKX option identifier: {identify!r}"
                ) from exc

            options.append(
                OkxOption(
                    identify=identify,
                    mini_ticker_size=1,
                    validate_before=exp_time,
                    strike=strike_price,
                    multiplier=multiplier,
                    base_ccy=base_ccy or underlying,
                    option_type=option_type,
                )
            )

        return options

    def query_options_by_close_time(self, close_time: Union[datetime.datetime, str]) -> List[OkxOption]:
        pass
