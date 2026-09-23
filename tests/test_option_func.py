from s2cpy.core.option import sort_options_by_strike
from s2cpy.model.core_model import OptionType
from s2cpy.model.option import CMOption


def make_option(strike: float, identify: str) -> CMOption:
    return CMOption(
        identify=identify,
        strike=strike,
        multiplier=1.0,
        base_ccy="BTC",
        option_type=OptionType.Call,
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
