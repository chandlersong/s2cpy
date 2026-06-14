from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from py_clob_client_v2 import Side

from s2cpy.infrastructure.settings import get_global_config
from s2cpy.model.core_model import Position
from s2cpy.model.polymarke_core import PolyLiquidityProviderAccount, AssertInfo


def create_mock_account(mock_clob_cls) -> PolyLiquidityProviderAccount:
    fake_clob = MagicMock()
    fake_clob.create_or_derive_api_key.return_value = MagicMock(api_key="k", api_secret="s", api_passphrase="p")
    mock_clob_cls.return_value = fake_clob

    cfg = get_global_config()
    account_config = cfg.get_default_account()
    return PolyLiquidityProviderAccount(account_config)


@patch('s2cpy.model.polymarke_core.asserts_by_market_id', new_callable=AsyncMock)
@patch("s2cpy.model.polymarke_core.ClobClient")
async def test_new_trade_complete(mock_clob_cls, mock_assets):
    """
    如果成交的订单，不在资产列表中。那么就更新资产列表
    - 仓位新建一个asset的
    - 其包含所有的asset等信息。
    :param mock_api: mock调用API的代码
    :param mock_clob_cls: mockclob的api
    :return:
    """
    mock_asset = MagicMock()
    mock_assets.return_value = {"1234567890": mock_asset}
    subscribe = MagicMock()
    account = create_mock_account(mock_clob_cls)
    data = {
        "status": "CONFIRMED",
        "asset_id": "1234567890",
        "market": "abc",
        "size": "10",
        "price": "8",
        "maker_orders": [
            {
                "order_id": "0xff354cd7ca7539dfa9c28d90943ab5779a4eac34b9b37a757d7b32bdfb11790b",
            }
        ]
    }
    account._handler = subscribe
    account._asset = {}
    await account.on_web_socket_trade(data)

    assets = account._asset

    assert "1234567890" in assets
    info = assets["1234567890"]
    assert info is not None
    assert info.asset == mock_asset
    position = info.position
    assert position.latest_price == 8
    assert position.quantity == 10
    assert position.avg_price == 8

    subscribe.assert_called_once()
    # Inspect the arguments passed to the subscribe handler
    call_args = subscribe.call_args
    assert call_args is not None
    topic_arg, live_data_arg = call_args[0]
    # topic should be the trade_confirm topic for this account
    assert topic_arg == account.get_topic("trade_confirm")
    # live_data should carry the asset and original data
    from s2cpy.model.core_model import LiveData
    assert isinstance(live_data_arg, LiveData)
    assert live_data_arg.asset == mock_asset
    assert live_data_arg.data == data


@patch("s2cpy.model.polymarke_core.ClobClient")
async def test_trade_buy(mock_clob_cls):
    """
      成交了一笔买入的订单。
    - 仓位该改变。
    - 发送消息
    :param mock_api: mock调用API的代码
    :param mock_clob_cls: mockclob的api
    :return:
    """
    subscribe = MagicMock()
    account = create_mock_account(mock_clob_cls)
    data = {
        "status": "CONFIRMED",
        "asset_id": "1234567890",
        "market": "abc",
        "size": "15",
        "price": "8",
        "side": "BUY",
        "maker_orders": [
            {
                "order_id": "0xff354cd7ca7539dfa9c28d90943ab5779a4eac34b9b37a757d7b32bdfb11790b",
            }
        ]
    }
    account._handler = subscribe
    position = Position(latest_price=1, quantity=5, avg_price=5)
    asset = MagicMock()
    account._asset = {"1234567890": AssertInfo(asset=asset, position=position)}
    await account.on_web_socket_trade(data)

    assets = account._asset

    assert "1234567890" in assets
    info = assets["1234567890"]
    assert info is not None
    position = info.position
    assert position.latest_price == 8
    assert position.quantity == 20
    assert position.avg_price == 7.25

    subscribe.assert_called_once()
    # Verify subscribe was called with expected topic and LiveData
    call_args = subscribe.call_args
    assert call_args is not None
    topic_arg, live_data_arg = call_args[0]
    assert topic_arg == account.get_topic("trade_confirm")
    from s2cpy.model.core_model import LiveData
    assert isinstance(live_data_arg, LiveData)
    assert live_data_arg.asset == asset
    assert live_data_arg.data == data


