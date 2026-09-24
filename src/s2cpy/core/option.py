from typing import List, Tuple, Optional

import numpy as np
from matplotlib import pyplot as plt

from s2cpy.model.option import CMOption, ExpirationDate


def sort_options_by_strike(options: List[CMOption], price: float) -> Tuple[List[CMOption], int]:
    """
    1. 把option按照strike排序，有小到大。然后返回
    2. 找到最接近的price的option的indx
    :param options: 期权
    :param price: 价格
    :return: 排序好的option，和strike最接近price的的index
    """
    if not options:
        return [], -1

    sorted_options = sorted(options, key=lambda option: option.strike)
    closest_index = min(
        range(len(sorted_options)),
        key=lambda idx: (
            abs(sorted_options[idx].strike - price),
            sorted_options[idx].strike,
        ),
    )
    return sorted_options, closest_index


# ==================== 策略类 ====================
class OptionStrategy:
    def __init__(
            self,
            options: List[CMOption],
            fee_per_contract: float = 0.0,
            fee_rate: float = 0.0,
            include_close_fee: bool = True,
            name: str = "OKX 币本位策略"
    ):
        self.options = options
        self.fee_per_contract = fee_per_contract
        self.fee_rate = fee_rate
        self.include_close_fee = include_close_fee
        self.name = name

    def calculate_fees(self) -> float:
        return 0

    def calculate_payoff(self, S: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
        """返回单位：币"""
        gross = np.zeros_like(S, dtype=float)
        for opt in self.options:
            gross += opt.payoff(S)

        total_fee = self.calculate_fees()
        net = gross - total_fee
        return gross, net, total_fee

    def plot_payoff(self, S: Optional[np.ndarray] = None, figsize=(13, 7)):
        if S is None:
            strikes = [opt.strike for opt in self.options]
            S = np.linspace(min(strikes) * 0.6, max(strikes) * 1.5, 600)

        S = np.maximum(S, 1e-8)  # 防止除零

        gross_coin, net_coin, total_fee = self.calculate_payoff(S)

        # 把币收益换算成大约的 USDT 价值
        net_usdt = net_coin * S

        # ---------- 开始画图 ----------
        fig, ax1 = plt.subplots(figsize=figsize)

        # 左轴：币收益
        ax1.plot(S, net_coin, 'b-', linewidth=2.5, label='净收益（BTC）')
        ax1.axhline(0, color='black', linewidth=1)
        ax1.set_xlabel('标的价格 S (USD)', fontsize=12)
        ax1.set_ylabel('收益（BTC）', color='b', fontsize=12)
        ax1.tick_params(axis='y', labelcolor='b')

        # 右轴：USDT 价值
        ax2 = ax1.twinx()
        ax2.plot(S, net_usdt, color='darkorange', linestyle='--', linewidth=2, label='净收益换算 USDT')
        ax2.set_ylabel('收益换算（USDT）', color='darkorange', fontsize=12)
        ax2.tick_params(axis='y', labelcolor='darkorange')

        # 行权价参考线
        for opt in self.options:
            ax1.axvline(opt.strike, color='gray', linestyle=':', alpha=0.6)

        # 图例合并
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')

        plt.title(f'{self.name}\n蓝色实线 = BTC收益 | 橙色虚线 = 换算成USDT的价值', fontsize=14)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

        # 打印关键数据
        print("=" * 65)
        print(f"策略名称       : {self.name}")
        print(f"总手续费       : {total_fee:.6f} BTC")
        print(f"最大净收益(BTC): {np.max(net_coin):.6f} BTC")
        print(f"最大净亏损(BTC): {np.min(net_coin):.6f} BTC")
        print("=" * 65)
