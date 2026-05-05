from typing import Dict, List

from s2cpy.infrastructure.time import TimeInterval
from s2cpy.model.core_model import Strategy, Data
from loguru import logger


class PolyMarketRepeatDemoStrategy(Strategy):

    def data_list(self) -> List[str]:
        key = self.domain_key
        return [
            f"{key}.book",
            f"{key}.price_change",
            f"{key}.tick_size_change",
            f"{key}.last_trade_price",
            f"{key}.best_bid_ask",
            f"{key}.new_market",
            f"{key}.market_resolved",
        ]

    def __init__(self, coin_name="btc", interval: TimeInterval = TimeInterval.FifteenMinute):
        self._coin_name = coin_name
        self._interval = interval

    def get_name(self) -> str:
        return self.domain_key

    @property
    def domain_key(self):
        return f"{self._coin_name}-updown-{self._interval.to_str()}"

    @property
    def current_slug(self):
        interval = self._interval
        return f"{self._coin_name}-updown-{interval.to_str()}-{interval.get_close_now_second()}"

    def on_change(self, data: Data):
        logger.info(f"strategy {self.domain_key}: {data}")
