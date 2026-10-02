"""
# Leg和Option的一些思考。
本质是标的和仓位区别的思考。其实期权还是一个挺复杂的东西。
因为我想的是leg表示的是仓位。而Option表示的是具体东西。

# option的抽象过程。
发觉自己给自己上难度。要把这个抽象出来。但是实际上，不得不做。主要是Option的种类实在太多。
1. Polymarket的各种类型，比如时候达到过，最后落点。
2. Okx的期权有币本位喝U本位，计算实在太多。

"""
import dataclasses
from datetime import date as Date, datetime, timedelta, timezone, date
from functools import total_ordering
from typing import Optional, List, Protocol, Final, Any, Dict
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


"""
"""


class TradingFeeCalculator(Protocol):
    """
    交易手续费计算器
    """

    def calculate_trading_fee(self, quantity: float, premium: float,
                              is_taker: bool = True, addition: Dict[str, Any] = None) -> float:
        """
        计算交易手续费。因为不同交易所的手续费计算方式不同，所以需要在子类中实现。
        因为有些信息，比如是卖盒卖。所以多了一个addition。
        :param addition: 其余的函数
        :param is_taker: 是否吃单
        :param quantity: 成交数量
        :param premium: 成交价格
        :return:
        """
        pass


@dataclasses.dataclass(kw_only=True)
class Option(Instrument, Protocol):
    strike: float  # 行权价
    multiplier: float
    base_ccy: str
    option_type: OptionType
    trade_type: str = "NONE"
    premium: float  # 权利金
    premium_ts: datetime  # 权利金时间戳
    trading_fee_calculator: TradingFeeCalculator

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
        pass

    def calculate_trading_fee(self, quantity: float, premium: Optional[float] = None,
                              is_taker: bool = True, **kwargs: Any) -> float:
        """
        计算交易手续费。因为不同交易所的手续费计算方式不同，所以需要在子类中实现。
        :param is_taker: 是否吃单
        :param quantity: 成交数量
        :param premium: 成交价格
        :return:
        """
        if premium is None:
            premium = self.premium
        return self.trading_fee_calculator.calculate_trading_fee(quantity, premium, is_taker)


@dataclasses.dataclass(eq=False, kw_only=True)
class CMOption(Option):

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
    option: Option
    premium: float
    quantity: float = 1

    def __init__(self, option: Option, quantity: Optional[float] = None, premium: Optional[float] = None):
        self.option = option
        if premium is None:
            premium = option.premium
        self.premium = premium
        if quantity is None:
            quantity = 1
        self.quantity = quantity

    @property
    def base_ccy(self) -> str:
        return self.option.base_ccy

    def intrinsic_value(self, s: np.ndarray) -> np.ndarray:
        return self.option.intrinsic_value(s) * self.quantity

    def payoff(self, S: np.ndarray) -> np.ndarray:
        """单腿收益（单位：币）"""
        return (self.option.intrinsic_value(S) - self.premium) * self.option.multiplier * self.quantity

    def trading_fee(self, premium: float = None) -> float:
        if premium is None:
            premium = self.premium
        return self.option.calculate_trading_fee(quantity=self.quantity, premium=premium)


@dataclasses.dataclass
class OptionList:
    put: List[Option]
    call: List[Option]
    underlying_price: float
    call_least_otm_index: int  # call里面最小的虚值期权的index
    put_least_itm_index: int  # put里面，最小的实值期权
