import asyncio
import inspect
from typing import Callable, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger


async def periodic_runner(func: Callable[[], Any], interval_seconds: int = 600) -> None:
    """
    Generic periodic runner that calls `func` every `interval_seconds` seconds.

    - `func` can be a synchronous callable or an async callable that returns an awaitable
      when invoked (e.g. `lambda: obj.async_method()` which returns a coroutine).
    - The runner sleeps first, then invokes `func` (so callers can do an immediate
      action before scheduling the runner, matching previous semantics).
    - It catches and logs exceptions from `func` to avoid silent task exit.
    """
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                result = func()
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("Error in periodic runner")
    except asyncio.CancelledError:
        logger.info("Periodic runner cancelled")
        raise


_SCHEDULER: AsyncIOScheduler = None


def get_task_scheduler() -> AsyncIOScheduler:
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = AsyncIOScheduler()
        _SCHEDULER.start()
    return _SCHEDULER
