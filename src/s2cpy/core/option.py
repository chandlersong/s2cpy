import dataclasses
from typing import List, Tuple, Optional

import numpy as np
from matplotlib import pyplot as plt

from s2cpy.model.core_model import OptionType, BASE_CRYPTO_STABLE_COIN
from s2cpy.model.option import CMOption, ExpirationDate, Leg, OptionList


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


NOT_FOUND_OPTION_INDEX = -1


def _find_high_underlying_price(options: List[CMOption], underlying_price: float) -> int:
    for index, option in enumerate(options):
        if option.strike > underlying_price:
            return index
    return NOT_FOUND_OPTION_INDEX


def group_options_by_expiration_date(
        options: List[CMOption],
        underlying_price: float
) -> dict[ExpirationDate, OptionList]:
    """
    把options根据其expiration_date进行分组。
    然后根据put和call进行分组。

    关于underlying_price:
    每一个OptionList统一取underlying_price.
    call_anchor_index:为call里面，以期权里最价格最低的虚值期权，即strike大于underlying_price里面，strike最小的
    put_anchor_index:为put里面，以期权里最价格最低的实质期权，即strike大于underlying_price里面，strike最小的
    :param underlying_price:
    :param options:
    :return:
    """
    grouped: dict[Optional[ExpirationDate], OptionList] = {}
    for option in options:
        expiration_date = option.expiration_date
        if expiration_date not in grouped:
            grouped[expiration_date] = OptionList(
                put=[],
                call=[],
                underlying_price=underlying_price,
                call_least_otm_index=NOT_FOUND_OPTION_INDEX,
                put_least_itm_index=NOT_FOUND_OPTION_INDEX,
            )

        option_list = grouped[expiration_date]
        if option.option_type is OptionType.Put:
            option_list.put.append(option)
        elif option.option_type is OptionType.Call:
            option_list.call.append(option)
        else:
            raise ValueError(f"Unsupported option type: {option.option_type!r}")

    for option_list in grouped.values():
        option_list.call = sorted(option_list.call, key=lambda o: o.strike)
        option_list.put = sorted(option_list.put, key=lambda o: o.strike)
        option_list.call_least_otm_index = _find_high_underlying_price(
            option_list.call, underlying_price
        )
        option_list.put_least_itm_index = _find_high_underlying_price(
            option_list.put, underlying_price
        )

    return grouped


@dataclasses.dataclass
class OptionPositionCurve:
    gross: np.ndarray
    net: np.ndarray
    total_fee: float
    ccy: str
    coin_value: np.ndarray

    @property
    def is_stable_coin(self) -> bool:
        return self.ccy == BASE_CRYPTO_STABLE_COIN

    @property
    def stable_coin_net(self) -> np.ndarray:
        """
        把币收益换算成大约的 USDT 价值
        :return:
        """
        if self.is_stable_coin:
            return self.net
        return self.net * self.coin_value

    @property
    def stable_coin_gross(self) -> np.ndarray:
        """
        把币收益换算成大约的 USDT 价值
        :return:
        """
        if self.is_stable_coin:
            return self.gross
        return self.gross * self.coin_value


"""
这个类的定位还是很模糊。我也不太清楚这个具体的类到底是干什么。
其实我想要的就是，给一组期权。然后计算出资金曲线。
"""