@patch("s2cpy.model.polymarke_core.ClobClient")
async def test_trade_sell(mock_clob_cls):
    """
    成交了一笔卖出的订单。
    - 仓位该改变。
    - 发送消息
    :param mock_clob_cls: mockclob的api
    :return:
    """
    subscribe = MagicMock()
    account = create_mock_account(mock_clob_cls)
    data = {
        "status": "CONFIRMED",
        "asset_id": "1234567890",
        "market": "abc",
        "size": "5",
        "price": "8",
        "side": "SELL",
        "maker_orders": [
            {
                "order_id": "0xff354cd7ca7539dfa9c28d90943ab5779a4eac34b9b37a757d7b32bdfb11790b",
            }
        ]
    }
    account._handler = subscribe
    position = Position(latest_price=1, quantity=20, avg_price=5)
    asset = MagicMock()
    account._asset = {"1234567890": AssertInfo(asset=asset, position=position)}
    await account.on_web_socket_trade(data)

    assets = account._asset

    assert "1234567890" in assets
    info = assets["1234567890"]
    assert info is not None
    position = info.position
    assert position.latest_price == 8
    assert position.quantity == 15
    assert position.avg_price == 4

    subscribe.assert_called_once()
    # Verify subscribe was called with expected topic and LiveData
    call_args = subscribe.call_args
    assert call_args is not None
    topic_arg, live_data_arg = call_args[0]
    assert topic_arg == account.get_topic("trade_confirm")
    from s2cpy.model.core_model import LiveData
    assert isinstance(live_data_arg, LiveData)
    assert live_data_arg.asset == asset
    assert live_data_arg.data == data


@patch("s2cpy.model.polymarke_core.ClobClient")
async def test_trade_fail(mock_clob_cls):
    """
    如果订单失败，
    1. 不改变仓位
    2. 改变balance
    :param mock_clob_cls: mockclob的api
    :return:
    """
    subscribe = MagicMock()
    account = create_mock_account(mock_clob_cls)
    data = {
        "status": "FAILED",
        "asset_id": "1234567890",
        "market": "abc",
        "size": "5",
        "price": "8",
        "side": "SELL",
        "maker_orders": [
            {
                "order_id": "0xff354cd7ca7539dfa9c28d90943ab5779a4eac34b9b37a757d7b32bdfb11790b",
            }
        ]
    }
    account._handler = subscribe
    account._usdc_balance = 10
    position = Position(latest_price=1, quantity=20, avg_price=5)
    asset = MagicMock()
    account._asset = {"1234567890": AssertInfo(asset=asset, position=position)}
    await account.on_web_socket_trade(data)

    assets = account._asset

    assert "1234567890" in assets
    info = assets["1234567890"]
    assert info is not None
    position = info.position
    assert position.latest_price == 1
    assert position.quantity == 20
    assert position.avg_price == 5
    assert account._usdc_balance == 50
    subscribe.assert_called_once()
    # Verify subscribe was called with expected topic and LiveData
    call_args = subscribe.call_args
    assert call_args is not None
    topic_arg, live_data_arg = call_args[0]
    assert topic_arg == account.get_topic("trade_failed")
    from s2cpy.model.core_model import LiveData
    assert isinstance(live_data_arg, LiveData)
    assert live_data_arg.asset == asset
    assert live_data_arg.data == data


@patch("s2cpy.model.polymarke_core.ClobClient")
async def test_order_update_sell(mock_clob_cls):
    """
    更新order需要做的逻辑
    1. 改变仓位。为交易的部分
    2. 发送给下游
    :param mock_clob_cls: mockclob的api
    :return:
    """
    subscribe = MagicMock()
    account = create_mock_account(mock_clob_cls)
    data = {
        "id": "abc",
        "type": "UPDATE",
        "asset_id": "1234567890",
        "market": "abc",
        "price": 8,
        "original_size": "10",
        "size_matched": "5",
        "side": "SELL",
        "maker_orders": [
            {
                "order_id": "0xff354cd7ca7539dfa9c28d90943ab5779a4eac34b9b37a757d7b32bdfb11790b",
            }
        ]
    }
    account._handler = subscribe
    account._usdc_balance = 10
    position = Position(latest_price=1, quantity=20, avg_price=5)
    asset = MagicMock()
    account._asset = {"1234567890": AssertInfo(asset=asset, position=position)}
    account.on_web_socket_order(data)

    assets = account._asset

    assert "1234567890" in assets
    info = assets["1234567890"]
    assert info is not None
    position = info.position
    assert position.latest_price == 8
    assert position.quantity == 15
    assert position.avg_price == 4
    assert account._usdc_balance == 10
    subscribe.assert_called_once()
    # Verify subscribe was called with expected topic and LiveData
    call_args = subscribe.call_args
    assert call_args is not None
    topic_arg, live_data_arg = call_args[0]
    assert topic_arg == account.get_topic("order_update")
    from s2cpy.model.core_model import LiveData
    assert isinstance(live_data_arg, LiveData)
    assert live_data_arg.asset == asset
    assert live_data_arg.data == data


