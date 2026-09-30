import datetime
from types import SimpleNamespace
from unittest.mock import patch

from s2cpy.core.postgresql_tools import PostgresqlInfo
from s2cpy.data_feeds.polymarket_option_feed import PolyMarketHistoryDataFeed


class FakeCursor:
    def __init__(self, rows, columns):
        self.rows = rows
        self.description = [SimpleNamespace(name=column) for column in columns]
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
    def __init__(self, rows, columns):
        self.cursor_instance = FakeCursor(rows, columns)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return self.cursor_instance


def make_feed():
    return PolyMarketHistoryDataFeed(
        PostgresqlInfo(
            user="postgres",
            password="password",
            host="localhost",
            port=5432,
            dbname="test",
        )
    )


def test_query_pm_price_returns_dataframe_from_direct_postgres_query():
    columns = [
        "assert_id",
        "assert_slug",
        "series_id",
        "series_slug",
        "market_slug",
        "start_ms",
        "end_ms",
        "price",
    ]
    rows = [(1, "will-bitcoin-reach-80k_yes", "10016", "series", "market", 10, 20, 0.7)]
    connection = FakeConnection(rows, columns)
    ts = datetime.datetime(2026, 9, 23, 12, 30)

    with patch(
        "s2cpy.data_feeds.polymarket_option_feed.psycopg.connect",
        return_value=connection,
    ) as connect:
        result = make_feed().query_pm_price(ts)

    connect.assert_called_once_with(
        host="localhost",
        port=5432,
        dbname="test",
        user="postgres",
        password="password",
    )
    assert connection.cursor_instance.executed[1] == ("2026-09-23 12:30:00",)
    assert result.columns.tolist() == columns
    assert result.iloc[0]["price"] == 0.7


def test_query_pm_instruments_at_maps_rows_to_binary_options():
    rows = [
        (1, "will-bitcoin-reach-80k_yes", "10016", "series", "market", 10, 1_800_000_000_000, "0.7")
    ]
    connection = FakeConnection(rows, [])

    with patch(
        "s2cpy.data_feeds.polymarket_option_feed.psycopg.connect",
        return_value=connection,
    ):
        options = make_feed().query_pm_instruments_at("2026-09-23 12:30:00")

    assert len(options) == 1
    assert options[0].asset_slug == "will-bitcoin-reach-80k_yes"
    assert options[0].latest_price == 0.7
    assert options[0].expiration.timestamp() == 1_800_000_000
