"""
主要是做市的GLFT模型的相关计算
"""
import asyncio
import dataclasses
import math
from collections import deque
from typing import Optional

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
        self._last_orderbook: Optional[_GLFTOrderBook] = None
        self._window_period_seconds = window_period_seconds
        self._update_cycle_seconds = update_cycle_seconds
        self._trades = []
        self._task = asyncio.create_task(self._run_periodic())
        self._k = 0.25
        self._a = 0.55
        self._position = 0
        self._mid_prices = deque(maxlen=window_period_seconds // update_cycle_seconds)

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

    def calculate_volatility(self):
        """计算波动率"""
        window = int(self._window_period_seconds / self._update_cycle_seconds)
        threshold = window * 0.9
        mid_prices = np.array(self._mid_prices)
        if len(mid_prices) < threshold:
            logger.warning(f"计算GLFT模型数据太少，现有{len(mid_prices)},需要{threshold}")
            return np.nan

        log_ret = np.log(mid_prices[1:] / mid_prices[:-1])
        vol = np.std(log_ret[-window:]) * np.sqrt(self._update_cycle_seconds)
        return max(vol, 0.01)

    def glft_calculate(self,
                       p: float,
                       gamma: float = 0.02,
                       adj1=1.0, adj2=0.15, min_tick=0.01):
        vol = self.calculate_volatility()
        if vol is np.nan:
            return None, None
        half, skew = self.glft_half_spread_skew(
            gamma, vol,
            adj1=adj1, adj2=adj2
        )
        logger.info(f"half: {half}, skew: {skew}")
        # reservation_price = mid - skew * position（库存倾斜）
        mid_price = self._last_orderbook.mid_price if self._last_orderbook else None
        if mid_price is None:
            logger.info(f"GLFT模型在预热中")
            return None, None
        reservation = mid_price - skew * p

        bid_price = reservation - half
        ask_price = reservation + half
        logger.info(f"bid_price:{bid_price}, ask_price:{ask_price},mid_price:{mid_price}")
        # 防止越界（可选）
        bid_price = max(bid_price, mid_price - half * 3)
        ask_price = min(ask_price, mid_price + half * 3)

        return round(bid_price / min_tick) * min_tick, \
               round(ask_price / min_tick) * min_tick

    def compute_glft_coeffs(self, gamma, delta_param=1.0):
        """计算 c1, c2"""
        A = self.a
        k = self.k
        if A is None or k is None or A <= 0 or k <= 0:
            logger.warning(f"A:{A}, k:{k}, delta_param:{delta_param}")
            return 1.0, 0.1
        inv_k = 1.0 / k
        xi_delta = gamma * delta_param
        term = 1 + xi_delta * inv_k
        c1 = (1.0 / xi_delta) * np.log(term)
        exponent = k / xi_delta + 1
        inside = (gamma / (2 * A * delta_param * k)) * (term ** exponent)
        c2 = np.sqrt(inside)
        return c1, c2

    def glft_half_spread_skew(self, gamma, volatility, delta_param=1.0, adj1=1.0, adj2=0.5):
        """返回 half_spread 和 skew（可加调整因子调保守程度）"""
        c1, c2 = self.compute_glft_coeffs(gamma, delta_param)
        half_spread = (c1 + (delta_param / 2) * c2 * volatility) * adj1
        skew = c2 * volatility * adj2
        return half_spread, skew

    async def _run_periodic(self):
        while True:
            try:

                lambdas = dict()
                while True:
                    try:
                        self._mid_prices.append(self._last_orderbook.mid_price)
                        lambdas = self.calibrate_a_k(lambdas)
                    except Exception as e:
                        logger.error(e)

                    # do work
                    await asyncio.sleep(self._update_cycle_seconds)
            except Exception as e:
                # 为了保证程序一定运行
                logger.info(f"gifts loop error：{e}")
                await asyncio.sleep(self._update_cycle_seconds)

    def calibrate_a_k(self, lambdas: dict):
        hits = self.count_hits()
        if hits is None:
            return lambdas
        logger.info(f"latest hits:{hits}")
        lambdas[self._last_orderbook.timestamp] = hits
        valid_timestamp = get_unix_seconds_utc() - self._window_period_seconds
        # 删除所有的lambdas的key小于valid_timestamp的数据。
        lambdas = {k: v for k, v in lambdas.items() if k >= valid_timestamp}
        # loop所有的values，把他们相同index的相加
        if len(lambdas) == 0:
            return lambdas
        records_num = self._window_period_seconds / self._update_cycle_seconds
        hits_mean = np.array(list(lambdas.values())).sum(axis=0) / records_num
        logger.info(f"hits_mean:{hits_mean}")
        # mask = (hits_mean > 1e-8) & (np.arange(len(hits_mean)) >= 1)
        mask = (hits_mean > 1e-8)
        if np.sum(mask) < 5:
            logger.info(
                f"数据太少了，无法计算a和k，继续等待数据,lambda数据{len(lambdas)}.mask长度{np.sum(mask)}.records_num{records_num}")
            self._k = 0.25
            self._a = 0.55
            return lambdas

        result = linregress(self._depths[mask], np.log(hits_mean[mask]))
        # TODO:这里是为了演示，k总是负数，但是这里感觉应该是正的。以后需要好好的验证过程。
        k = -result.slope
        a = np.exp(result.intercept)
        self._a = a
        self._k = k
        logger.info(f"lastest k:{k}, a:{a}")
        return lambdas

    def count_hits(self):
        mid = self._last_orderbook.mid_price
        trades = self._trades.copy()
        self._trades.clear()
        if len(trades) == 0:
            return None
        hits = np.zeros_like(self._depths)
        prev_count_sum = 0
        for j, d in enumerate(self._depths):
            price_low = mid - d
            price_high = mid + d
            h = int(np.sum((trades >= price_low) & (trades <= price_high)))
            temp = h
            h = h - prev_count_sum
            prev_count_sum = temp
            hits[j] = h
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
