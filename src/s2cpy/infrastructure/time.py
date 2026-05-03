import time
from enum import Enum


def now_unix_ms_utc() -> int:
    return int(time.time() * 1000)


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

    def to_str(self)->str:
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
