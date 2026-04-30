import pytest
from loguru import logger

from s2cpy.exchange.polymarket_api import GammaAPI
from s2cpy.exchange.polymarket_io import PublicSearchRequest, PublicSearchResponse
from s2cpy.infrastructure.settings import get_global_config, setup_gobal_logging


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
