from s2cpy.infrastructure.time import now_unix_ms_utc
from loguru import logger


def test_now_unix_ms_utc() -> None:
    """
    傻逼的单元测试
    :return:
    """
    logger.info(now_unix_ms_utc())
    assert now_unix_ms_utc() == now_unix_ms_utc()

