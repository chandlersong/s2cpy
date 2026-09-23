import dataclasses
from abc import ABC
from datetime import datetime

import numpy as np

from s2cpy.model.core_model import Instrument, OptionType

"""
因为OKX有着两种期权。币本位所以分开来说
"""


@dataclasses.dataclass(eq=False, kw_only=True)
class CMOption(Instrument):
    strike: float  # 行权价
    multiplier: float
    base_ccy: str
    option_type: OptionType
    premium: float
    premium_ts: datetime

    def intrinsic_value(self, s: np.ndarray) -> np.ndarray:
        if self.option_type == OptionType.Call:
            # max(K-S, 0) / S
            return np.maximum(s - self.strike, 0) / s
        else:
            # max(K-S, 0) / S
            return np.maximum(self.strike - s, 0) / s

    def payoff(self, S: np.ndarray) -> np.ndarray:
        """单腿收益（单位：币）"""
        return 1 * (self.intrinsic_value(S) - self.premium) * self.multiplier
