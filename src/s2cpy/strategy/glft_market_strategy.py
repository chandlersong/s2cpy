import asyncio
from typing import List, Any
from loguru import logger

from s2cpy.algorithms.glfts import RollingGLFT
from s2cpy.data_feeds.ploymarket_feed import OneMarketDataFeed
from s2cpy.exchange.polymarket_api import RestfulAPI
from s2cpy.model.core_model import Strategy, WebsocketData
from s2cpy.model.polymarke_core import PolyMarketMarketMakerAccount
from s2cpy.model.polymarket_io import MarketGetBySlugRequest


class PolyMarketGLFTStrategy(Strategy):

    def __init__(self, account: PolyMarketMarketMakerAccount, market_slug: str):
        self._market_slug = market_slug
        self._account = account
        self._yes_token = None
        self._no_token = None
        self._glft = RollingGLFT(window_period_seconds=5 * 60, update_cycle_seconds=10)
        self._best_ask_bid_topic = f"{self.name}.best_bid_ask"
        self._trade_topic = f"{self.name}.last_trade_price"
        self._task = asyncio.create_task(self._run_periodic())

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

    def on_change(self, data: WebsocketData):
        # logger.info(f"strategy {self.name} receive: {data}")
        topic = data.topic
        if topic == self._best_ask_bid_topic:
            best_bid = float(data.data['best_bid'])
            best_ask = float(data.data['best_ask'])
            mid_price = (best_bid + best_ask) / 2
            timestamp = int(data.data['timestamp'])
            self._glft.append_order_books(timestamp // 1000, mid_price)
            self._yes_token = None
            self._no_token = None
        elif topic == self._trade_topic:
            trade_price = float(data.data['price'])
            timestamp = int(data.data['timestamp']) // 1000
            quantity = data.data['size']
            side = 1 if data.data['side'] == 'BUY' else -1
            self._glft.append_trades(timestamp, trade_price, quantity, side)

    async def _run_periodic(self):
        """
        为了测试以后删掉
        :return:
        """

        try:
            while True:
                try:
                    ask, bid = self._glft.glft_calculate(q=5)
                    logger.info(f"ask: {ask}, bid: {bid}")
                except Exception as e:
                    logger.error(e)
                # do work
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            # 清理
            raise
