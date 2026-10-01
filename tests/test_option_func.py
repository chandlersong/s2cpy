from datetime import datetime, timezone

import numpy as np
import pytest

from s2cpy.core.option import OptionPositon, sort_options_by_strike
from s2cpy.model.core_model import OptionType
from s2cpy.model.option import CMOption, Leg


def make_option(strike: float, identify: str) -> CMOption:
    return CMOption(
        identify=identify,
        strike=strike,
        multiplier=1.0,
        base_ccy="BTC",
        option_type=OptionType.Call,
        premium=100,
        premium_ts=datetime.now(timezone.utc),
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
    position = OptionPositon([Leg(make_option(100.0, "OPT-100"))])

    result = position.calculate_payoff(np.array([100.0]))

    assert result.ccy == "BTC"


def test_calculate_payoff_rejects_ccy_that_does_not_match_legs():
    position = OptionPositon([Leg(make_option(100.0, "OPT-100"))])

    with pytest.raises(ValueError, match="base_ccy 'ETH'"):
        position.calculate_payoff(np.array([100.0]), ccy="ETH")


def test_calculate_payoff_rejects_legs_with_different_base_ccy():
    btc_option = make_option(100.0, "OPT-BTC")
    eth_option = make_option(100.0, "OPT-ETH")
    eth_option.base_ccy = "ETH"
    position = OptionPositon([Leg(btc_option), Leg(eth_option)])

    with pytest.raises(ValueError, match="same base_ccy"):
        position.calculate_payoff(np.array([100.0]))


def test_calculate_payoff_rejects_inference_for_empty_position():
    with pytest.raises(ValueError, match="no legs"):
        OptionPositon([]).calculate_payoff(np.array([100.0]))
