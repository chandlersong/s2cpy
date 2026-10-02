from typing import Final, Literal

from s2cpy.model.core_model import Instrument

USDC: Final[str] ="USDC"

USDT: Final[str] = "USDT"

SIDE_LONG:int = 1
SIDE_SHORT:int  = -1
SIDE_PARAMETER_TYPE = Literal[-1, 1]