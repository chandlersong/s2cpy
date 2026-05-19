"""
主要是做市的GLFT模型的相关计算
"""
import asyncio
import dataclasses

import numpy as np

from s2cpy.infrastructure.time import get_unix_seconds_utc
from s2cpy.model.common_consts import SIDE_PARAMETER_TYPE
from scipy.stats import linregress
from loguru import logger


@dataclasses.dataclass
class _GLFTOrderBook:
    timestamp: int
    mid_price: float


class RollingGLFT:
    """
    滚动的计算GLFT相关值的算法。
    """

    def __init__(self, window_period_seconds: int = 60 * 60, update_cycle_seconds=60, min_tick: float = 0.01,
                 depth_size=8):
        """
        用于动态计算GLFT模型中的的值
        :param window_period_seconds: 滚动窗口的周期，单位是秒，例如可以设置为3600，代表1小时的滚动窗口.这个主要因为最早是polymarket。
        :param update_cycle_seconds:  a,k值的计算频率。默认1分钟
        :param min_tick: 最小的周期
        """
        self._depths = generate_depths_from_min_tick(min_tick=min_tick, n_points=depth_size)
        self._last_orderbook = None
        self._window_period_seconds = window_period_seconds
        self._update_cycle_seconds = update_cycle_seconds
        self._trades = []
        self._task = asyncio.create_task(self._run_periodic())
        self._k = None
        self._a = None

    @property
    def k(self):
        return self._k

    @property
    def a(self):
        return self._a

    def append_trades(self, _timestamp: int, price: float, _quantity: float, _side: SIDE_PARAMETER_TYPE):
        self._trades.append(price)

    def append_order_books(self, timestamp: int, mid_price: float):
        self._last_orderbook = _GLFTOrderBook(timestamp, mid_price)

    async def _run_periodic(self):
        try:
            lambdas = dict()
            while True:
                try:
                    lambdas = self.calibrate_a_k(lambdas)
                except Exception as e:
                    logger.error(e)

                # do work
                await asyncio.sleep(self._update_cycle_seconds)
        except asyncio.CancelledError:
            # 清理
            raise

    def calibrate_a_k(self, lambdas: dict):
        hits = self.count_hits()
        if hits is None:
            return lambdas
        lambdas[self._last_orderbook.timestamp] = hits
        valid_timestamp = get_unix_seconds_utc() - self._window_period_seconds
        # 删除所有的lambdas的key小于valid_timestamp的数据。
        lambdas = {k: v for k, v in lambdas.items() if k >= valid_timestamp}
        # loop所有的values，把他们相同index的相加
        if len(lambdas) == 0:
            return lambdas
        hits_mean = np.array(list(lambdas.values())).sum(axis=0) / len(lambdas)
        records_num = self._window_period_seconds / self._update_cycle_seconds

        mask = hits_mean > 1e-8
        if np.sum(mask) < 5 or records_num < len(lambdas) * 0.8:
            logger.info(
                f"数据太少了，无法计算a和k，继续等待数据,lambda数据{len(lambdas)}.mask长度{np.sum(mask)}.records_num{records_num}")
            self._a = None
            self._k = None
            return lambdas

        result = linregress(self._depths[mask],np.log(hits_mean[mask]))
        k = -result.slope
        a = np.exp(result.intercept)
        self._a = a
        self._k = k
        return lambdas

    def count_hits(self):
        mid = self._last_orderbook.mid_price
        trades = self._trades
        self._trades = []
        if len(trades) == 0:
            return None
        hits = np.zeros_like(self._depths)
        for j, d in enumerate(self._depths):
            price_low = mid - d
            price_high = mid + d
            h = int(np.sum((trades >= price_low) & (trades <= price_high)))
            hits[j] = h / self._update_cycle_seconds
        return hits


def generate_depths_from_min_tick(min_tick: float,
                                  n_points: int = 8):
    """
    根据 min_tick 生成合理的 depths 档位

    参数:
        min_tick: 交易所的最小价格刻度 (例如 0.1, 0.01, 1 等)
        n_points: 生成多少个深度档位
        max_multiple: 最大是 min_tick 的多少倍
    """
    # 推荐使用对数间隔或常见倍数，更符合市场实际
    multiples = np.array([1, 2, 3, 5, 8, 12, 20, 35, 60, 100, 150, 200])

    # 截取需要的数量
    multiples = multiples[:n_points]

    depths = multiples * min_tick

    return depths
