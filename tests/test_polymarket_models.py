import datetime

from s2cpy.model.polymarket_option import HitPriceBinaryOption, TOKEN_YES, TOKEN_NO


def test_reach_yes_parsing():
    slug = "will-bitcoin-reach-80k-august-31-september-6-2026_Yes"
    ms = 1690000000000
    o = HitPriceBinaryOption(slug, ms)
    assert o.strike == 80000.0
    assert o.direction == TOKEN_YES
    assert o.is_above is True
    assert o.expiration == datetime.datetime.fromtimestamp(ms / 1000.0, tz=datetime.timezone.utc)


def test_reach_no_parsing():
    slug = "will-bitcoin-reach-80k-august-31-september-6-2026_No"
    ms = 1690000000000
    o = HitPriceBinaryOption(slug, ms)
    assert o.strike == 80000.0
    assert o.direction == TOKEN_NO
    assert o.is_above is True


def test_dip_yes_parsing():
    slug = "will-bitcoin-dip-to-76k-august-31-september-6-2026_Yes"
    ms = 1690000000000
    o = HitPriceBinaryOption(slug, ms)
    assert o.strike == 76000.0
    assert o.direction == TOKEN_YES
    assert o.is_above is False


def test_numeric_strike_without_k():
    slug = "will-bitcoin-reach-80000-august-31-september-6-2026_Yes"
    ms = 1690000000000
    o = HitPriceBinaryOption(slug, ms)
    assert o.strike == 80000.0
    assert o.is_above is True


def test_dip_strike_with_pt_decimal_notation():
    slug = "will-bitcoin-dip-to-77pt5k-in-september-2026-from-september-11_Yes"
    o = HitPriceBinaryOption(slug, 1690000000000)
    assert o.strike == 77500.0
    assert o.direction == TOKEN_YES
    assert o.is_above is False


def test_dip_numeric_strike_ignores_trailing_numeric_identifiers():
    slug = (
        "will-bitcoin-dip-to-30000-by-december-31-2026"
        "-971-191-116-343-999-758-299-813-237_No"
    )
    o = HitPriceBinaryOption(slug, 1690000000000)
    assert o.strike == 30000.0
    assert o.direction == TOKEN_NO
    assert o.is_above is False


def test_missing_parts_defaults():
    slug = "some-random-slug"
    ms = 1690000000000
    o = HitPriceBinaryOption(slug, ms)
    # fallback strike
    assert o.strike == 1
    # default direction -> NO because suffix absent
    assert o.direction == TOKEN_NO
    # default is_above True
    assert o.is_above is True


def test_intrinsic_yes_reach_hit():
    slug = "will-bitcoin-reach-80k-august-31-september-6-2026_Yes"
    ms = 1690000000000
    o = HitPriceBinaryOption(slug, ms)
    # 当价格等于或高于行权价，Yes 的内在价值为 1
    assert o.get_intrinsic_value(80000.0) == 1.0
    assert o.get_intrinsic_value(90000.0) == 1.0


def test_intrinsic_yes_reach_miss():
    slug = "will-bitcoin-reach-80k-august-31-september-6-2026_Yes"
    ms = 1690000000000
    o = HitPriceBinaryOption(slug, ms)
    assert o.get_intrinsic_value(79999.99) == 0.0


def test_intrinsic_no_reach():
    slug = "will-bitcoin-reach-80k-august-31-september-6-2026_No"
    ms = 1690000000000
    o = HitPriceBinaryOption(slug, ms)
    # reach 成立时 No 的价值为 0
    assert o.get_intrinsic_value(80000.0) == 0.0
    assert o.get_intrinsic_value(81000.0) == 0.0
    # reach 不成立时 No 的价值为 1
    assert o.get_intrinsic_value(70000.0) == 1.0


def test_intrinsic_yes_dip():
    slug = "will-bitcoin-dip-to-76k-august-31-september-6-2026_Yes"
    ms = 1690000000000
    o = HitPriceBinaryOption(slug, ms)
    # dip 成立（价格 <= strike）时 Yes 为 1
    assert o.get_intrinsic_value(76000.0) == 1.0
    assert o.get_intrinsic_value(70000.0) == 1.0
    # dip 不成立时为 0
    assert o.get_intrinsic_value(77000.0) == 0.0
