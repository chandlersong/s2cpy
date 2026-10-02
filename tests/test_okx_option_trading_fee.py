import pytest

from s2cpy.exchange.okx import (
    OkxOptionTradingFeeCalculator,
    btc_cm_option_fee_calculator,
    eth_cm_option_fee_calculator,
)


def test_calculates_taker_fee_at_taker_rate():
    calculator = OkxOptionTradingFeeCalculator()

    assert calculator.calculate_trading_fee(quantity=2, premium=0.05) == pytest.approx(0.00006)


def test_calculates_maker_fee_at_maker_rate():
    calculator = OkxOptionTradingFeeCalculator()

    assert calculator.calculate_trading_fee(quantity=2, premium=0.05, is_taker=False) == pytest.approx(0.00004)


def test_caps_fee_at_seven_percent_of_premium():
    calculator = OkxOptionTradingFeeCalculator()

    assert calculator.calculate_trading_fee(quantity=2, premium=0.001) == pytest.approx(0.000014)


def test_fee_scales_with_multiplier_contract_size_and_quantity():
    calculator = OkxOptionTradingFeeCalculator(multiplier=0.5, contract_size=10)

    assert calculator.calculate_trading_fee(quantity=3, premium=0.1) == pytest.approx(0.0045)


@pytest.mark.parametrize(
    ("calculator_factory", "expected_multiplier"),
    [
        (btc_cm_option_fee_calculator, 0.01),
        (eth_cm_option_fee_calculator, 0.1),
    ],
)
def test_coin_margined_factories_set_multiplier(calculator_factory, expected_multiplier):
    calculator = calculator_factory()

    assert calculator.multiplier == expected_multiplier
