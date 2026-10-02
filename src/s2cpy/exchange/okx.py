from s2cpy.model.option import TradingFeeCalculator


class OkxOptionTradingFeeCalculator(TradingFeeCalculator):
    def __init__(self, multiplier: float = 0.1, contract_size: float = 1):
        """
        FUTURE:
        1. 费率加入VIP的支持。
        """
        self.taker_fee_rate = 0.0003  # 假设taker费率为0.03%
        self.maker_fee_rate = 0.0002  # 假设maker费率为0.02%
        self.multiplier = multiplier
        self.contract_size = contract_size

    """
    [计算okx的交易手续费](https://www.okx.com/zh-hans/help/trading-fee-rules-faq#10-%E4%BA%A4%E6%98%93%E6%89%8B%E7%BB%AD%E8%B4%B9%E5%A6%82%E4%BD%95%E8%AE%A1%E7%AE%97)
    主要依据这里
    """

    def calculate_trading_fee(self, quantity: float, premium: float, is_taker: bool = True) -> float:
        if is_taker:
            fee_rate = self.taker_fee_rate
        else:
            fee_rate = self.maker_fee_rate

        notional_factor = self.multiplier * self.contract_size * quantity
        rate_fee = fee_rate * notional_factor
        cap_fee = 0.07 * premium * notional_factor
        return min(rate_fee, cap_fee)


def btc_cm_option_fee_calculator() -> OkxOptionTradingFeeCalculator:
    return OkxOptionTradingFeeCalculator(multiplier=0.01)


def eth_cm_option_fee_calculator() -> OkxOptionTradingFeeCalculator:
    return OkxOptionTradingFeeCalculator(multiplier=0.1)
