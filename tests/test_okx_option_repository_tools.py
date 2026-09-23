import datetime
from unittest.mock import patch

from s2cpy.core.postgresql_tools import PostgresqlInfo
from s2cpy.data_feeds.okx_local_feed import OkxOptionRepository
from s2cpy.model.core_model import OptionType


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, params):
        self.executed = (query, params)

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.cursor_instance = FakeCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return self.cursor_instance


def make_repository():
    return OkxOptionRepository(
        PostgresqlInfo(
            user="postgres",
            password="secret",
            host="localhost",
            port=5432,
            dbname="test",
        )
    )


def test_query_option_kline_maps_database_rows_to_options():
    ts = datetime.datetime(2026, 9, 23, tzinfo=datetime.timezone.utc)
    rows = [
        ("BTC-USD-260925-73000-C", 179, "BTC"),
        ("ETH-USD-260926-2500-P", 180, "ETH"),
    ]
    connection = FakeConnection(rows)

    with patch(
        "s2cpy.core.postgresql_tools.psycopg.connect",
        return_value=connection,
    ) as connect:
        options = make_repository().query_option_kline(ts)

    connect.assert_called_once_with(
        host="localhost",
        port=5432,
        dbname="test",
        user="postgres",
        password="secret",
    )
    assert connection.cursor_instance.executed[1] == (ts,)
    assert [(option.identify, option.strike, option.multiplier) for option in options] == [
        ("BTC-USD-260925-73000-C", 73000.0, 0.01),
        ("ETH-USD-260926-2500-P", 2500.0, 0.1),
    ]
    assert options[0].base_ccy == "BTC"
    assert options[0].option_type is OptionType.Call
    assert options[1].option_type is OptionType.Put
    assert options[0].mini_ticker_size == 1
    assert options[0].validate_before == 179


def test_query_option_kline_returns_empty_list_when_no_rows():
    connection = FakeConnection([])

    with patch(
        "s2cpy.core.postgresql_tools.psycopg.connect",
        return_value=connection,
    ):
        assert make_repository().query_option_kline("2026-09-23T00:00:00Z") == []


def test_parse_inst_identify_returns_all_five_values():
    assert OkxOptionRepository.parse_inst_identify(
        "BTC-USD-260925-73000-C"
    ) == ("BTC", "USD", "260925", 73000.0, OptionType.Call)

    assert OkxOptionRepository.parse_inst_identify(
        "ETH-USD-260926-2500-P"
    ) == ("ETH", "USD", "260926", 2500.0, OptionType.Put)


def test_parse_inst_identify_rejects_invalid_identifier():
    invalid_identifiers = (
        "BTC-USD-260925-C",
        "BTC-USD-260925-not-a-number-C",
        "BTC-USD-260925-73000-X",
    )

    for identifier in invalid_identifiers:
        try:
            OkxOptionRepository.parse_inst_identify(identifier)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected ValueError for {identifier!r}")
