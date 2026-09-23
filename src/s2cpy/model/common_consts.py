from typing import Final, Literal

from s2cpy.model.core_model import Instrument

USDC: Final[Instrument] = Instrument("USDC")

USDT: Final[Instrument] = Instrument("USDT")

SIDE_LONG:int = 1
SIDE_SHORT:int  = -1
SIDE_PARAMETER_TYPE = Literal[-1, 1]