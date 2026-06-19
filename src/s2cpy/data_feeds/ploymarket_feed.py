import asyncio
import dataclasses
import datetime
from dataclasses import dataclass
from types import CoroutineType
from typing import Any, Dict, Optional, List, Generator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from py_clob_client_v2 import ClobClient, PricesHistoryParams

from s2cpy.exchange.polymarket_api import RestfulAPI
from s2cpy.exchange.polymarket_tools import convert_markets_2_assets, split_series_markets
from s2cpy.exchange.polymarket_ws import PolymarketWS
from s2cpy.infrastructure.async_tools import get_task_scheduler
from s2cpy.infrastructure.time import TimeInterval, now_unix_ms_utc, str_iso_datetime_to_unix_seconds
from s2cpy.model.core_model import DataFeed, DataHandler, Asset, AssetLiveData
from s2cpy.model.polymarke_core import PolyMarketHistoryPriceLiveData
from s2cpy.model.polymarket_io import Market, MarketGetBySlugRequest, SeriesGetRequest, EventGetByIdRequest
from loguru import logger

POLYMARKET_DATA_FEED_TOPICS = {
    "book": "{name}.book",
    "tick_size_change": "{name}.tick_size_change",
    "last_trade_price": "{name}.last_trade_price",
    "best_bid_ask": "{name}.best_bid_ask",
    # "price_change": "{name}.price_change",
}


