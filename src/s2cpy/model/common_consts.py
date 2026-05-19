from typing import Final, Literal

from s2cpy.model.core_model import Asset

USDC: Final[Asset] = Asset("USDC")

USDT: Final[Asset] = Asset("USDT")

SIDE_LONG:int = 1
SIDE_SHORT:int  = -1
SIDE_PARAMETER_TYPE = Literal[-1, 1]