from dataclasses import dataclass


class PolyMarketError(Exception):
    """所有异常的基类"""
    error_code: str = "UNKNOWN_ERROR"

    def __str__(self):
        if hasattr(self, 'error_code'):
            return f"[{self.error_code}] {super().__str__()}"
        return super().__str__()


@dataclass
class MarketCloseError(PolyMarketError):
    """用户不存在"""
    error_code: str = "Market closed"
    market_id: str = None
    asset_id: str = None

    def __post_init__(self):
        msg = f"Market {self.market_id} close, assert id:{self.asset_id}."
        super().__init__(msg)
