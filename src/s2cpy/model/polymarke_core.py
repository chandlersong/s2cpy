import collections
import dataclasses
import pickle
from pathlib import Path

from py_builder_relayer_client.client import RelayClient
from py_builder_relayer_client.models import RelayerTxType
from py_builder_signing_sdk.config import BuilderConfig
from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds
from py_clob_client_v2 import ClobClient, BalanceAllowanceParams, AssetType, PartialCreateOrderOptions, OrderArgs, Side, \
    OrderType, SignatureTypeV2, OrderPayload
from py_clob_client_v2.constants import POLYGON

from s2cpy.exchange.polymarket_api import RestfulAPI
from s2cpy.exchange.polymarket_tools import asserts_by_market_id
from s2cpy.exchange.polymarket_ws import PolymarketWS
from s2cpy.infrastructure.async_tools import periodic_runner
from s2cpy.infrastructure.settings import PolyMarketRelayerAccount
from s2cpy.infrastructure.time import str_iso_datetime_to_unix_seconds, get_unix_seconds_utc
from s2cpy.model.core_model import Account, Asset, Position, Order, DataHandler, LiveData

import asyncio
from typing import Optional, Dict, List, Any

from loguru import logger

from s2cpy.model.polymarket_io import MarketGetBySlugRequest

_CLOB_HOST = "https://clob.polymarket.com"
_RELAYER_URL = "https://relayer-v2.polymarket.com"
"""
# 业务定义
主要是polymarket也一些基础的业务规则的定义。

## Asset
因为polymarket上面所有的资产，本质是一个二元期权。如果简化的来做的话，难度其实在于统计。
举个例子来说，比如说做15m的BTC涨跌。因为因为参数这类都是token相关的。但是事后的统计，就有点麻烦了。
计划是通过category来进行区分，但是感觉还是有些有点难搞。

identify: 应该是market_slug+outcome
external_id: tokenId

FUTURE:
1. 考虑统计问题。


"""

POLYMARKET_ACCOUNT_TOPICS = {
    "new_order": "{name}.order_created",
    "order_update": "{name}.order_updated",
    "order_cancelled": "{name}.order_cancelled",
    "trade_confirm": "{name}.trade_confirm",
    "trade_failed": "{name}.trade_failed",
}


@dataclasses.dataclass
class AssertInfo:
    asset: Asset
    position: Position


