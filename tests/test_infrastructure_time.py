from s2cpy.infrastructure.time import now_unix_ms_utc, TimeInterval, get_unix_seconds_utc
from loguru import logger
import pytest
from datetime import datetime, timezone

from s2cpy.infrastructure.time import str_date_to_unix_seconds
from s2cpy.infrastructure.time import str_iso_datetime_to_unix_seconds

def test_now_unix_ms_utc() -> None:
    """
    傻逼的单元测试
    :return:
    """
    logger.info(now_unix_ms_utc())
    logger.info(get_unix_seconds_utc())
    assert now_unix_ms_utc() == now_unix_ms_utc()

@pytest.mark.parametrize(
    "interval,timestamp,expected",
    [
        # exact boundary: timestamp is an exact multiple of the interval
        (TimeInterval.OneMinute, 1620000060, 1620000060),
        # non-boundary: should floor down to the previous minute
        (TimeInterval.OneMinute, 1620000067, 1620000060),
        # larger interval (15 minutes)
        (TimeInterval.FifteenMinute, 1620001234, (1620001234 // 900) * 900),
        # day interval
        (TimeInterval.OneDay, 1650000000, (1650000000 // 86400) * 86400),
        # zero timestamp
        (TimeInterval.OneMinute, 0, 0),
        # negative timestamp: ensure behavior matches Python integer floor-division
        (TimeInterval.OneMinute, -1, (-1 // 60) * 60),
    ],
)
def test_get_close_unix_seconds(interval: TimeInterval, timestamp: int, expected: int):
    """Verify get_close_unix_seconds returns the floored timestamp to the interval.

    These tests document current behavior including negative timestamps which rely
    on Python's floor-division semantics. If you want different semantics for
    negative inputs (e.g. clamp to 0), tell me and I will update the implementation
    and tests accordingly.
    """
    assert interval.get_close_unix_seconds(timestamp) == expected


@pytest.mark.parametrize(
    "interval,expected",
    [
        (TimeInterval.OneMinute, "1m"),
        (TimeInterval.FiveMinute, "5m"),
        (TimeInterval.FifteenMinute, "15m"),
        (TimeInterval.OneHour, "1h"),
        (TimeInterval.FourHour, "4h"),
        (TimeInterval.OneDay, "1d"),
        (TimeInterval.OneWeek, "1w"),
        (TimeInterval.OneMonth, "1mo"),
        (TimeInterval.OneYear, "1y"),
    ],
)
def test_to_str(interval: TimeInterval, expected: str):
    """Verify TimeInterval.to_str returns the expected compact representation."""
    assert interval.to_str() == expected

def test_str_date_to_unix_seconds_epoch():
    # 1970-01-01 00:00:00 UTC should be unix epoch 0
    assert str_date_to_unix_seconds("1970-01-01") == 0


def test_str_date_to_unix_seconds_known_date():
    # verify against a computed UTC datetime to avoid depending on system tz
    expected = int(datetime(2026, 12, 31, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    assert str_date_to_unix_seconds("2026-12-31") == expected


def test_str_date_to_unix_seconds_invalid_format():
    # invalid formats should raise ValueError from date.fromisoformat
    with pytest.raises(ValueError):
        str_date_to_unix_seconds("2026/12/31")

    with pytest.raises(ValueError):
        str_date_to_unix_seconds("not-a-date")


def test_str_iso_datetime_to_unix_seconds_strptime():
    s = "2026-05-13T12:45:00Z"
    expected = int(datetime(2026, 5, 13, 12, 45, 0, tzinfo=timezone.utc).timestamp())
    assert str_iso_datetime_to_unix_seconds(s) == expected

    # non-Z input should raise
    with pytest.raises(ValueError):
        str_iso_datetime_to_unix_seconds("2026-05-13T12:45:00+00:00")

