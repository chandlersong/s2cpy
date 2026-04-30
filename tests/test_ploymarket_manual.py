import aiohttp
import pytest
from loguru import logger

from s2cpy.infrastructure.settings import get_global_config, setup_gobal_logging


@pytest.mark.manual
async def test_manual_case():
    logger.debug(f"test_manual_case")


