from typing import Dict, List

from s2cpy.infrastructure.time import TimeInterval
from s2cpy.model.core_model import Strategy, LiveData, Account
from loguru import logger

from s2cpy.model.polymarke_core import PolyMarketMarketMakerAccount, POLYMARKET_ACCOUNT_TOPICS


class PolyMarketRepeatDemoStrategy(Strategy):


    def data_list(self) -> List[str]:
        market = self.domain_key
        market_topic = [
            f"{market}.book",
            f"{market}.price_change",
            f"{market}.tick_size_change",
            f"{market}.last_trade_price",
            f"{market}.best_bid_ask",
            f"{market}.new_market",
            f"{market}.market_resolved",
        ]

        account_topic = [t.format(name=self._account.name) for t in POLYMARKET_ACCOUNT_TOPICS.values()]
        logger.info(f"策略注册账户的topic:{account_topic}")
        logger.info(f"策略注册市场的topic:{market_topic}")
        return account_topic

    def __init__(self, account: PolyMarketMarketMakerAccount, coin_name="btc",
                 interval: TimeInterval = TimeInterval.FifteenMinute):
        self._coin_name = coin_name
        self._interval = interval
        self._account = account

    def get_name(self) -> str:
        return self.domain_key

    @property
    def domain_key(self):
        return f"{self._coin_name}-updown-{self._interval.to_str()}"

    @property
    def current_slug(self):
        interval = self._interval
        return f"{self._coin_name}-updown-{interval.to_str()}-{interval.get_close_now_second()}"

    def on_live_change(self, data: LiveData):
        logger.info(f"strategy {self.domain_key}: {data}")
