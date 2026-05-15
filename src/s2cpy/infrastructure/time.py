import time
import calendar
from enum import Enum
from datetime import date, datetime, time as dt_time, timezone


def now_unix_ms_utc() -> int:
    return int(time.time() * 1000)


def get_unix_seconds_utc() -> int:
    return int(time.time())


def str_date_to_unix_seconds(str_date: str) -> int:
    """
    :param str_date: formate是 YYYY-MM-DD
    :return: unix timestamp，utc时区，然后精确到s
    """
    # 解释：原实现使用 time.mktime => 按本地时区将 struct_time 转换为 epoch，
    # 这会导致结果依赖运行环境的时区。这里改为把日期视为 UTC 的当天 00:00:00，
    # 并返回对应的 UTC unix seconds，保证跨时区一致性。
    d = date.fromisoformat(str_date)
    dt = datetime.combine(d, dt_time(0, 0, 0), tzinfo=timezone.utc)
    return int(dt.timestamp())


def str_iso_datetime_to_unix_seconds(str_dt: str) -> int:
    """Parse an ISO-8601 datetime string like '2026-05-13T12:45:00Z' using strptime
    and return UTC unix seconds.

    This implementation uses time.strptime to parse the string with a '%Y-%m-%dT%H:%M:%SZ'
    format and then calendar.timegm to convert the resulting struct_time to seconds since
    the epoch treating the struct_time as UTC. It intentionally only supports the 'Z'
    (UTC) suffix; other ISO offsets (e.g. '+00:00' or '-04:00') are not handled by this
    helper.
    """
    # expect a trailing Z for UTC
    if not str_dt.endswith("Z"):
        raise ValueError("Only 'Z' (UTC) timezone is supported by this parser")

    # parse using time.strptime which returns a struct_time
    tm = time.strptime(str_dt, "%Y-%m-%dT%H:%M:%SZ")
    # calendar.timegm treats the tuple as UTC and returns epoch seconds
    return calendar.timegm(tm)


class TimeInterval(Enum):
    OneMinute = 60
    FiveMinute = 5 * 60
    FifteenMinute = 15 * 60
    OneHour = 60 * 60
    FourHour = 4 * 60 * 60
    OneDay = 24 * 60 * 60
    OneWeek = 7 * 24 * 60 * 60
    OneMonth = 30 * 24 * 60 * 60
    OneYear = 365 * 24 * 60 * 60

    def to_str(self) -> str:
        """Return a compact human-readable string for the interval.

        Examples:
        - OneMinute -> "1m"
        - FiveMinute -> "5m"
        - OneHour -> "1h"
        - OneDay -> "1d"
        - OneMonth -> "1mo"
        - OneYear -> "1y"

        We format using the largest whole unit among years, months(30d), weeks,
        days, hours, minutes, and seconds. Months are represented as "mo" to
        avoid confusion with minutes.
        """
        seconds = int(self.value)

        units = [
            (365 * 24 * 60 * 60, "y"),
            (30 * 24 * 60 * 60, "mo"),
            (7 * 24 * 60 * 60, "w"),
            (24 * 60 * 60, "d"),
            (60 * 60, "h"),
            (60, "m"),
            (1, "s"),
        ]

        for unit_seconds, suffix in units:
            if seconds % unit_seconds == 0 and seconds >= unit_seconds:
                return f"{seconds // unit_seconds}{suffix}"

        # Fallback: express as seconds if no larger whole unit matched
        return f"{seconds}s"

    def to_milliseconds(self):
        return self.value * 1000

    def to_seconds(self):
        return self.value

    def get_close_unix_ms(self, timestamp: int) -> int:
        """
        给定一个unix time，计算已经过的最近的单元时间
        :param timestamp:
        :return:
        """
        return self.get_close_unix_seconds(timestamp // 1000) * 1000

    def get_close_unix_seconds(self, timestamp: int) -> int:
        """
        给定一个unix time，计算已经过的最近的un
        :param timestamp:
        :return:
        """
        interval_second = self.to_seconds()
        return (timestamp // interval_second) * interval_second

    def get_close_now_ms(self) -> int:
        return self.get_close_unix_ms(now_unix_ms_utc())

    def get_close_now_second(self) -> int:
        return self.get_close_unix_seconds(get_unix_seconds_utc())
