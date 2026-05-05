import asyncio
from types import CoroutineType
from typing import Any, Dict

from s2cpy.exchange.polymarket_api import GammaAPI
from s2cpy.exchange.polymarket_ws import PolymarketWS
from s2cpy.infrastructure.time import TimeInterval, now_unix_ms_utc
from s2cpy.model.core_model import DataFeed, DataHandler
from s2cpy.model.polymarket_io import Market, MarketGetBySlugRequest
from loguru import logger


class CryptoRepeatDataFeed(DataFeed):
    """
    主要是代表那些BTC，一段时间内猜涨跌的数据连接
    """

    def get_name(self) -> str:
        return self.domain_key

    def supported_data_identify(self) -> list[str]:
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

    async def start(self):
        """
        启动流程
        1. 开始监听。
        2. 等到下一个运行时间。时间点为next_market_start_timestamp
          1. 断开之前的连接
          2. 开始监听。
          3. 重复循环
        :return:
        """
        # Start initial listener
        ws = await self.start_listening()

        # compute next market start timestamp (ms since epoch)
        next_market_start_timestamp = self._interval.get_close_now_ms() + self._interval.to_milliseconds()

        try:
            while True:
                sleep_ms = next_market_start_timestamp - now_unix_ms_utc()
                sleep_seconds = 0 if sleep_ms <= 0 else sleep_ms / 1000.0

                try:
                    await asyncio.sleep(sleep_seconds)
                except asyncio.CancelledError:
                    # on cancellation ensure websocket is closed then re-raise
                    await ws.close()
                    raise

                # rotate connection
                await ws.close()
                ws = await self.start_listening()
                next_market_start_timestamp = self._interval.get_close_now_ms() + self._interval.to_milliseconds()

        finally:
            await ws.close()

    def subscribe(self, handler: DataHandler):
        self._handler = handler

    def __init__(self, coin_name="btc", interval: TimeInterval = TimeInterval.FifteenMinute):
        self._coin_name = coin_name
        self._interval = interval
        self._handler: DataHandler = lambda _key, _val: (_ for _ in (0,)).throw(AttributeError("handler没有设置"))

    @property
    def current_slug(self):
        interval = self._interval
        return f"{self._coin_name}-updown-{interval.to_str()}-{interval.get_close_now_second()}"

    @property
    def domain_key(self):
        return f"{self._coin_name}-updown-{self._interval.to_str()}"

    def _on_web_socket_message(self, data: Dict[str, Any]):
        event_type = data["event_type"]
        key = self.domain_key
        self._handler(f"{key}.{event_type}", data)

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
