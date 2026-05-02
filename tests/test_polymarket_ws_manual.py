import asyncio
import json

import pytest
from loguru import logger
from s2cpy.exchange.polymarket_ws import PolymarketWS


@pytest.mark.manual
async def test_ws_echo_manual():
    """Manual test: connect to a public echo server and verify send/receive.

    Note: marked manual because it uses real network and an external server.
    """
    url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"  # public echo service (manual only)
    ws = PolymarketWS(url, reconnect_attempts=2)

    received = asyncio.Queue()

    async def on_msg(msg):
        await received.put(msg)

    ws.register_handler("default", on_msg)

    await ws.connect()
    logger.info(f"WS connected to {url}")
    sub = {
        "assets_ids": [
            "26871611942842159660578538115087561842096772208823332594549095712451566897786"
        ],
        "type": "market",
        "initial_dump": False,
        "level": 2,
        "custom_feature_enabled": True
    }
    await ws.send(sub)

    # wait for a message from the server (timeout to avoid hanging)
    try:
        msg = await asyncio.wait_for(received.get(), timeout=10)
        logger.info(f"msg: {msg}")
        assert isinstance(msg, dict)
    finally:
        await ws.close()
