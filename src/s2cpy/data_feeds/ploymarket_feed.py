import asyncio
from types import CoroutineType
from typing import Any, Dict

from s2cpy.exchange.polymarket_api import GammaAPI
from s2cpy.exchange.polymarket_ws import PolymarketWS
from s2cpy.infrastructure.time import TimeInterval
from s2cpy.model.core_model import DataFeed, DataHandler
from s2cpy.model.polymarket_io import Market, MarketGetBySlugRequest, Event
from loguru import logger


class CryptoRepeatDataFeed(DataFeed):
    """
    主要是代表那些BTC，一段时间内猜涨跌的数据连接
    """

    def supported_data_identify(self) -> list[str]:
        return super().supported_data_identify()

    async def start(self):
        ws = await self.start_listening()

    def subscribe(self, handler: DataHandler):
        super().subscribe(handler)

    def __init__(self, coin_name="btc", interval: TimeInterval = TimeInterval.FifteenMinute):
        self._coin_name = coin_name
        self._interval = interval

    @property
    def current_slug(self):
        interval = self._interval
        return f"{self._coin_name}-updown-{interval.to_str()}-{interval.get_close_now_second()}"

    def _on_web_socket_message(self, data: Dict[str, Any]):
        logger.info(f"WebSocket message: {data}")

    def get_last_market(self) -> CoroutineType[Any, Any, Market]:
        logger.info(f"PolyMarket:Getting last market from {self.current_slug}")
        gamma_api = GammaAPI()
        reqeust = MarketGetBySlugRequest(slug=self.current_slug)
        return gamma_api.get_market_by_slug(reqeust)

    async def start_listening(self) -> PolymarketWS:
        logger.info(f"PolyMarket:Listening for {self.current_slug}")
        url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"  # public echo service (manual only)
        ws = PolymarketWS(url, reconnect_attempts=2)
        ws.register_handler("default", self._on_web_socket_message)
        await ws.connect()
        market = await self.get_last_market()
        logger.info(f"WS connected to {url}")
        sub = {
            "assets_ids": market.clobTokenIds,
            "type": "market",
            "initial_dump": False,
            "level": 2,
            "custom_feature_enabled": True
        }
        await ws.send(sub)
        return ws
