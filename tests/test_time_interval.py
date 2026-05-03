import pytest

from s2cpy.infrastructure.time import TimeInterval


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


