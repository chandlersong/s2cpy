from s2cpy.infrastructure.settings import get_global_config, setup_global_logging
from loguru import logger

async def test_config():
    config = get_global_config()
    setup_global_logging(config.log)
    logger.info(f"应用名称: {config.instance_name}")
    logger.info(f"运行环境: {config.environment}")
    logger.info(f"debug: {config.debug}")
    assert config.debug == True
    assert config.environment == "untest"
