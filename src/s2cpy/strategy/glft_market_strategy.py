from typing import List
from loguru import logger

from s2cpy.data_feeds.ploymarket_feed import OneMarketDataFeed
from s2cpy.exchange.polymarket_api import RestfulAPI
from s2cpy.model.core_model import Strategy, Data
from s2cpy.model.polymarke_core import PolyMarketMarketMakerAccount
from s2cpy.model.polymarket_io import MarketGetBySlugRequest


class PolyMarketGLFTStrategy(Strategy):

    def __init__(self, account: PolyMarketMarketMakerAccount, market_slug: str):
        self._market_slug = market_slug
        self._account = account
        self._yes_token = None
        self._no_token = None

    def data_list(self) -> List[str]:
        key = self.name
        return [f"{key}.{event_type}" for event_type in OneMarketDataFeed.EVENT_LIST]

    async def start(self):
        gamma_api = RestfulAPI()
        market_request = MarketGetBySlugRequest.build(slug=self._market_slug)
        market = await gamma_api.get_market_by_slug(market_request)
        logger.info(f"market id: {market.id}, slug: {market.slug}")
        tokens = market.clobTokenIds

        # TODO: 根据outcomes来判断，现在这样只是支持简单的yes/no，标准做法应该是根据yes/no来判断
        self._yes_token = tokens[0]
        self._no_token = tokens[1]

    @property
    def name(self):
        return self._market_slug

    def on_change(self, data: Data):
        logger.info(f"strategy {self.name} receive: {data}")


