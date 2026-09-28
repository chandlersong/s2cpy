"""
# Leg和Option的一些思考。
本质是标的和仓位区别的思考。其实期权还是一个挺复杂的东西。
因为我想的是leg表示的是仓位。而Option表示的是具体东西。


"""
import dataclasses
from datetime import date as Date, datetime, timedelta, timezone, date
from functools import total_ordering
from typing import Optional, List
import numpy as np

from s2cpy.model.core_model import Instrument, OptionType

"""
代表行权日，需求为。
1. 能够比较大小。
2. 输出的字符串格式为YYYYMMDD
3. 能够作为dict里面的key。
"""


@total_ordering
class ExpirationDate:
    """Immutable value object for an option expiration date."""

    __slots__ = ("_date",)

    def __init__(
            self,
            value: Date | str | int | None = None,
            month: int | None = None,
            day: int | None = None,
            *,
            year: int | None = None,
    ) -> None:
        if year is not None:
            if value is not None or month is None or day is None:
                raise TypeError("year, month and day must be provided together")
            value = year

        if isinstance(value, int):
            if month is None or day is None:
                raise TypeError("month and day are required when value is a year")
            parsed = date(value, month, day)
        elif month is not None or day is not None:
            raise TypeError("month and day can only be used with a year")
        elif isinstance(value, datetime):
            parsed = value.date()
        elif isinstance(value, Date):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.strptime(value, "%Y%m%d").date()
            except ValueError as exc:
                raise ValueError(
                    "expiration date must use the YYYYMMDD format"
                ) from exc
        else:
            raise TypeError(
                "expiration date must be a date, datetime, YYYYMMDD string, "
                "or year/month/day"
            )

        object.__setattr__(self, "_date", parsed)

    @property
    def date(self) -> Date:
        return self._date

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __str__(self) -> str:
        return self._date.strftime("%Y%m%d")

    def days_until(self, value: Date | datetime | str) -> int:
        """Return the number of calendar days from ``value`` to expiration."""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            reference_date = value.astimezone(timezone.utc).date()
        elif isinstance(value, Date):
            reference_date = value
        elif isinstance(value, str):
            try:
                reference_date = datetime.strptime(value, "%Y%m%d").date()
            except ValueError as exc:
                raise ValueError(
                    "reference date must use the YYYYMMDD format"
                ) from exc
        else:
            raise TypeError("reference time must be a date, datetime, or YYYYMMDD string")

        return (self._date - reference_date).days

    def __repr__(self) -> str:
        return f"{type(self).__name__}({str(self)!r})"

    def __hash__(self) -> int:
        return hash(self._date)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ExpirationDate):
            return self._date == other._date
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, ExpirationDate):
            return self._date < other._date
        return NotImplemented


@dataclasses.dataclass(eq=False, kw_only=True)
class CMOption(Instrument):
    strike: float  # 行权价
    multiplier: float
    base_ccy: str
    option_type: OptionType
    premium: float
    premium_ts: datetime

    @property
    def expiration_date(self) -> Optional[ExpirationDate]:
        """Return the UTC expiration date represented by ``validate_before``."""
        if self.validate_before is None:
            return None

        return ExpirationDate(
            datetime(1970, 1, 1, tzinfo=timezone.utc)
            + timedelta(milliseconds=self.validate_before)
        )

    def intrinsic_value(self, s: np.ndarray) -> np.ndarray:
        if self.option_type == OptionType.Call:
            # max(K-S, 0) / S
            return np.maximum(s - self.strike, 0) / s
        else:
            # max(K-S, 0) / S
            return np.maximum(self.strike - s, 0) / s

    def payoff(self, S: np.ndarray) -> np.ndarray:
        """单腿收益（单位：币）"""
        return (self.intrinsic_value(S) - self.premium) * self.multiplier


@dataclasses.dataclass
class Leg:
    option: CMOption
    quantity: float = 1

    def intrinsic_value(self, s: np.ndarray) -> np.ndarray:
        return self.option.intrinsic_value(s) * self.quantity

    def payoff(self, S: np.ndarray) -> np.ndarray:
        """单腿收益（单位：币）"""
        return self.option.payoff(S) * self.quantity


@dataclasses.dataclass
class OptionList:
    put: List[CMOption]
    call: List[CMOption]
    underlying_price: float
    call_least_otm_index: int  # call里面最小的虚值期权的index
    put_least_itm_index: int  # put里面，最小的实值期权
