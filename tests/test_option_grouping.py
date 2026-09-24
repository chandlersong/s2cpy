from datetime import datetime, timezone

from s2cpy.core.option import OptionList, group_options_by_expiration_date
from s2cpy.model.core_model import OptionType
from s2cpy.model.option import CMOption, ExpirationDate


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
    )


def test_group_options_by_expiration_date_groups_puts_and_calls():
    call = make_option("call-0925", OptionType.Call, "20260925")
    put = make_option("put-0925", OptionType.Put, "20260925")
    other_call = make_option("call-0926", OptionType.Call, "20260926")

    grouped = group_options_by_expiration_date([call, put, other_call])

    assert grouped == {
        ExpirationDate("20260925"): OptionList(put=[put], call=[call]),
        ExpirationDate("20260926"): OptionList(put=[], call=[other_call]),
    }


def test_group_options_by_expiration_date_preserves_order():
    calls = [
        make_option("call-1", OptionType.Call, "20260925"),
        make_option("call-2", OptionType.Call, "20260925"),
    ]

    grouped = group_options_by_expiration_date(calls)

    assert grouped[ExpirationDate("20260925")].call == calls


def test_group_options_by_expiration_date_groups_permanent_options_under_none():
    option = make_option("permanent", OptionType.Put, None)

    grouped = group_options_by_expiration_date([option])

    assert grouped[None] == OptionList(put=[option], call=[])


def test_group_options_by_expiration_date_returns_empty_dict_for_empty_input():
    assert group_options_by_expiration_date([]) == {}
