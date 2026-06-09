"""
主要是polymarket的一些工具类方法
"""
from datetime import datetime, timezone
from typing import List, Dict

from s2cpy.infrastructure.time import str_iso_datetime_to_unix_seconds
from s2cpy.model.core_model import Asset
from s2cpy.model.polymarket_io import Market


def convert_markets_2_assets(market: Market) -> Dict[str, Asset]:
    """
    把market转换成assert
    :param market:
    :return:
    """
    if market.endDate is None:
        raise ValueError(f"market:{market.slug} market.endDate is None")
    validate_before = str_iso_datetime_to_unix_seconds(market.endDate)
    result: Dict[str, Asset] = {}
    outcomes = market.outcomes
    slug = market.slug
    for index, token_id in enumerate(market.clobTokenIds or []):
        result[token_id] = Asset(
            identify=f"{slug}-{outcomes[index]}",
            external_id=token_id,
            validate_before=validate_before,
            extra_info={"market": market},
        )
    return result
