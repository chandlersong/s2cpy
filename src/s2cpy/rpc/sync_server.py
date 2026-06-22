from pathlib import Path
from typing import List

from apscheduler.triggers.cron import CronTrigger

from s2cpy.generated import history_data_pb2, history_data_pb2_grpc
from s2cpy.infrastructure.async_tools import get_task_scheduler
from s2cpy.infrastructure.time import now_unix_ms_utc
from s2cpy.model.core_model import LiveData
from s2cpy.model.polymarke_core import PolyMarketHistoryPriceLiveData
from loguru import logger


class HistorySyncServer(history_data_pb2_grpc.SyncServer):
    """
    这是一个同步程序。
    这里我想要这样。
    1. 在handler接收数据。
    2. 在启动的时候，启动一个线程，坚持一下

    TODO：改进列表
    1. 检测cache大小。如果cache大于某个值，比如5G。则删除id最小的文件。
    """

    def __init__(self, cache_root: Path | None = None):
        if cache_root is None:
            cache_root = Path("/app/cache/polymarket_history_cache")
        self._cache_root = cache_root / "polymarket_history_cache"
        if not self._cache_root.exists():
            self._cache_root.mkdir(parents=True, exist_ok=True)

        self._cache = history_data_pb2.PolyMarketHistoryList()

    def handler_new_data(self, topic, data: LiveData):
        if isinstance(data, PolyMarketHistoryPriceLiveData):
            history = history_data_pb2.PolyMarketHistory()
            history.table = data.table
            history.series_id = data.series_id
            history.series_slug = data.series_slug
            history.event_id = data.event_id
            history.event_slug = data.event_slug
            history.market_id = data.market_id
            history.market_slug = data.market_slug
            history.asset_id = data.asset_id
            history.asset_slug = data.asset_slug
            history.timestamp = data.timestamp
            history.price = data.price
            self._cache.history_list.append(history)
            if len(self._cache.history_list) > 100:
                self.persist_cache()

    def persist_cache(self):
        if len(self._cache.history_list) == 0:
            return
        cache_entry = self._cache.SerializeToString()
        cache_file_name = self._cache_root / f"{now_unix_ms_utc()}.bin"
        with open(cache_file_name, "wb") as f:
            f.write(cache_entry)
        logger.trace(f"保存缓存文件到{cache_file_name}")
        self._cache = history_data_pb2.PolyMarketHistoryList()

    def find_history_list(self, n: int = 0)->List[int]:
        """
        在_cache_root的目录中，找出大于n所有的文件。
        例如，我输入的是5.，然后_cahce_root下面，有1.bin,5.bin,6.bin,8.bin.9.bin这五个文件
        怎么返回[6,8,9]
        # 介绍。
        在_cache_root中，所有的文件，都睡时间戳.bin。类似于1.bin这类
        :param n:
        :return:
        """
        results: List[int] = []
        if not self._cache_root.exists():
            return results

        for p in self._cache_root.iterdir():
            # only consider regular files
            if not p.is_file():
                continue
            name = p.name
            # accept files that match the pattern "<digits>.bin"
            if not name.endswith(".bin"):
                continue
            # split off the extension safely
            parts = name.rsplit('.', 1)
            if len(parts) != 2:
                continue
            base, ext = parts
            if ext != 'bin':
                continue
            try:
                ts = int(base)
            except ValueError:
                # skip files that don't have an integer timestamp as the base name
                continue
            if ts > n:
                results.append(ts)

        results.sort()
        return results

    async def start(self):
        scheduler = get_task_scheduler()
        scheduler.add_job(
            self.persist_cache,
            trigger=CronTrigger.from_crontab('*/10 * * * *'),  # 秒 分 时 日 月 周
            id="HistorySyncServerPersistCache",
            replace_existing=True
        )


if __name__ == '__main__':
    HistorySyncServer()
