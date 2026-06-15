import collections
import dataclasses
import pickle
from pathlib import Path

from py_builder_relayer_client.client import RelayClient
from py_builder_relayer_client.models import RelayerTxType
from py_builder_signing_sdk.config import BuilderConfig
from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds
from py_clob_client_v2 import ClobClient, BalanceAllowanceParams, AssetType, PartialCreateOrderOptions, OrderArgs, Side, \
    OrderType, SignatureTypeV2
from py_clob_client_v2.constants import POLYGON

from s2cpy.exchange.polymarket_api import RestfulAPI
from s2cpy.exchange.polymarket_tools import asserts_by_market_id, is_valid_tick_size, convert_markets_2_assets
from s2cpy.exchange.polymarket_ws import PolymarketWS
from s2cpy.infrastructure.async_tools import periodic_runner
from s2cpy.infrastructure.settings import PolyMarketRelayerAccount
from s2cpy.infrastructure.time import str_iso_datetime_to_unix_seconds, get_unix_seconds_utc
from s2cpy.model.core_model import Account, Asset, Position, Order, DataHandler, LiveData

import asyncio
from typing import Optional, Dict, Any, List

from loguru import logger

from s2cpy.model.polymarket_io import MarketGetBySlugRequest, Market

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
    """
    最理想的状态是。在data feed阶段，产生，然后在那个阶段做流转。
    但是实际情况是一层，都有同步的需求。
    所以暂时先这么考虑吧。
    """
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

    def create_order(self, asset: Asset, **kwargs) -> Optional[str]:
        """
         TODO：
         1. 动态的获得这个ticker(缓存机制)
         2. 判断asset是否存在，如果不存在。就更新
         3. 更新usdc的balance

         FUTURE:
         1. orderPriceMinTickSize变化时，自动更新
        :param asset: 交易标的
        :param kwargs:
        :return:
        """
        s = str(asset.mini_ticker_size)
        # Validate tick size first to avoid making other API/IO calls that
        # may access additional market attributes (like endDate) on the
        # provided `market` object. Tests expect an invalid tick size to raise
        # a ValueError early.
        if not is_valid_tick_size(s):
            raise ValueError(f"asset {asset.identify}, orderPriceMinTickSize {s} is not valid")
        options = PartialCreateOrderOptions(
            tick_size=s,
        )
        asset_id = asset.external_id
        if asset_id is None:
            raise ValueError(f"asset {asset.identify}, has no asset id")
        if asset_id not in self._asset:
            position = Position(latest_price=0.0, quantity=0.0, avg_price=0.0)
            info = AssertInfo(asset=asset, position=position)
            self._asset[asset_id] = info

        side = kwargs["side"]
        if side == Side.BUY:
            cost = kwargs["price"] * kwargs["size"]
            self._usdc_balance = self._usdc_balance - cost

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

    def cancel_order_by_asset(self, asset: Asset):
        order_ids = []
        asset_id = asset.external_id
        for order in self._open_orders.values():
            if order.asset_id == asset_id:
                order_ids.append(order.id)
        if len(order_ids) != 0:
            self.cancel_order(order_ids)

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

    @property
    def asset(self) -> Dict[str, AssertInfo]:
        return self._asset

    def supported_data_list(self) -> list[str]:

        account_name = self._config.name
        return [
            template.format(name=account_name) for template in POLYMARKET_ACCOUNT_TOPICS.values()
        ]

    @property
    def orders_group_by_asset(self) -> Dict[str, List[Order]]:
        """
        根据order的asset_id的区别，把相同的asset_id的order放入list。最后组成一个list返回
        :return:
        """
        # Only consider the Order.asset_id attribute (previously there was
        # some handling for an alternative name like `assert_id`). The codebase
        # uses `asset_id` on the Order dataclass, so keep behavior simple and
        # strict: group open orders by their `asset_id` value and ignore any
        # orders that don't have one.
        grouped: Dict[str, List[Order]] = collections.defaultdict(list)
        for order in self._open_orders.values():
            aid = order.asset_id
            if aid is None:
                # skip orders without an asset identifier
                continue
            grouped.setdefault(aid, []).append(order)

        return grouped

    def get_topic(self, topic: str) -> str:
        return POLYMARKET_ACCOUNT_TOPICS[topic].format(name=self._config.name)

    @property
    def asset_dict(self) -> dict[str, AssertInfo]:
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

        FUTURE：优化点
        1. 完成后更新order的asset信息，可能有些order。但是没有asset。比如重启的时候。
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
                          status=o["status"], price=o["price"], extra_info=o, asset_id=o["asset_id"])
            self._open_orders[id_] = order

    async def _query_positions(self):
        """
        TODO：优化一下
        1. 删除过期的asset
        2. 去掉一些其他逻辑
        :return:
        """
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
                position = Position(latest_price=position.curPrice, quantity=position.size, avg_price=position.avgPrice,
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

        FUTURE：改进项目
        1.部分成功的时候是怎么处理的。这个还是未知。所以暂时放弃。
        2.去掉初始化 asset。因为create order的时候，就会出现

        :param data:
        :return:
        """
        trade_type = data["status"]
        # TODO: 下面代码，纯粹是为了收集数据。正式版后请删除
        export_folder = Path("/app/records")
        if export_folder.exists():
            pickle.dump(data, open(export_folder / f'trade_{trade_type}_{get_unix_seconds_utc()}.pkl', 'wb'))
        refresh_position = True
        price = float(data["price"])
        quantity = float(data["size"])
        if trade_type == "CONFIRMED":
            topic = self.get_topic("trade_confirm")
        elif trade_type == "FAILED":
            topic = self.get_topic("trade_failed")
            refresh_position = False
            self._usdc_balance += quantity * price
        else:
            # 其他的topic暂时先不弄了。
            return
        maker_orders = data['maker_orders']
        for maker_order in maker_orders:
            order_id = maker_order["order_id"]
            if order_id in self._open_orders:
                del self._open_orders[order_id]
            else:
                # TODO:监控代码，确认后去掉
                logger.warning(f"trade的maker_order:{order_id}，在open_orders中没有找到，请检查")
        asset_id = data["asset_id"]
        orders = self.orders_group_by_asset[asset_id]
        # TODO:监控代码，确认后去掉
        logger.info(f"{asset_id}，trade type:{trade_type}，现有orders:{len(orders)}")

        side = 1 if data["side"] == "BUY" else -1
        info = self._asset[asset_id]
        if info is None:
            # 应该在order之前就是初始化了。
            raise ValueError(f"trade的asset_id:{asset_id}，在账户的asset_dict中没有找到，请检查")
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
        这里的逻辑比较
        1. PLACEMENT: 过滤。从文档上来看，就是上订单簿了。暂时感觉对于下游没有什么意义。
        2. UPDATE：更新仓位
        3. CANCELLATION的时候，恢复balance

        [polymarket order status](https://docs.polymarket.com/market-data/websocket/user-channel#order)
        :param data:
        :return:
        """
        order_type = data["type"]
        # TODO: 下面代码，纯粹是为了收集数据。正式版后请删除
        export_folder = Path("/app/records")
        if export_folder.exists():
            pickle.dump(data, open(export_folder / f'order_{order_type}_{get_unix_seconds_utc()}.pkl', 'wb'))
        else:
            logger.warning(f"{export_folder} does not exist")

        asset_id = data["asset_id"]
        asset_info = self._asset[asset_id]
        price = float(data["price"])
        quantity = float(data["size_matched"])
        id_: str = data["id"]
        side = 1 if data["side"] == "BUY" else -1
        if order_type == "CANCELLATION":
            id_: str = data["id"]
            if id_ in self._open_orders:
                _ = self._open_orders.pop(id_)
            if side == 1:
                # 因为只有买的时候，会退钱。但是如果说卖，仓位和金额都不变。
                # TODO: 确认这个逻辑
                usdc_return = price * quantity
                self._usdc_balance += usdc_return
            topic = self.get_topic("order_cancelled")
            live_data = LiveData(topic=topic, asset=asset_info.asset, data=data)
            self._handler(topic, live_data)
        elif order_type == "UPDATE":
            order = Order(id=id_, side=side, quantity=data["original_size"], quantity_match=data["size_matched"],
                          status=data["type"], price=data["price"], extra_info=data, asset_id=asset_id)
            self._open_orders[id_] = order
            if side == 1:
                position = asset_info.position
                cost = position.quantity * position.avg_price + price * quantity
                position.quantity = position.quantity + quantity
            else:
                position = asset_info.position
                cost = position.quantity * position.avg_price - price * quantity
                position.quantity = position.quantity - quantity
            position.latest_price = price

            position.avg_price = cost / position.quantity
            if position.quantity < 0:
                # 算是一个错误处理吧。
                asyncio.run(self.sync_account_position())

            topic = self.get_topic("order_update")
            live_data = LiveData(topic=topic, asset=asset_info.asset, data=data)
            self._handler(topic, live_data)
        elif order_type == "PLACEMENT":
            order = Order(id=id_, side=side, quantity=data["original_size"], quantity_match=data["size_matched"],
                          status=data["type"], price=data["price"], extra_info=data, asset_id=asset_id)
            self._open_orders[id_] = order