class PolyLiquidityProviderAccount(Account):
    """
    # 信息同步
    因为像position，账户余额等信息，不太可能实事同步。所以做出以下规则。
    然后每隔一段时间去做同步。

    ## balance
    采用这样的策略，来处理相应的保守的时间点。
    正常流程：
    - 创建订单时减去相应的金额。
    - 在卖出的交易被确认时候加上。

    取消流程：（需要确认）
    - order被取消时加回。
    - trade被取消。

    # Position
    完全根据相应的position取更新

    # order
    完全根据相应的order取更新。

    具体功能描述
    1. 同步仓位信息。
        - 启动时。同步订单信息
        - 没10分钟，同步一次新单信息。
    2. 同步订单信息。
        - 下达订单的信息。
        - 监听订单成功与否的信息。
    3. 发送消息给engine。
        - 订单成交与失败。包括订单和仓位变化。

    """

    def create_order(self, **kwargs) -> Optional[str]:
        # TODO： 动态的获得这个ticker
        options = PartialCreateOrderOptions(
            tick_size="0.001"
        )
        try:
            order = self._clob_client.create_and_post_order(
                order_args=OrderArgs(
                    **kwargs
                ),
                options=options,
                order_type=OrderType.GTC,
                post_only=True
            )
            logger.info(f"create order success,{order}")
            return str(order["orderID"])
        except Exception as e:
            logger.error(f"Create order error: {e}")

    def cancel_order(self, order_ids: list[str]):
        self._clob_client.cancel_orders(order_ids)

    async def heartbeat_loop(self):
        heartbeat_id = ""  # 第一次必须为空字符串
        while True:
            try:
                if len(self._open_orders) != 0:
                    resp = self._clob_client.post_heartbeat(heartbeat_id)
                    if resp and isinstance(resp, dict) and "heartbeat_id" in resp:
                        heartbeat_id = resp["heartbeat_id"]
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
            await asyncio.sleep(8)  # 每5秒一次

    def __init__(self, config: PolyMarketRelayerAccount):
        self._config = config
        # Background periodic sync task handle. Created by `start_sync`.
        self._sync_task: Optional[asyncio.Task] = None
        self._asset: Dict[str, AssertInfo] = dict()  # assertid/AssertInfo：主要方便查询
        self._clob_client = ClobClient(
            host=_CLOB_HOST,
            chain_id=POLYGON,
            key=self._config.private_key,
            funder=self._config.funder_address,
            signature_type=SignatureTypeV2.POLY_1271,  # POLY_1271 Deposit Wallet
        )

        builder_config = BuilderConfig(
            local_builder_creds=BuilderApiKeyCreds(
                key=config.builder_api,
                secret=config.builder_secret,
                passphrase=config.builder_pass_phrase,
            )
        )

        self._relay_client = RelayClient(_RELAYER_URL, POLYGON, self._config.private_key, builder_config,
                                         relay_tx_type=RelayerTxType.PROXY)

        self._api_creds = self._clob_client.create_or_derive_api_key()
        self._clob_client.set_api_creds(self._api_creds)
        self._usdc_balance: float = 0.0
        self._open_orders: Dict[str, Order] = dict()
        self._handler: DataHandler = lambda _key, _val: (_ for _ in (0,)).throw(
            AttributeError(f"handler没有设置，就是监听账户{self._config.name}, 请检查代码"))
        try:
            asyncio.create_task(self.heartbeat_loop())
        except RuntimeError:
            logger.exception("Failed to schedule background task for sync_account_position")

    @property
    def name(self):
        return self._config.name

    def supported_data_list(self) -> list[str]:

        account_name = self._config.name
        return [
            template.format(name=account_name) for template in POLYMARKET_ACCOUNT_TOPICS.values()
        ]

    def get_topic(self, topic: str) -> str:
        return POLYMARKET_ACCOUNT_TOPICS[topic].format(name=self._config.name)

    @property
    def asset_dict(self) -> Dict[Asset, Position]:
        return self._asset

    @property
    def usdc_balance(self) -> float:
        return self._usdc_balance

    @property
    def open_orders(self) -> Dict[str, Order]:
        return self._open_orders

    def get_order_by_id(self, order_id: str) -> Order:
        return self._open_orders[order_id]

    async def start_sync(self, handler: Optional[DataHandler] = None, interval_seconds: int = 600):
        """
        Start an initial sync and schedule periodic syncs running in background.

        This coroutine performs one immediate `sync_account_position()` call,
        then schedules a background task that calls `sync_account_position`
        every `interval_seconds`. It returns immediately after scheduling the
        background task. The background task can be cancelled via `stop_sync()`.
        """
        # perform an initial sync (so caller can await start_sync to ensure first sync done)
        await self.sync_account_position()

        # schedule periodic background task if not already running
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop — cannot schedule background task
            raise RuntimeError("start_sync must be called from within a running event loop")

        if self._sync_task is None or self._sync_task.done():
            # schedule a generic periodic runner that calls our sync coroutine
            self._sync_task = loop.create_task(
                periodic_runner(lambda: self.sync_account_position(), interval_seconds)
            )

        if handler is not None:
            logger.info(f"{self._config.name}开始监听工作")
            self._handler = handler
            await self._start_websocket_listening()

    async def sync_account_position(self):
        """
        同步账户的订单信息。
        1. 通过api /positions 去获取所有assert
        2. 通过clob获取usdc
        :return:
        """
        # Run the three independent sync steps concurrently to reduce total latency.
        # Use gather(return_exceptions=True) so one failing step doesn't cancel the others
        # and we can log failures individually.
        results = await asyncio.gather(
            self._query_positions(),
            self._query_balance(),
            self._query_open_orders(),
            return_exceptions=True,
        )

        # Log any exceptions returned by gather
        for idx, res in enumerate(results):
            if isinstance(res, Exception):
                step_name = ("_query_positions", "_query_balance", "_query_open_orders")[idx]
                logger.exception(f"Error running {step_name}: {res}")

    async def _query_balance(self):
        client = self._clob_client
        balance_collateral = client.get_balance_allowance(
            BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        )
        usdc_balance = int(balance_collateral["balance"]) / 1_000_000
        self._usdc_balance = usdc_balance

    async def _query_open_orders(self):
        open_orders = self._clob_client.get_open_orders()
        for o in open_orders:
            side = 1 if o["side"] == "BUY" else -1
            id_: str = o["id"]
            order = Order(id=id_, side=side, quantity=o["original_size"], quantity_match=o["size_matched"],
                          status=o["status"], price=o["price"], extra_info=o)
            self._open_orders[id_] = order

    async def _query_positions(self):
        gramma_api = RestfulAPI()
        acc_config = self._config
        response = await gramma_api.positions(acc_config.funder_address)
        positions = response.positions
        market_cache = collections.defaultdict()
        if positions is None or len(positions) == 0:
            logger.info(f"{acc_config.name} 下没有仓位")
        else:
            for position in positions:
                asset_id = f"{position.slug}-{position.outcome}"
                market_slug = position.slug
                if market_slug is None or position.asset is None:
                    logger.error(f"{position.slug}不存在，数据问题")
                    continue
                if market_slug not in market_cache.keys():
                    reqeust = MarketGetBySlugRequest(slug=market_slug)
                    market = await gramma_api.get_market_by_slug(reqeust)
                    if market is None or market.endDate is None:
                        logger.error(f"{position.slug}数据错误，api没有找到")
                        continue
                    validate_before = str_iso_datetime_to_unix_seconds(market.endDate)
                    market_cache[market_slug] = market
                else:
                    validate_before = str_iso_datetime_to_unix_seconds(market_cache[market_slug].endDate)

                asset = Asset(
                    identify=asset_id,
                    external_id=position.asset,
                    validate_before=validate_before,
                    extra_info=market_cache[market_slug],
                )
                if position.curPrice is None or position.size is None:
                    logger.error(f"{position.slug}数据错误，价格或者数量不存在")
                    continue
                position = Position(price=position.curPrice, quantity=position.size, avg_price=position.avgPrice,
                                    extra_info=position.to_dict())
                self._asset[asset_id] = AssertInfo(asset=asset, position=position)

    def stop_sync(self) -> None:
        """Cancel the periodic background sync task if running."""
        if self._sync_task is not None and not self._sync_task.done():
            self._sync_task.cancel()
            self._sync_task = None

    async def _start_websocket_listening(self) -> PolymarketWS:
        config = self._config
        logger.info(f"PolyMarket:Listening account for {config.name}")
        url = "wss://ws-subscriptions-clob.polymarket.com/ws/user"  # public echo service (manual only)
        ws = PolymarketWS(url, reconnect_attempts=2)
        ws.register_handler("default", self.on_web_socket_message)
        await ws.connect()
        creds = self._api_creds
        sub = {
            "auth": {
                "apiKey": creds.api_key,
                "secret": creds.api_secret,
                "passphrase": creds.api_passphrase

            },
            "type": "user",
        }
        await ws.send(sub)
        return ws

    def on_web_socket_message(self, data: Dict[str, Any]):
        logger.debug(f"PolyMarket:WebSocket message: {data}")
        event_type = data["event_type"]
        if event_type == "order":  # 处理订单逻辑
            self.on_web_socket_order(data)
        elif event_type == "trade":  # 处理交易逻辑
            asyncio.run(self.on_web_socket_trade(data))

    async def on_web_socket_trade(self, data: Dict[str, Any]):
        """
        [官方资料](https://docs.polymarket.com/market-data/websocket/user-channel#trade)
        1. 根据资料，整个trade有五个，为了简化，只把failed和confirm做处理。
        :param data:
        :return:
        """
        trade_type = data["status"]
        # TODO: 下面代码，纯粹是为了收集数据。正式版后请删除
        export_folder = Path("/app/examples")
        if export_folder.exists():
            pickle.dump(data, open(export_folder / f'{trade_type}_{get_unix_seconds_utc()}.pkl', 'wb'))
        refresh_position = True
        price = data["price"]
        quantity = data["size"]
        if trade_type == "CONFIRMED":
            topic = self.get_topic("trade_confirm")
        elif trade_type == "FAILED":
            topic = self.get_topic("trade_failed")
            refresh_position = False
            self._usdc_balance += quantity * price
        else:
            # 其他的topic暂时先不弄了。
            return

        asset_id = data["asset_id"]
        asset = None
        if asset_id not in self._asset:
            """
            polymarket没有合约，不可能卖空。所以第一笔交易必然是买的。
            """
            market_id = data["market"]
            logger.info(f"新的交易的asset:{asset_id},不存在缓存中，开始更新，market_id:{market_id}")
            assets = await asserts_by_market_id(market_id)
            if refresh_position:
                for k, v in assets.items():
                    if k == asset_id:
                        position = Position(latest_price=price, quantity=quantity, avg_price=price)
                        info = AssertInfo(asset=v, position=position)
                        self._asset[k] = info
                        asset = v
                        break
                if asset is None:
                    logger.error(f"assert:{asset_id}，market{market_id},没有在polymarket上找到，请检查")
                    # TODO:加入到通知用户环节，为的是保护用户
                    return
        else:
            side = 1 if data["side"] == "BUY" else -1
            info = self._asset[asset_id]
            asset = info.asset
            if refresh_position:
                if side == 1:
                    p = info.position
                    total_cost = price * quantity + p.quantity * p.avg_price
                    p.latest_price = price
                    p.quantity = quantity + p.quantity
                    p.avg_price = total_cost / p.quantity
                else:
                    p = info.position
                    total_cost = p.quantity * p.avg_price - price * quantity
                    p.latest_price = price
                    p.quantity = p.quantity - quantity
                    p.avg_price = total_cost / p.quantity
                    if p.quantity < 0:
                        # 算是一个错误处理吧。
                        asyncio.create_task(self.sync_account_position())

        live_data = LiveData(topic=topic, asset=asset, data=data)
        self._handler(topic, live_data)

    def on_web_socket_order(self, data: Dict[str, Any]):
        """
        1. PLACEMENT的时候需要更新本地的可以交易金额。
        2. UPDATE过滤
        3. CANCELLATION的时候，恢复金额

        [polymarket order status](https://docs.polymarket.com/market-data/websocket/user-channel#order)
        :param data:
        :return:
        """
        order_type = data["type"]
        if order_type == "PLACEMENT":  # null
            side = 1 if data["side"] == "BUY" else -1
            id_: str = data["id"]
            order = Order(id=id_, side=side, quantity=data["original_size"], quantity_match=data["size_matched"],
                          status=data["type"], price=data["price"], extra_info=data)
            self._open_orders[id_] = order

            self._handler(self.get_topic("new_order"), order)
        elif order_type == "CANCELLATION":
            id_: str = data["id"]
            if id_ in self._open_orders:
                pop = self._open_orders.pop(id_)
                pop.status = "CANCELLATION"
                pop.extra_info = data
                self._handler(self.get_topic("order_cancelled"), pop)

        elif order_type == "UPDATE":

            id_: str = data["id"]
            side = 1 if data["side"] == "BUY" else -1
            order = Order(id=id_, side=side, quantity=data["original_size"], quantity_match=data["size_matched"],
                          status=data["type"], price=data["price"], extra_info=data)
            self._open_orders[id_] = order
            self._handler(self.get_topic("order_update"), order)
        # Schedule a background sync of positions/balance instead of calling the
        # async coroutine directly (avoids 'coroutine was never awaited').
        try:
            asyncio.create_task(self.sync_account_position())
        except RuntimeError:
            logger.exception("Failed to schedule background task for sync_account_position")
