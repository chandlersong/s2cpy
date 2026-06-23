import queue
import time
from concurrent import futures
from pathlib import Path
from typing import List, Iterator, Tuple

import grpc
from collections import Counter
from apscheduler.triggers.cron import CronTrigger

from s2cpy.generated import history_data_pb2, history_data_pb2_grpc
from s2cpy.infrastructure.async_tools import get_task_scheduler
from s2cpy.infrastructure.time import now_unix_ms_utc
from s2cpy.model.core_model import LiveData
from s2cpy.model.polymarke_core import PolyMarketHistoryPriceLiveData, PolyMarketHistoryPricePK
from loguru import logger


class HistorySyncServer(history_data_pb2_grpc.SyncServerServicer):
    """
    这是一个同步程序。
    这里我想要这样。
    1. 在handler接收数据。
    2. 在启动的时候，启动一个线程，坚持一下

    TODO：改进列表
    1. 检测cache大小。如果cache大于某个值，比如5G。则删除id最小的文件。
    """

    def __init__(self, cache_root: Path | None = None, port: int = 50051):

        if cache_root is None:
            cache_root = Path("/app/cache/polymarket_history_cache")
        self._cache_root = cache_root / "polymarket_history_cache"
        if not self._cache_root.exists():
            self._cache_root.mkdir(parents=True, exist_ok=True)

        self._cache = history_data_pb2.PolyMarketHistoryList()
        self._cache_queue = queue.Queue()
        self.port = port

    def handler_new_data(self, _, data: LiveData):
        if isinstance(data, PolyMarketHistoryPriceLiveData):
            history = history_data_pb2.PolyMarketHistory()
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
        timestamp = now_unix_ms_utc()
        cache = self._cache
        cache.timestamp = timestamp
        self._cache = history_data_pb2.PolyMarketHistoryList()
        cache_entry = cache.SerializeToString()
        # Check for duplicate timestamps inside the PolyMarketHistoryList
        try:
            pk_list = [PolyMarketHistoryPricePK(asset_id=h.asset_id, timestamp=h.timestamp,slug=h.asset_slug) for h in
                       cache.history_list]
            counts = Counter(pk_list)
            duplicates = [(pk, cnt) for pk, cnt in counts.items() if cnt > 1]
            for pk, cnt in duplicates:
                logger.warning(f"find duplicate history {pk}, counts {cnt}")
        except Exception:
            # Defensive: if the proto structure is unexpected, don't fail persist
            logger.exception("persist_cache: failed to check duplicate timestamps")
        cache_file_name = self._cache_root / f"{timestamp}.bin"
        with open(cache_file_name, "wb") as f:
            f.write(cache_entry)
        logger.trace(f"保存缓存文件到{cache_file_name}")
        # notify listeners (sync) that a new cache file is available
        try:
            self._cache_queue.put(cache)
        except Exception:
            logger.debug("无法将timestamp放入_cache_queue")

    def sync(self, request_iterator, context):
        """
        1. 接收第一条消息，判断是不是initial。如果不是，报错，切断连接
        2. 如果是，则获取local_max_timestamp，给客户端推送相关的信息。并记录所有的timestamp
        3. 推送完成后，监听 self._cache_queue，检测timestamp。如果没有的timestamp。则推向客户端
        4. 同时监听是否有其他命令

        # 客户端和服务器端连接的的基本规则。
        ## V1
        1. server和client端，暂时为一对一。以后再考虑一对多。
        2. 客户端的数据由客户端保证完整。如果漏了数据以后再考虑。
            - 例如：下面场景。
                1. 在T1时间断开。然后T2连接。
                2. T1和T2相差很多。致使服务器删除一部分数据。那么这些数据删了，也就是删了。

        :param request_iterator:
        :param context:
        :return:
        """
        # First message must be `initial` per protocol
        try:
            first_msg = next(request_iterator)
        except StopIteration:
            return

        if not first_msg.HasField("initial"):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "first message must be initial")

        initial_command = first_msg.initial
        logger.info(f"收到初始化命令，初始数据的timestamp:{initial_command.local_max_timestamp}")

        # get iterator and timestamps list, send existing history
        iter_msgs, _timestamps = self.push_local_history(initial_command.local_max_timestamp)
        for m in iter_msgs:
            yield m

        # spawn a thread to consume client messages (no processing as requested)
        def _consume_requests():
            """
            线做为一个place holder。等到有initial的其他命令后在考虑
            :return:
            """
            try:
                for _ in request_iterator:
                    pass
            except Exception:
                pass

        reader = futures.ThreadPoolExecutor(max_workers=1)
        reader_future = reader.submit(_consume_requests)
        max_timestamp = max(_timestamps)
        try:
            # listen on self._cache_queue for new timestamps and send them
            while context.is_active():
                try:
                    history_list = self._cache_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if history_list is None:
                    continue

                if not isinstance(history_list, history_data_pb2.PolyMarketHistoryList):
                    logger.warning(f"收到不明类型的数据,类型{type(history_list)},数据:{history_list}")
                    continue

                if history_list.timestamp > max_timestamp:
                    yield history_list
                    time.sleep(2)
        finally:
            try:
                reader_future.cancel()
            except Exception:
                pass

    def push_local_history(self, initial_timestamp: int) -> Tuple[Iterator[history_data_pb2.ServerMessage], List[int]]:
        """Return (iterator, timestamps_list). Iterator yields ServerMessage objects."""
        timestamps = self.find_history_list(initial_timestamp)
        logger.info(f"需要像客户端推送{len(timestamps)}条记录")

        def _iter():
            for timestamp in timestamps:
                cache_file_name = self._cache_root / f"{timestamp}.bin"
                with open(cache_file_name, "rb") as f:
                    cache_entry = f.read()
                history_list = history_data_pb2.PolyMarketHistoryList()
                history_list.ParseFromString(cache_entry)
                yield history_data_pb2.ServerMessage(polymarket_history=history_list)

        return _iter(), timestamps

    def find_history_list(self, n: int = 0) -> List[int]:
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
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        history_data_pb2_grpc.add_SyncServerServicer_to_server(
            self, server
        )

        server.add_insecure_port(f'[::]:{self.port}')
        logger.info(f"服务器启动在 [::]:{self.port}")
        server.start()
        server.wait_for_termination()


if __name__ == '__main__':
    HistorySyncServer()
