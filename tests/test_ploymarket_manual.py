import pytest
from loguru import logger

from s2cpy.exchange.polymarket_api import GammaAPI
from s2cpy.infrastructure.settings import get_global_config, setup_gobal_logging
from s2cpy.model.polymarket_io import PublicSearchRequest, EventGetBySlugRequest, SeriesGetRequest


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
    setup_gobal_logging(cfg.log)

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


