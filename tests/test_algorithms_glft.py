import asyncio

import numpy as np
import pytest
from loguru import logger
from loguru import logger
from s2cpy.algorithms.glfts import generate_depths_from_min_tick, RollingGLFT
from s2cpy.infrastructure.time import get_unix_seconds_utc


def test_generate_depths_from_normal():
    min_ticker = 0.001
    res = generate_depths_from_min_tick(min_tick=min_ticker)
    logger.info(f"generate_depths_from_normal:{res}")


async def test_rolling_glft_update_lambdas():
    glft = RollingGLFT(min_tick=0.1, depth_size=3)
    logger.info(f"depth is :{glft._depths}")
    glft.append_order_books(0, 1)
    glft.append_trades(0, 1.01, 0, 1)
    glft.append_trades(0, 1.12, 0, 1)
    glft.append_trades(0, 1.11, 0, 1)
    glft.append_trades(0, 1.21, 0, 1)
    glft.append_trades(0, 1.31, 0, 1)
    actual = glft.count_hits()
    logger.info(f"depth is :{actual}")
    # use allclose to allow for tiny floating point differences
    assert np.allclose(np.array([0.01666667, 0.05      , 0.06666667]), actual)

@pytest.mark.manual
async def test_rolling_glft_calculate_a_k():
    glft = RollingGLFT(min_tick=0.1, depth_size=8, update_cycle_seconds=2, window_period_seconds=100)
    logger.info(f"depth is :{glft._depths}")
    glft.append_order_books(get_unix_seconds_utc(), 1)
    glft.append_trades(0, 1.01, 0, 1)
    glft.append_trades(0, 1.12, 0, 1)
    glft.append_trades(0, 1.11, 0, 1)
    glft.append_trades(0, 1.21, 0, 1)
    glft.append_trades(0, 1.31, 0, 1)

    await asyncio.sleep(2)

    glft.append_order_books(get_unix_seconds_utc(), 1.1)
    glft.append_trades(0, 1.01, 0, 1)
    glft.append_trades(0, 1.12, 0, 1)
    glft.append_trades(0, 1.11, 0, 1)
    glft.append_trades(0, 1.21, 0, 1)
    glft.append_trades(0, 1.31, 0, 1)

    await asyncio.sleep(2)

    glft.append_order_books(get_unix_seconds_utc(), 1.0)
    glft.append_trades(0, 1.01, 0, 1)
    glft.append_trades(0, 1.12, 0, 1)
    glft.append_trades(0, 1.11, 0, 1)
    glft.append_trades(0, 1.21, 0, 1)
    glft.append_trades(0, 1.31, 0, 1)

    await asyncio.sleep(2)
    glft.append_order_books(get_unix_seconds_utc(), 1.1)
    glft.append_trades(0, 1.01, 0, 1)
    glft.append_trades(0, 1.12, 0, 1)
    glft.append_trades(0, 1.11, 0, 1)
    glft.append_trades(0, 1.21, 0, 1)
    glft.append_trades(0, 1.31, 0, 1)
    await asyncio.sleep(2)

    glft.append_order_books(get_unix_seconds_utc(), 1.0)
    glft.append_trades(0, 1.01, 0, 1)
    glft.append_trades(0, 1.12, 0, 1)
    glft.append_trades(0, 1.11, 0, 1)
    glft.append_trades(0, 1.21, 0, 1)
    glft.append_trades(0, 1.31, 0, 1)
    await asyncio.sleep(2)

    logger.info(f"a is :{glft.a},k is :{glft.k}")
