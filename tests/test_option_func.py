from datetime import datetime, timezone

import numpy as np
import pytest
from matplotlib import pyplot as plt

from s2cpy.core.option import OptionPositon, sort_options_by_strike
from s2cpy.model.core_model import BASE_CRYPTO_STABLE_COIN, OptionType
from s2cpy.model.option import CMOption, Leg


class ZeroFeeCalculator:
    def calculate_trading_fee(self, quantity: float, premium: float,
                              is_taker: bool = True, addition: dict | None = None) -> float:
        return 0.0


def make_option(strike: float, identify: str) -> CMOption:
    return CMOption(
        identify=identify,
        strike=strike,
        multiplier=1.0,
        base_ccy="BTC",
        option_type=OptionType.Call,
        premium=100,
        premium_ts=datetime.now(timezone.utc),
        trading_fee_calculator=ZeroFeeCalculator(),
    )


def test_sort_options_by_strike_orders_by_strike_and_returns_nearest_index():
    options = [
        make_option(110.0, "OPT-110"),
        make_option(90.0, "OPT-90"),
        make_option(120.0, "OPT-120"),
        make_option(100.0, "OPT-100"),
    ]

    sorted_options, closest_index = sort_options_by_strike(options, 101.5)

    assert [option.strike for option in sorted_options] == [90.0, 100.0, 110.0, 120.0]
    assert closest_index == 1
    assert sorted_options[closest_index].strike == 100.0


def test_calculate_payoff_infers_ccy_from_legs():
    position = OptionPositon([Leg(make_option(100.0, "OPT-100"), underlying_price=100.0)])

    result = position.calculate_payoff(np.array([100.0]))

    assert result.ccy == "BTC"


def test_calculate_payoff_rejects_ccy_that_does_not_match_legs():
    position = OptionPositon([Leg(make_option(100.0, "OPT-100"), underlying_price=100.0)])

    with pytest.raises(ValueError, match="base_ccy 'ETH'"):
        position.calculate_payoff(np.array([100.0]), ccy="ETH")


def test_calculate_payoff_rejects_legs_with_different_base_ccy():
    btc_option = make_option(100.0, "OPT-BTC")
    eth_option = make_option(100.0, "OPT-ETH")
    eth_option.base_ccy = "ETH"
    position = OptionPositon([
        Leg(btc_option, underlying_price=100.0),
        Leg(eth_option, underlying_price=100.0),
    ])

    with pytest.raises(ValueError, match="same base_ccy"):
        position.calculate_payoff(np.array([100.0]))


def test_calculate_payoff_converts_each_leg_to_stable_coin_value():
    btc_option = make_option(100.0, "OPT-BTC")
    position = OptionPositon([Leg(btc_option, underlying_price=100.0)])
    coin_value = np.array([1000.0])

    result = position.calculate_payoff(coin_value, ccy="USDT")

    expected = ((btc_option.intrinsic_value(coin_value) - btc_option.premium) * btc_option.multiplier) * coin_value
    np.testing.assert_allclose(result.gross, expected)
    np.testing.assert_allclose(result.net, expected)


def test_calculate_payoff_rejects_inference_for_empty_position():
    with pytest.raises(ValueError, match="no legs"):
        OptionPositon([]).calculate_payoff(np.array([100.0]))


def test_plot_payoff_uses_usdt_on_left_and_coin_on_right(monkeypatch):
    monkeypatch.setattr(plt, "show", lambda: None)
    position = OptionPositon([Leg(make_option(100.0, "OPT-100"), underlying_price=100.0)])

    position.plot_payoff(np.array([90.0, 110.0]))

    axes = plt.gcf().axes
    assert len(axes) == 2
    assert axes[0].get_ylabel() == "收益（USDT）"
    assert axes[1].get_ylabel() == "收益（BTC）"
    plt.close("all")


def test_plot_payoff_hides_coin_axis_for_stable_coin_ccy(monkeypatch):
    monkeypatch.setattr(plt, "show", lambda: None)
    position = OptionPositon([Leg(make_option(100.0, "OPT-100"), underlying_price=100.0)])

    position.plot_payoff(
        np.array([90.0, 110.0]),
        ccy=BASE_CRYPTO_STABLE_COIN,
    )

    axes = plt.gcf().axes
    assert len(axes) == 1
    assert axes[0].get_ylabel() == "收益（USDT）"
    plt.close("all")
