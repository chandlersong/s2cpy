import os

os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7891'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7891'
from pathlib import Path

from s2cpy.data_feeds.ploymarket_feed import SeriesHistoryDataFeed
from s2cpy.infrastructure.time import TimeInterval

from s2cpy.rpc.sync_server import HistorySyncServer
import asyncio

from s2cpy.infrastructure.settings import get_global_config, setup_global_logging
from loguru import logger


async def main():
    """
    ENV: sync
    series id:45,series slug:btc-multi-strikes-weekly
    series id:10151,series slug:bitcoin-hit-price-weekly
    series id:10041,series slug:bitcoin-neg-risk-weekly
    :return:
    """

    config = get_global_config()
    setup_global_logging(config.log)
    sync_config = config.sync_server
    sync_server = HistorySyncServer(cache_root=Path(sync_config.sync_cache_folder), port=sync_config.port)
    series_ids = ["45",
                  "10151",
                  "10041", ]
    data_feed = SeriesHistoryDataFeed(series_ids, interval=TimeInterval.OneHour)
    data_feed.subscribe(sync_server.handler_new_data)
    # await data_feed.start()
    await sync_server.start()
    while True:
        await asyncio.sleep(60 * 60)


if __name__ == '__main__':
    asyncio.run(main())
