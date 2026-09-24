from datetime import date, datetime, timedelta, timezone

import pytest

from s2cpy.model.option import ExpirationDate


def test_expiration_date_accepts_supported_inputs():
    expected = ExpirationDate("20260925")

    assert ExpirationDate(date(2026, 9, 25)) == expected
    assert ExpirationDate(datetime(2026, 9, 25, 12)) == expected
    assert ExpirationDate(2026, 9, 25) == expected
    assert ExpirationDate(year=2026, month=9, day=25) == expected


def test_expiration_date_formats_as_yyyymmdd():
    expiration = ExpirationDate("20260925")

    assert str(expiration) == "20260925"
    assert repr(expiration) == "ExpirationDate('20260925')"


def test_expiration_date_can_be_compared_and_used_as_dict_key():
    earlier = ExpirationDate("20260924")
    later = ExpirationDate("20260925")

    assert earlier < later
    assert later > earlier
    assert earlier != later
    assert {earlier: "value"}[ExpirationDate(date(2026, 9, 24))] == "value"


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("20260924", 1),
        (date(2026, 9, 25), 0),
        (date(2026, 9, 26), -1),
        (datetime(2026, 9, 24, 23), 1),
        (
            datetime(2026, 9, 25, 0, tzinfo=timezone(timedelta(hours=8))),
            1,
        ),
    ],
)
def test_days_until_returns_calendar_days(reference, expected):
    assert ExpirationDate("20260925").days_until(reference) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        20260925,
        "2026-09-25",
        object(),
    ],
)
def test_expiration_date_rejects_invalid_values(value):
    with pytest.raises((TypeError, ValueError)):
        ExpirationDate(value)


@pytest.mark.parametrize("value", ["2026-09-24", None, object()])
def test_days_until_rejects_invalid_values(value):
    with pytest.raises((TypeError, ValueError)):
        ExpirationDate("20260925").days_until(value)
