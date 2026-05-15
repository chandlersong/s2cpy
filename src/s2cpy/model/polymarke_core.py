import collections
import dataclasses

from py_clob_client_v2 import ClobClient, BalanceAllowanceParams, AssetType
from py_clob_client_v2.constants import POLYGON

from s2cpy.exchange.polymarket_api import GammaAPI
from s2cpy.infrastructure.async_tools import periodic_runner
from s2cpy.infrastructure.settings import PolyMarketRelayerAccount
from s2cpy.infrastructure.time import str_iso_datetime_to_unix_seconds
from s2cpy.model.core_model import Account, Asset, Position

import asyncio
from typing import Optional, Dict

from loguru import logger

from s2cpy.model.polymarket_io import MarketGetBySlugRequest

_CLOB_HOST = "https://clob.polymarket.com"

"""
# 业务定义
主要是polymarket也一些基础的业务规则的定义。


FUTURE:
1. 考虑统计问题。


"""


@dataclasses.dataclass
class PolyMarketAsset(Asset):
    """
    ## Asset
    因为polymarket上面所有的资产，本质是一个二元期权。如果简化的来做的话，难度其实在于统计。
    举个例子来说，比如说做15m的BTC涨跌。因为因为参数这类都是token相关的。但是事后的统计，就有点麻烦了。
    计划是通过category来进行区分，但是感觉还是有些有点难搞。

    identify: 应该是market_slug+outcome
    external_id: tokenId
    """
    market_slug: Optional[str] = None
    outcome: Optional[str] = None
    opposite_asset: Optional[str] = None
    market_conditionId: Optional[str] = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Asset):
            return NotImplemented
        # Assets are considered equal if their id is equal. Other metadata
        # (external_id, validate_before) is not part of identity used for
        # hashing/keying.
        return self.identify == other.identify

    def __hash__(self) -> int:
        # Use the unique id string as the basis for the hash so Asset can be
        # safely used as a dict key or in sets.
        return hash(self.identify)


class PolyMarketMarketMakerAccount(Account):
    """
    具体功能描述
    1. 同步仓位信息。
        - 启动时。同步订单信息
        - 没10分钟，同步一次新单信息。
    2. 同步订单信息。
        - 下达订单的信息。
        - 监听订单成功与否的信息。
    3. 发送消息给engine，进入bus
        - 订单成交与失败。包括订单和仓位变化。

    """

    def __init__(self, config: PolyMarketRelayerAccount):
        self._config = config
        # Background periodic sync task handle. Created by `start_sync`.
        self._sync_task: Optional[asyncio.Task] = None
        self._asset: Dict[PolyMarketAsset, Position] = dict()  # 资产/价格
        self._clob_client = ClobClient(
            host=_CLOB_HOST,
            chain_id=POLYGON,
            key=self._config.private_key,
            funder=self._config.funder_address,
            signature_type=3,  # POLY_1271 Deposit Wallet
        )
        self._api_creds = self._clob_client.create_or_derive_api_key()
        self._clob_client.set_api_creds(self._api_creds)
        self._usdc_balance: float = 0.0

    @property
    def asset_dict(self) -> Dict[Asset, Position]:
        return self._asset

    @property
    def usdc_balance(self) -> float:
        return self._usdc_balance

    async def start_sync(self, interval_seconds: int = 600):
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

    async def sync_account_position(self):
        """
        同步账户的订单信息。
        1. 通过api /positions 去获取所有assert
        2. 通过clob获取usdc
        :return:
        """
        await self._query_positions()
        await self._query_balance()

    async def _query_balance(self):
        client = self._clob_client
        balance_collateral = client.get_balance_allowance(
            BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        )
        usdc_balance = int(balance_collateral["balance"]) / 1_000_000
        self._usdc_balance = usdc_balance
        open_orders = client.get_open_orders()
        print(f"open_orders: {open_orders}")

    async def _query_positions(self):
        gramma_api = GammaAPI()
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
                    market_cache[market_slug] = validate_before
                else:
                    validate_before = market_cache[market_slug]

                asset = PolyMarketAsset(identify=asset_id,
                                        external_id=position.asset,
                                        validate_before=validate_before,
                                        market_slug=position.slug,
                                        outcome=position.outcome,
                                        opposite_asset=position.oppositeAsset,
                                        market_conditionId=position.conditionId,
                                        )
                if position.curPrice is None or position.size is None:
                    logger.error(f"{position.slug}数据错误，价格或者数量不存在")
                    continue
                position = Position(price=position.curPrice, quantity=position.size, avg_price=position.avgPrice)
                self._asset[asset] = position

    def stop_sync(self) -> None:
        """Cancel the periodic background sync task if running."""
        if self._sync_task is not None and not self._sync_task.done():
            self._sync_task.cancel()
            self._sync_task = None