@patch("s2cpy.model.polymarke_core.ClobClient")
async def test_order_update_buy(mock_clob_cls):
    """
    更新order需要做的逻辑
    1. 改变仓位。为交易的部分
    2. 发送给下游
    :param mock_clob_cls: mockclob的api
    :return:
    """
    subscribe = MagicMock()
    account = create_mock_account(mock_clob_cls)
    data = {
        "id": "abc",
        "type": "UPDATE",
        "asset_id": "1234567890",
        "market": "abc",
        "price": 8,
        "original_size": "10",
        "size_matched": "5",
        "side": "BUY",
        "maker_orders": [
            {
                "order_id": "0xff354cd7ca7539dfa9c28d90943ab5779a4eac34b9b37a757d7b32bdfb11790b",
            }
        ]
    }
    account._handler = subscribe
    account._usdc_balance = 10
    position = Position(latest_price=1, quantity=20, avg_price=5)
    asset = MagicMock()
    account._asset = {"1234567890": AssertInfo(asset=asset, position=position)}
    account.on_web_socket_order(data)

    assets = account._asset

    assert "1234567890" in assets
    info = assets["1234567890"]
    assert info is not None
    position = info.position
    assert position.latest_price == 8
    assert position.quantity == 25
    assert position.avg_price == 5.6
    assert account._usdc_balance == 10
    subscribe.assert_called_once()
    # Verify subscribe was called with expected topic and LiveData
    call_args = subscribe.call_args
    assert call_args is not None
    topic_arg, live_data_arg = call_args[0]
    assert topic_arg == account.get_topic("order_update")
    from s2cpy.model.core_model import LiveData
    assert isinstance(live_data_arg, LiveData)
    assert live_data_arg.asset == asset
    assert live_data_arg.data == data


@patch("s2cpy.model.polymarke_core.ClobClient")
async def test_order_cancel(mock_clob_cls):
    """
    更新order 取消逻辑
    1. 改变仓位。为交易的部分
    2. 发送给下游
    :param mock_clob_cls: mockclob的api
    :return:
    """
    subscribe = MagicMock()
    account = create_mock_account(mock_clob_cls)
    data = {
        "id": "abc",
        "type": "CANCELLATION",
        "asset_id": "1234567890",
        "market": "abc",
        "price": 8,
        "original_size": "10",
        "size_matched": "5",
        "side": "BUY",
        "maker_orders": [
            {
                "order_id": "0xff354cd7ca7539dfa9c28d90943ab5779a4eac34b9b37a757d7b32bdfb11790b",
            }
        ],
    }
    account._handler = subscribe
    account._usdc_balance = 10
    position = Position(latest_price=1, quantity=20, avg_price=5)
    asset = MagicMock()
    account._asset = {"1234567890": AssertInfo(asset=asset, position=position)}
    account.on_web_socket_order(data)

    assets = account._asset

    assert "1234567890" in assets
    info = assets["1234567890"]
    assert info is not None
    position = info.position
    assert position.latest_price == 1
    assert position.quantity == 20
    assert position.avg_price == 5
    assert account._usdc_balance == 50
    subscribe.assert_called_once()
    # Verify subscribe was called with expected topic and LiveData
    call_args = subscribe.call_args
    assert call_args is not None
    topic_arg, live_data_arg = call_args[0]
    assert topic_arg == account.get_topic("order_cancelled")
    from s2cpy.model.core_model import LiveData
    assert isinstance(live_data_arg, LiveData)
    assert live_data_arg.asset == asset
    assert live_data_arg.data == data


