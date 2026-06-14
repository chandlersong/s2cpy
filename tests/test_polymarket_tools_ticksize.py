import pytest

from s2cpy.exchange.polymarket_tools import is_valid_tick_size


def test_literal_tick_size_valid_invalid():
    # For the real installed py_clob_client_v2 TickSize (Literal), common value should be valid
    assert is_valid_tick_size("0.1") is True
    assert is_valid_tick_size("0.2") is False


def test_enum_tick_size(monkeypatch):
    from enum import Enum

    class E(Enum):
        A = "0.1"
        B = "0.01"

    monkeypatch.setattr('s2cpy.exchange.polymarket_tools.TickSize', E)

    assert is_valid_tick_size("0.01") is True
    assert is_valid_tick_size("0.2") is False


def test_constants_class(monkeypatch):
    class C:
        TEN = "0.1"
        HUNDRED = "0.01"

    monkeypatch.setattr('s2cpy.exchange.polymarket_tools.TickSize', C)

    # Value matching
    assert is_valid_tick_size("0.1") is True
    # Name matching (the helper also accepts uppercase attribute names)
    assert is_valid_tick_size("TEN") is True
    assert is_valid_tick_size("0.2") is False


def test_constructable_class(monkeypatch):
    # A class that accepts construction with valid values and raises otherwise
    class ConstructableTickSize:
        def __init__(self, v):
            if v not in ("0.1", "0.01"):
                raise ValueError("invalid")

    monkeypatch.setattr('s2cpy.exchange.polymarket_tools.TickSize', ConstructableTickSize)

    assert is_valid_tick_size("0.01") is True
    assert is_valid_tick_size("0.2") is False

