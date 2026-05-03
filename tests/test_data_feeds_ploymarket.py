import asyncio

import pytest

from s2cpy.data_feeds.ploymarket_feed import CryptoRepeatDataFeed
from loguru import logger


@pytest.mark.manual
async def test_crypto_repeat_data_start_listen() -> None:
    repeat_data_feed = CryptoRepeatDataFeed()
    printer_handler = lambda data_name, content: logger.info(f"receive:{data_name}: {content}")
    repeat_data_feed.subscribe(printer_handler)
    await repeat_data_feed.start()
    await asyncio.sleep(30)