class OptionPositon:
    def __init__(
            self,
            legs: List[Leg],
            fee_per_contract: float = 0.0,
            fee_rate: float = 0.0,
            include_close_fee: bool = True,
            name: str = "OKX 币本位策略",

    ):
        self.legs = legs
        self.fee_per_contract = fee_per_contract
        self.fee_rate = fee_rate
        self.include_close_fee = include_close_fee
        self.name = name

    def calculate_fees(self, ccy: Optional[str] = None) -> float:
        """
        希望每个交易锁不同的交易手续费。
        所以由各个交易所单独处理和计算，这里只是计算。
        :return:
        """
        if ccy is not None and ccy != BASE_CRYPTO_STABLE_COIN:
            leg_ccys = {leg.base_ccy for leg in self.legs}
            if len(leg_ccys) > 1:
                raise ValueError("All option legs must have the same base_ccy")
            if leg_ccys != {ccy}:
                raise ValueError(f"All option legs must have base_ccy {ccy!r}")
        total_fee = sum([leg.trading_fee(ccy=ccy) for leg in self.legs])
        return total_fee

    """
    计算收益曲线。返回币收益和换算成USDT的收益曲线。
    1. gross: 单腿收益曲线的总和
    2. net: 扣除手续费后的收益曲线
    3. total_fee: 总手续费
    
    # ccy确定流程
    1. ccy不为BASE_CRYPTO_STABLE_COIN时，做以下检测
       - 所有leg的base_ccy必须相同，否则抛出异常
         - 所有leg的base_ccy必须为ccy，否则抛出异常
    2. 如果说ccy为None，则使用legs的base_ccy作为ccy。返回的为币收益曲线。
    """

    def calculate_payoff(self, coin_value: np.ndarray, ccy: Optional[str] = None) -> OptionPositionCurve:
        """返回单位：币"""
        if ccy is None:
            if not self.legs:
                raise ValueError("Cannot infer ccy from an option position with no legs")
            ccy = self.legs[0].base_ccy

        if ccy != BASE_CRYPTO_STABLE_COIN:
            leg_ccys = {leg.base_ccy for leg in self.legs}
            if len(leg_ccys) > 1:
                raise ValueError("All option legs must have the same base_ccy")
            if leg_ccys != {ccy}:
                raise ValueError(f"All option legs must have base_ccy {ccy!r}")

        gross = np.zeros_like(coin_value, dtype=float)
        '''
        在计算的时候，gross是所有leg的收益曲线的总和。然后再减去手续费，得到net。
        # ccy
        到这里时，只有两种情况。需要对每条leg的曲线，做特殊处理。
        - 如果ccy为BASE_CRYPTO_STABLE_COIN,且leg的base_ccy不为BASE_CRYPTO_STABLE_COIN，则返回gross和net是换算成USDT的收益曲线。
        - 如果ccy不为BASE_CRYPTO_STABLE_COIN，则返回的net是币收益曲线。
        '''
        for leg in self.legs:
            leg_payoff = leg.payoff(coin_value)
            if ccy == BASE_CRYPTO_STABLE_COIN and leg.base_ccy != BASE_CRYPTO_STABLE_COIN:
                leg_payoff = leg_payoff * coin_value
            gross += leg_payoff

        total_fee = self.calculate_fees(ccy=ccy)
        net = gross - total_fee
        return OptionPositionCurve(gross=gross, net=net, total_fee=total_fee, ccy=ccy, coin_value=coin_value)

    def plot_payoff(self, S: Optional[np.ndarray] = None, figsize=(13, 7), ccy: Optional[str] = None):
        if S is None:
            strikes = [leg.option.strike for leg in self.legs]
            S = np.linspace(min(strikes) * 0.6, max(strikes) * 1.5, 600)

        S = np.maximum(S, 1e-8)  # 防止除零

        payoff_curve = self.calculate_payoff(S, ccy=ccy)
        net_usdt = payoff_curve.stable_coin_net

        # ---------- 开始画图 ----------
        fig, ax1 = plt.subplots(figsize=figsize)

        # 左轴：USDT 收益
        ax1.plot(S, net_usdt, color='darkorange', linestyle='--', linewidth=2,
                 label='净收益（USDT）')
        ax1.axhline(0, color='black', linewidth=1)
        ax1.set_xlabel('标的价格 S (USD)', fontsize=12)
        ax1.set_ylabel('收益（USDT）', color='darkorange', fontsize=12)
        ax1.tick_params(axis='y', labelcolor='darkorange')

        # 稳定币计价时收益本身已是 USDT，不再重复显示币收益轴。
        axes = [ax1]
        if not payoff_curve.is_stable_coin:
            ax2 = ax1.twinx()
            ax2.plot(S, payoff_curve.net, 'b-', linewidth=2.5,
                     label=f'净收益（{payoff_curve.ccy}）')
            ax2.set_ylabel(f'收益（{payoff_curve.ccy}）', color='b', fontsize=12)
            ax2.tick_params(axis='y', labelcolor='b')
            axes.append(ax2)

        # 行权价参考线
        for leg in self.legs:
            ax1.axvline(leg.option.strike, color='gray', linestyle=':', alpha=0.6)

        # 图例合并
        lines, labels = [], []
        for axis in axes:
            axis_lines, axis_labels = axis.get_legend_handles_labels()
            lines.extend(axis_lines)
            labels.extend(axis_labels)
        ax1.legend(lines, labels, loc='best')

        title = f'{self.name}\n橙色虚线 = USDT收益'
        if not payoff_curve.is_stable_coin:
            title += f' | 蓝色实线 = {payoff_curve.ccy}收益'
        plt.title(title, fontsize=14)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

        # 打印关键数据
        print("=" * 65)
        print(f"策略名称       : {self.name}")
        print(f"总手续费       : {payoff_curve.total_fee:.6f} {payoff_curve.ccy}")
        print(f"最大净收益({payoff_curve.ccy}): {np.max(payoff_curve.net):.6f} {payoff_curve.ccy}")
        print(f"最大净亏损({payoff_curve.ccy}): {np.min(payoff_curve.net):.6f} {payoff_curve.ccy}")
        print("=" * 65)