class CryptoRepeatDataFeed(DataFeed):
    """
    主要是代表那些BTC，一段时间内猜涨跌的数据连接
    """
    EVENT_LIST = ["book", "tick_size_change", "last_trade_price", "best_bid_ask"]

    def __init__(self, coin_name="btc", interval: TimeInterval = TimeInterval.FifteenMinute):
        self._coin_name = coin_name
        self._interval = interval
        self._rotation_task: Optional[asyncio.Task] = None
        self._handler: DataHandler = lambda _key, _val: (_ for _ in (0,)).throw(
            AttributeError(f"CryptoRepeatDataFeed-{coin_name}-{interval},handler没有设置, 请检查代码"))
        self._asset: Dict[str, Asset] = dict()

    @property
    def name(self) -> str:
        return self.domain_key

    def supported_data_list(self) -> list[str]:
        key = self.domain_key
        return [
            template.format(name=key) for template in POLYMARKET_DATA_FEED_TOPICS.values()
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
        # Start the rotation loop in the background and return immediately.
        # This keeps the websocket reconnection loop running without blocking
        # the caller. The created asyncio.Task is stored on the instance so
        # it can be cancelled via `await stop()`.
        if self._rotation_task is not None and not self._rotation_task.done():
            return
        self._rotation_task = asyncio.create_task(self._rotation_loop())

    async def _rotation_loop(self):
        """
        Internal coroutine that performs the periodic sleep/rotate cycle for
        the websocket connection. Extracted from `start` to make the loop
        clearer and reusable while preserving the original semantics: if the
        coroutine is cancelled it will close the current websocket and
        re-raise the CancelledError; on normal exit it ensures the ws is
        closed.
        """
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

    @property
    def current_slug(self):
        interval = self._interval
        return f"{self._coin_name}-updown-{interval.to_str()}-{interval.get_close_now_second()}"

    @property
    def domain_key(self):
        return f"{self._coin_name}-updown-{self._interval.to_str()}"

    def _on_web_socket_message(self, data: Dict[str, Any]):
        event_type = data["event_type"]
        # TODO:处理tick_size_change事件
        if event_type in self.EVENT_LIST:
            key = self.domain_key
            asset_id = data["asset_id"]
            asset = self._asset[asset_id]
            topic = f"{key}.{event_type}"
            live_data = AssetLiveData(topic=topic, asset=asset, data=data)
            self._handler(topic, live_data)

    def get_last_market(self) -> CoroutineType[Any, Any, Market]:
        logger.info(f"PolyMarket:Getting last market from {self.current_slug}")
        gamma_api = RestfulAPI()
        reqeust = MarketGetBySlugRequest(slug=self.current_slug)
        return gamma_api.get_market_by_slug(reqeust)

    async def start_listening(self) -> PolymarketWS:
        logger.info(f"PolyMarket:Listening for {self.current_slug}")
        url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"  # public echo service (manual only)
        ws = PolymarketWS(url, reconnect_attempts=2)
        ws.register_handler("default", self._on_web_socket_message)
        await ws.connect()
        market = await self.get_last_market()
        self._asset = convert_markets_2_assets(market)
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


class OneMarketDataFeed(DataFeed):
    """
    对于单市场的websocket的监听
    """
    EVENT_LIST = ["book", "tick_size_change", "last_trade_price", "best_bid_ask"]

    def __init__(self, market_slug: str):
        self._market_slug = market_slug
        self._handler: DataHandler = lambda _key, _val: (_ for _ in (0,)).throw(
            AttributeError(f"polymarket OneMarketDataFeed-{market_slug},handler没有设置, 请检查代码"))
        # Background rotation task (asyncio.Task) if started via start()
        self._rotation_task: Optional[asyncio.Task] = None
        self._asset: Dict[str, Asset] = dict()

    @property
    def name(self) -> str:
        return self._market_slug

    def supported_data_list(self) -> list[str]:
        key = self.name
        return [
            template.format(name=key) for template in POLYMARKET_DATA_FEED_TOPICS.values()
        ]

    async def start(self):
        """
        :return:
        """
        # Start the rotation loop in the background and return immediately.
        # This keeps the websocket reconnection loop running without blocking
        # the caller. The created asyncio.Task is stored on the instance so
        # it can be cancelled via `await stop()`.
        if self._rotation_task is not None and not self._rotation_task.done():
            return
        self._rotation_task = asyncio.create_task(self._rotation_loop())

    async def stop(self):
        """
        Stop the background rotation loop (if running) and ensure the
        websocket is closed. This method is idempotent.
        """
        task = self._rotation_task
        if task is None:
            return

        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._rotation_task = None

    async def _rotation_loop(self):
        """
        Internal coroutine that performs the periodic sleep/rotate cycle for
        the websocket connection. Extracted from `start` to make the loop
        clearer and reusable while preserving the original semantics: if the
        coroutine is cancelled it will close the current websocket and
        re-raise the CancelledError; on normal exit it ensures the ws is
        closed.
        """

        # Connect, then wait one day between rotations. On cancellation
        # ensure the websocket is closed and re-raise the CancelledError.
        ws = await self.start_listening()

        try:
            # rotate once every 24 hours
            one_day_seconds = 24 * 60 * 60
            while True:
                try:
                    await asyncio.sleep(one_day_seconds)
                except asyncio.CancelledError:
                    # Ensure websocket closed on cancellation and propagate
                    await ws.close()
                    raise

                # Time to rotate the connection: close current ws and start a new one
                await ws.close()
                ws = await self.start_listening()

        finally:
            # Ensure websocket closed on normal exit as well
            await ws.close()

    def subscribe(self, handler: DataHandler):
        self._handler = handler

    def _on_web_socket_message(self, data: Dict[str, Any]):
        event_type = data["event_type"]
        # TODO:处理tick_size_change事件
        if event_type in self.EVENT_LIST:
            key = self.name
            asset_id = data["asset_id"]
            asset = self._asset[asset_id]
            topic = f"{key}.{event_type}"
            live_data = AssetLiveData(topic=topic, asset=asset, data=data)
            self._handler(topic, live_data)

    def get_last_market(self) -> CoroutineType[Any, Any, Market]:
        logger.info(f"PolyMarket:Getting last market from {self._market_slug}")
        gamma_api = RestfulAPI()
        reqeust = MarketGetBySlugRequest(slug=self._market_slug)
        return gamma_api.get_market_by_slug(reqeust)

    async def start_listening(self) -> PolymarketWS:
        logger.info(f"PolyMarket:Listening for {self._market_slug}")
        url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"  # public echo service (manual only)
        ws = PolymarketWS(url, reconnect_attempts=2)
        ws.register_handler(self._on_web_socket_message)
        await ws.connect()
        market = await self.get_last_market()
        self._asset = convert_markets_2_assets(market)
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


class SeriesHistoryDataFeed(DataFeed):

    def __init__(self, series_ids: list[str], interval: TimeInterval, refresh_market_corn: str = '3 5 * * *'):
        """

        :param series_ids: ides
        :param interval: 间隔周期
        :param refresh_market_corn: 很多币圈的日级别的都在11:59 PM ET。因为夏令时的关系。所以暂时先在这个时间
        """
        self._series_ids = series_ids
        self._interval = interval
        self._handler: DataHandler = None
        self._refresh_market_corn = refresh_market_corn
        self._open_market: List[Market] = []

    @property
    def open_market(self):
        return self._open_market

    def subscribe(self, handler: DataHandler):
        self._handler = handler

    async def start(self):
        await self.refresh_markets()
        scheduler = get_task_scheduler()
        task_id = f"series_history_{"_".join(self._series_ids)}"
        scheduler.add_job(
            self.refresh_markets,
            trigger='cron',
            cron=self._refresh_market_corn,  # ← 推荐这种，更接近 unix cron
            id=task_id,
            replace_existing=True
        )

    def supported_data_list(self) -> list[str]:
        interval_str = self._interval.to_str()
        return [f"{series_id}_{interval_str}_history" for series_id in self._series_ids]

    async def refresh_markets(self):
        # Use timezone-aware UTC now to avoid comparing naive and aware datetimes
        # returned by the API models. Convert naive datetimes to UTC as a fallback.
        new_open_market = []
        for series_id in self._series_ids:
            open_markets, _ = await split_series_markets(series_id)
            new_open_market.extend(open_markets)
        self._open_market = new_open_market


def query_market_history(client: ClobClient,  market: Market,interval: TimeInterval,
                         start_time: Optional[int] = None)-> Generator[PolyMarketHistoryPriceLiveData, None, None]:
    """
    查询历史数据。
    :param client: 查询客户端
    :param market:
    :param interval:
    :param start_time: unix timestamp in seconds
    :return:
    """
    if start_time is None:
        start_time = int(market.startDate.timestamp())
    start_time = interval.get_close_unix_seconds(timestamp=start_time)
    end_time = interval.get_close_now_second()
    out_comes = market.outcomes
    clob_token_ids = market.clobTokenIds
    market_slug = market.slug
    if market_slug is None:
        logger.warning(f"{market.id}没有slug")
        return
    if clob_token_ids is None:
        logger.warning(f"{market_slug}没有可交易的币")
        return
    for idx, asset_id in enumerate(clob_token_ids):
        params = PricesHistoryParams(
            market=asset_id,
            interval=interval.to_str(),
            start_ts=start_time,
            end_ts=end_time
        )
        asset_slug = f"{market_slug}_{out_comes[idx]}"
        history = client.get_prices_history(params=params)['history']
        for h in history:
             yield PolyMarketHistoryPriceLiveData(
                market_id=market.id,
                market_slug=market_slug,
                asset_id=asset_id,
                asset_slug=asset_slug,
                timestamp=h['t'],
                price=h['p'],
            )