@patch("s2cpy.model.polymarke_core.ClobClient")
async def test_create_order_buy(mock_clob_cls):
    """
    更新order 取消逻辑
    1. 要改变usdc_balance
    2. 发送给下游
    :param mock_clob_cls: mockclob的api
    :return:
    """
    account = create_mock_account(mock_clob_cls)
    account._usdc_balance = 10
    asset_info = MagicMock()
    account._asset = {"1234567890": asset_info}
    market = MagicMock()
    market.orderPriceMinTickSize = "0.1"
    arg = {
        "token_id": "1234567890",
        "price": 0.006,
        "size": 5,
        "side": Side.BUY,
        "market": market,
    }

    account.create_order(**arg)

    assert account._usdc_balance == 9.97


@patch("s2cpy.model.polymarke_core.convert_markets_2_assets")
@patch("s2cpy.model.polymarke_core.ClobClient")
async def test_create_order_no_asset(mock_clob_cls, mock_convert_markets_2_assets):
    """
    更新order 取消逻辑
    1. 要改变usdc_balance
    2. 发送给下游
    :param mock_clob_cls: mockclob的api
    :return:
    """
    asset = MagicMock()
    mock_convert_markets_2_assets.return_value = {"1234567890": asset}
    account = create_mock_account(mock_clob_cls)
    account._usdc_balance = 10
    market = MagicMock()
    market.orderPriceMinTickSize = "0.1"
    arg = {
        "token_id": "1234567890",
        "price": 0.006,
        "size": 5,
        "side": Side.SELL,
        "market": market,
    }

    account.create_order(**arg)

    assert account._usdc_balance == 10
    assert "1234567890" in account._asset


@patch("s2cpy.model.polymarke_core.ClobClient")
async def test_create_order_exception_flow(mock_clob_cls):
    """
    更新order 取消逻辑
    1. 要改变usdc_balance
    2. 发送给下游
    :param mock_clob_cls: mockclob的api
    :return:
    """
    account = create_mock_account(mock_clob_cls)
    account._usdc_balance = 10
    asset_info = MagicMock()
    account._asset = {"1234567890": asset_info}
    with pytest.raises(ValueError, match="参数中没有market"):
        arg = {
            "token_id": "1234567890",
            "price": 0.006,
            "size": 5,
            "side": Side.BUY,
        }
        account.create_order(**arg)


@patch("s2cpy.model.polymarke_core.ClobClient")
async def test_orders_by_asset_empty(mock_clob_cls):
    """
    orders_by_asset should return an empty dict when there are no open orders.
    """
    account = create_mock_account(mock_clob_cls)
    account._open_orders = {}
    grouped = account.orders_group_by_asset
    assert grouped == {}

    with pytest.raises(ValueError, match="market test, orderPriceMinTickSize 0.2 is not valid"):
        market = MagicMock()
        market.orderPriceMinTickSize = "0.2"
        market.slug = "test"
        arg = {
            "token_id": "1234567890",
            "price": 0.006,
            "size": 5,
            "side": Side.BUY,
            "market": market,
        }
        account.create_order(**arg)


@patch("s2cpy.model.polymarke_core.ClobClient")
async def test_orders_by_asset_grouping(mock_clob_cls):
    """
    Ensure orders_by_asset groups open orders by their assert_id correctly.
    """
    account = create_mock_account(mock_clob_cls)
    from s2cpy.model.core_model import Order

    o1 = Order(id="o1", asset_id="a1", side=1, quantity=5, quantity_match=0, price=1.0, status="OPEN")
    o2 = Order(id="o2", asset_id="a1", side=-1, quantity=2, quantity_match=0, price=2.0, status="OPEN")
    o3 = Order(id="o3", asset_id="a2", side=1, quantity=1, quantity_match=0, price=3.0, status="OPEN")

    account._open_orders = {"o1": o1, "o2": o2, "o3": o3}

    grouped = account.orders_group_by_asset

    assert set(grouped.keys()) == {"a1", "a2"}
    assert len(grouped["a1"]) == 2
    assert o1 in grouped["a1"] and o2 in grouped["a1"]
    assert len(grouped["a2"]) == 1 and grouped["a2"][0] is o3
