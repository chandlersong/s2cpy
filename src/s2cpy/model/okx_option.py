import dataclasses

from s2cpy.model.core_model import Instrument, OptionType

"""
因为OKX有着两种期权。币本位所以分开来说
"""


@dataclasses.dataclass(eq=False, kw_only=True)
class OkxOption(Instrument):
    strike: float  # 行权价
    multiplier: float
    base_ccy: str
    option_type: OptionType
