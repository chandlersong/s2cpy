import datetime
from typing import Union, List

import psycopg

from s2cpy.core.postgresql_tools import PostgresqlInfo
from s2cpy.model.core_model import OptionType
from s2cpy.model.option import Option


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

    def query_option_kline(self, ts: Union[datetime.datetime, str]) -> List[Option]:
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
            underlying, _, _, strike_price, option_type = self.parse_inst_identify(identify)
            try:
                multiplier = multiplier_by_underlying[underlying.upper()]
            except KeyError as exc:
                raise ValueError(f"Unexpected OKX option identifier: {identify!r}") from exc

            options.append(
                Option(
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

    def query_options_by_close_time(self, close_time: Union[datetime.datetime, str]) -> List[Option]:
        return []
