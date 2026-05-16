import asyncio
import os

os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7891'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7891'

from s2cpy.model.polymarke_core import PolyMarketMarketMakerAccount
import pytest
from loguru import logger

from s2cpy.data_feeds.ploymarket_feed import CryptoRepeatDataFeed
from s2cpy.exchange.polymarket_api import GammaAPI
from s2cpy.exchange.polymarket_ws import PolymarketWS
from s2cpy.infrastructure.settings import get_global_config, setup_global_logging, PolyMarketRelayerAccount
from s2cpy.model.polymarket_io import PublicSearchRequest, EventGetBySlugRequest, SeriesGetRequest, EventGetByIdRequest, \
    ListMarketsRequest


@pytest.mark.manual
async def test_list_markets():
    request = ListMarketsRequest.build(
        clob_token_ids=['69324317355037271422943965141382095011871956039434394956830818206664869608517'])
    cfg = get_global_config()
    setup_global_logging(cfg.log)
    api = GammaAPI()
    markets = await api.list_markets(request)
    for market in markets:
        logger.info(market)


@pytest.mark.manual
async def test_public_search_api():
    """
    GET /public-search
    主要是对一些publish search
    :return:
    """
    logger.debug(f"test_manual_case")
    # 初始化全局配置并启用日志（避免未使用导入的警告）
    cfg = get_global_config()
    setup_global_logging(cfg.log)

    # 使用 build() 工厂方法以避免 IDE 将 pydantic __init__ 误判为需要填写全部字段
    params = PublicSearchRequest.build(q="btc")
    gamma_api = GammaAPI()
    response = await gamma_api.public_search(params)
    if response.events is None:
        logger.error("事件为空")
        return
    logger.info(f"events num : {len(response.events)}")
    page_info = response.pagination
    logger.info(f"pagination info has more : {page_info.hasMore},totol results:{page_info.totalResults}")
    for event in response.events:
        logger.info(f"event id: {event.id}, slug: {event.slug}")
        event_series = event.series
        if event_series is None:
            logger.info(f"{event.slug} has no series")
        else:
            for series in event_series:
                logger.info(f"series id: {series.id}, slug: {series.slug}")


@pytest.mark.manual
async def test_event_slug_to_series_id():
    """
    通过event的slug，去确定合适的series id。然后再根据series id获得最新的event
    :return:
    """
    logger.debug(f"test_event_slug_to_series_id")
    gamma_api = GammaAPI()
    event_slug = "btc-updown-15m-1777468500"
    event_slug_request = EventGetBySlugRequest.build(slug=event_slug)
    event = await gamma_api.get_event_by_slug(event_slug_request)
    markets = event.markets
    if markets is not None:
        for market in markets:
            logger.info(f"market id: {market.id}, slug: {market.slug},market token id:{market.clobTokenIds}")

    event_series = event.series
    if event_series is None:
        logger.info(f"{event_slug_request.slug} has no series")
    else:
        for series in event_series:
            logger.info(f"series id: {series.id}, slug: {series.slug}")
            series_request = SeriesGetRequest.build(id=series.id)
            series_response = await gamma_api.get_series_by_id(series_request)
            logger.info(f"series id: {series_response.id}, slug: {series_response.slug}")
            series_events = series_response.events if series_response.events is not None else []
            series_events = [event for event in series_events if event.active is True and event.closed is False]
            series_events = sorted(series_events, key=lambda e: e.startTime)
            logger.info(f"series events num : {len(series_events)}")
            # logger.info(f"new_events : {len(series_events)}")
            latest_event = series_events[0]
            logger.info(f"latest_event slug is {latest_event.slug},start_time: {latest_event.startTime}")
            latest_market = latest_event.markets
            logger.info(f"lastest market from series is {latest_market}")

            event_id_request = EventGetByIdRequest.build(id=latest_event.id)
            event_id_response = await gamma_api.get_event_by_id(event_id_request)
            market_id_from_research = event_id_response.markets
            logger.info(
                f"latest_event slug is {market_id_from_research[0].slug},start_time: {market_id_from_research[0].clobTokenIds}")
            logger.info(f"market  num {len(market_id_from_research)}")


@pytest.mark.manual
async def test_crypto_repeat_data_start_listen() -> None:
    repeat_data_feed = CryptoRepeatDataFeed()
    printer_handler = lambda data_name, content: logger.info(f"receive:{data_name}: {content}")
    repeat_data_feed.subscribe(printer_handler)
    await repeat_data_feed.start()
    await asyncio.sleep(60)


@pytest.mark.manual
async def test_market_make_account() -> None:
    """
    应该是一个最简单的实盘启动
    :return:
    """

    logger.debug(f"test_market_make_account")
    config = get_global_config()
    setup_global_logging(config.log)
    account = PolyMarketMarketMakerAccount(config.get_default_account())
    await account.sync_account_position()
    asset_dict = account.asset_dict
    logger.info(f"账户有{len(asset_dict)}类资产")
    for asset, position in asset_dict.items():
        logger.info(f"asset: {asset}, position: {position}")
    open_orders = account.open_orders
    for order_id, open_order in open_orders.items():
        logger.info(f"order_id: {order_id}, open_order: {open_order}")

    await asyncio.sleep(60 * 60)


@pytest.mark.manual
async def test_ws_echo_manual():
    """Manual test: connect to a public echo server and verify send/receive.

    Note: marked manual because it uses real network and an external server.
    """
    url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"  # public echo service (manual only)
    ws = PolymarketWS(url, reconnect_attempts=2)

    received = asyncio.Queue()

    async def on_msg(msg):
        await received.put(msg)

    ws.register_handler("default", on_msg)

    await ws.connect()
    logger.info(f"WS connected to {url}")
    sub = {
        "assets_ids": [
            "26871611942842159660578538115087561842096772208823332594549095712451566897786"
        ],
        "type": "market",
        "initial_dump": False,
        "level": 2,
        "custom_feature_enabled": True
    }
    await ws.send(sub)

    # wait for a message from the server (timeout to avoid hanging)
    try:
        msg = await asyncio.wait_for(received.get(), timeout=10)
        logger.info(f"msg: {msg}")
        assert isinstance(msg, dict)
    finally:
        await ws.close()
