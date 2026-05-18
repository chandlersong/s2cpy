import os

os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7891'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7891'
import asyncio
import signal
from loguru import logger

from s2cpy.core.engine import SingleNodeLivingTradingEngine
from s2cpy.data_feeds.ploymarket_feed import CryptoRepeatDataFeed
from s2cpy.infrastructure.settings import get_global_config, setup_global_logging, PolyMarketRelayerAccount
from s2cpy.model.polymarke_core import PolyMarketMarketMakerAccount
from s2cpy.strategy.demo_strategies import PolyMarketRepeatDemoStrategy


async def main():
    """Run the engine and shut down gracefully on SIGINT/SIGTERM or on cancellation.

    The engine is started in a background task so we can await a stop event
    triggered by OS signals (Ctrl+C) or other code. When stopping we cancel
    the engine task which propagates CancelledError into the data feed
    coroutine; the data feed implements cleanup on cancellation.
    """
    config = get_global_config()
    setup_global_logging(config.log)

    account_list = config.accounts
    polymarket_account = account_list.get("main")
    if not isinstance(polymarket_account, PolyMarketRelayerAccount):
        logger.error("第一个账户必须是PolyMarketRelayerAccount")
        return

    engine = SingleNodeLivingTradingEngine()
    # 连接账户
    account = PolyMarketMarketMakerAccount(polymarket_account)
    await engine.register_account(account)

    repeat_data_feed = CryptoRepeatDataFeed()
    await engine.register_data_feed(repeat_data_feed)

    demo_strategy = PolyMarketRepeatDemoStrategy(account)
    await engine.register_strategy(demo_strategy)

    engine_task = asyncio.create_task(engine.start())

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    # Register signal handlers for graceful shutdown (works on macOS/Linux)
    try:
        # use a zero-arg callable so static checkers / event loop accept it
        loop.add_signal_handler(signal.SIGINT, lambda: stop_event.set())
        loop.add_signal_handler(signal.SIGTERM, lambda: stop_event.set())
    except NotImplementedError:
        # Some event loops (or Windows) may not support add_signal_handler from
        # non-main threads — fall back to KeyboardInterrupt handling below.
        logger.debug("signal handlers not available on this platform")

    logger.info("Engine started. Send SIGINT (Ctrl+C) or SIGTERM to stop.")

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        # If signal handlers aren't available, a Ctrl+C will raise here.
        logger.info("KeyboardInterrupt received, shutting down")
        stop_event.set()

    logger.info("Shutting down engine...")
    engine_task.cancel()
    try:
        await engine_task
    except asyncio.CancelledError:
        logger.info("Engine task cancelled")


if __name__ == '__main__':
    asyncio.run(main())
