from datetime import datetime, timezone
from typing import Dict, Any

from s2cpy.core.option import OptionList, group_options_by_expiration_date
from s2cpy.model.core_model import OptionType
from s2cpy.model.option import CMOption, ExpirationDate, TradingFeeCalculator


class ZeroTradingFeeCalculator(TradingFeeCalculator):
    def calculate_trading_fee(self, quantity: float, premium: float,
                              is_taker: bool = True, addition: Dict[str, Any] = None) -> float:
        return 0.0

def make_option(
        identify: str,
        option_type: OptionType,
        expiration: str | None,
) -> CMOption:
    validate_before = None
    if expiration is not None:
        validate_before = int(
            datetime.strptime(expiration, "%Y%m%d")
            .replace(tzinfo=timezone.utc)
            .timestamp()
            * 1000
        )

    return CMOption(
        identify=identify,
        strike=100.0,
        multiplier=1.0,
        base_ccy="BTC",
        option_type=option_type,
        premium=1.0,
        premium_ts=datetime(2026, 9, 1, tzinfo=timezone.utc),
        validate_before=validate_before,
        trading_fee_calculator=ZeroTradingFeeCalculator()  # type: ignore
    )


def test_group_options_by_expiration_date_groups_puts_and_calls():
    call = make_option("call-0925", OptionType.Call, "20260925")
    put = make_option("put-0925", OptionType.Put, "20260925")
    other_call = make_option("call-0926", OptionType.Call, "20260926")

    grouped = group_options_by_expiration_date(
        [call, put, other_call],
        underlying_price=101.0,
    )

    assert grouped == {
        ExpirationDate("20260925"): OptionList(
            put=[put],
            call=[call],
            underlying_price=101.0,
            call_least_otm_index=-1,
            put_least_itm_index=-1,
        ),
        ExpirationDate("20260926"): OptionList(
            put=[],
            call=[other_call],
            underlying_price=101.0,
            call_least_otm_index=-1,
            put_least_itm_index=-1,
        ),
    }


def test_group_options_by_expiration_date_preserves_order():
    calls = [
        make_option("call-1", OptionType.Call, "20260925"),
        make_option("call-2", OptionType.Call, "20260925"),
    ]

    grouped = group_options_by_expiration_date(calls, underlying_price=101.0)

    assert grouped[ExpirationDate("20260925")].call == calls


def test_group_options_by_expiration_date_sorts_options_and_initializes_least_indexes():
    call_far = make_option("call-110", OptionType.Call, "20260925")
    call_near = make_option("call-100", OptionType.Call, "20260925")
    put_far = make_option("put-90", OptionType.Put, "20260925")
    put_near = make_option("put-105", OptionType.Put, "20260925")
    call_far.strike = 110.0
    call_near.strike = 100.0
    put_far.strike = 90.0
    put_near.strike = 105.0

    grouped = group_options_by_expiration_date(
        [call_far, call_near, put_far, put_near],
        underlying_price=103.0,
    )
    result = grouped[ExpirationDate("20260925")]

    assert result.call == [call_near, call_far]
    assert result.put == [put_far, put_near]
    assert result.call_least_otm_index == 1
    assert result.put_least_itm_index == 1


def test_group_options_by_expiration_date_groups_permanent_options_under_none():
    option = make_option("permanent", OptionType.Put, None)

    grouped = group_options_by_expiration_date([option], underlying_price=100.0)

    assert grouped[None] == OptionList(
        put=[option],
        call=[],
        underlying_price=100.0,
        call_least_otm_index=-1,
        put_least_itm_index=-1,
    )


def test_group_options_by_expiration_date_returns_empty_dict_for_empty_input():
    assert group_options_by_expiration_date([], underlying_price=100.0) == {}
