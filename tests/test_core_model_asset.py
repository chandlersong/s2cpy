import dataclasses

from s2cpy.model.core_model import Instrument

@dataclasses.dataclass(eq=False)
class MockInstrument(Instrument):
    pass

def test_asset_equality_and_hash():
    a1 = MockInstrument(identify="asset-1", external_id="ext-a", validate_before=None)
    a2 = MockInstrument(identify="asset-1", external_id="ext-b", validate_before=123456)

    # identity is based on id
    assert a1 == a2
    assert hash(a1) == hash(a2)

    # usable as dict key and in sets
    d = {a1: "value"}
    assert d[a2] == "value"

    s = {a1}
    assert a2 in s


def test_asset_inequality():
    a1 = MockInstrument(identify="asset-1")
    a3 = MockInstrument(identify="asset-3")
    assert a1 != a3

