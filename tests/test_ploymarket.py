from s2cpy.exchange.polymarket_tools import convert_markets_2_assets
from s2cpy.model.polymarket_io import Market


def test_convert_markets_2_assets():
    market = Market(id="test")
    market.endDate = "2026-06-09T18:15:00Z"
    market.clobTokenIds = ["token1", "token2"]
    market.slug = "testmarket"
    market.outcomes = ["yes", "no"]
    assets = convert_markets_2_assets(market)
    assert len(assets) == 2
    token1 = assets["token1"]
    token2 = assets["token2"]

    assert token1.identify == "testmarket-yes"
    assert token2.identify == "testmarket-no"

    assert token1.external_id == "token1"
    assert token2.external_id == "token2"

    assert token1.validate_before == 1781028900
    assert token2.validate_before == 1781028900

    assert token1.extra_info['market'] == market
    assert token2.extra_info['market'] == market
