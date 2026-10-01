import datetime
from typing import Union

import numpy as np

from s2cpy.model.core_model import BASE_CRYPTO_STABLE_COIN
from s2cpy.model.option import Option

TOKEN_YES = 1
TOKEN_NO = 0


class HitPriceBinaryOption(Option):

    def intrinsic_value(self, s: np.ndarray) -> np.ndarray:
        res = [self.get_intrinsic_value(v) for v in s]
        return np.array(res)

    """
    对应的是btc-multi-strikes-weekly这类
    """

    def get_intrinsic_value(self, inst_value: float) -> float:
        """
        计算期权的内在价值
        1. 如果是 reach/above 且 inst_value >= strike_price，则 Yes 内在价值为 1，No 内在价值为 0
        2. 如果是 dip/below 且 inst_value <= strike_price，则 Yes 内在价值为 1，No 内在价值为 0

        :param inst_value:
        :return:
        """
        """
        对于 HitPriceBinaryOption，内在价值为 0.0 或 1.0（表示 token 的最终兑付），
        规则：
        - 如果 is_above 为 True（reach），当 inst_value >= strike_price 时事件成立；否则不成立。
        - 如果 is_above 为 False（dip），当 inst_value <= strike_price 时事件成立；否则不成立。
        - 对于 TOKEN_YES（direction == TOKEN_YES），事件成立时返回 1.0，否则 0.0。
        - 对于 TOKEN_NO（direction == TOKEN_NO），事件成立时返回 0.0，否则 1.0。
        """
        try:
            strike = float(self.strike)
        except Exception:
            return 0.0

        # 事件成立判断
        if self.is_above:
            event_happened = inst_value >= strike
        else:
            event_happened = inst_value <= strike

        if self.direction == TOKEN_YES:
            return 1.0 if event_happened else 0.0
        else:
            return 0.0 if event_happened else 1.0

    def __init__(self, asset_slug: str, expiration_ms: int, premium: float = None,
                 premium_ts: Union[str, datetime.datetime] = None):
        """

        可能的slug样式：
        will-bitcoin-dip/reach-xxk-month-date-month-date-year_Yes/No
        strike_price = xx*1000
        direction = TOKEN_YES if Yes else TOKEN_NO
        is_above = True if reach else False


        expiration_ms 为UTC的unix时间，转换成self.expiration
        列子：
        will-bitcoin-reach-80k-august-31-september-6-2026_Yes
        strike_price = 80000
        direction = TOKEN_YES
        is_above = True
        will-bitcoin-reach-80k-august-31-september-6-2026_No
        strike_price = 80000
        direction = TOKEN_NO
        is_above = True

        will-bitcoin-dip-to-76k-august-31-september-6-2026_No
        strike_price = 76000
        direction = TOKEN_NO
        is_above = False
        will-bitcoin-dip-to-76k-august-31-september-6-2026_Yes
        strike_price = 76000
        direction = TOKEN_YES
        is_above = False

        will-bitcoin-dip-to-77pt5k-in-september-2026-from-september-11_Yes
        strike_price = 77500
        direction = TOKEN_YES
        is_above = False

        will-bitcoin-dip-to-30000-by-december-31-2026-971-191-116-343-999-758-299-813-237_No
        strike_price = 30000
        direction = TOKEN_NO
        is_above = False

        FUTURE:
        1. 支持BTC之外的标的。
        :param asset_slug:
        :param expiration_ms:
        """
        import re
        self.premium = premium
        self.asset_slug = asset_slug
        self.identify = asset_slug
        self.premium_ts = premium_ts
        self.multiplier = 1

        # token 后缀 Yes/No
        if "_" in asset_slug:
            parts = asset_slug.rsplit("_", 1)
            slug_part, token_part = parts[0], parts[1]
        else:
            slug_part, token_part = asset_slug, ""

        self.direction = TOKEN_YES if token_part.lower().startswith("yes") else TOKEN_NO

        # is_above: prefer explicit keywords
        if "reach" in slug_part:
            self.is_above = True
        elif "dip" in slug_part:
            self.is_above = False
        else:
            self.is_above = True

        # 尝试通过上下文匹配 strike
        strike_candidate = None
        strike_pattern = r"([0-9]+(?:(?:\.|pt)[0-9]+)?k?)"
        m = re.search(r"reach-" + strike_pattern, slug_part, flags=re.IGNORECASE)
        if not m:
            m = re.search(r"dip-to-" + strike_pattern, slug_part, flags=re.IGNORECASE)
        if not m:
            m = re.search(r"to-" + strike_pattern, slug_part, flags=re.IGNORECASE)
        if m:
            strike_candidate = m.group(1)
        else:
            # 回退：提取所有数字片段，优先带 k 的，其次选择合理范围的第一个
            nums = re.findall(r'(\d+(?:\.\d+)?k?)', slug_part)
            pick = None
            if nums:
                for n in nums:
                    if n.lower().endswith('k'):
                        pick = n
                        break
                if not pick:
                    for n in nums:
                        try:
                            v = float(n.rstrip('k'))
                        except Exception:
                            continue
                        # 排除年份等（如 2026），选择较小但合理的值
                        if 1 <= v <= 1000000:
                            pick = n
                            break
            strike_candidate = pick

        if strike_candidate:
            s = strike_candidate.lower().replace("pt", ".")
            if s.endswith('k'):
                self.strike = float(s[:-1]) * 1000.0
            else:
                self.strike = float(s)
        else:
            self.strike = 1

        # expiration_ms 为 UTC unix 毫秒
        self.validate_before = expiration_ms
        self.base_ccy = BASE_CRYPTO_STABLE_COIN
