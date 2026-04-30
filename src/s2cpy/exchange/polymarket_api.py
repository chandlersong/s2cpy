"""Async client for Polymarket Gamma API.

提供对常用 Gamma API 端点的异步封装方法，并使用 `src/s2cpy/exchange/polymarket_io.py`
中定义的 Pydantic 模型进行请求参数与响应的解析。

实现要点：
- 使用 `aiohttp.ClientSession` 发送 HTTP 请求
- 具有简单的指数退避重试（`_get_json`）以提高健壮性
- 提供常用方法：`get_markets`, `get_market_by_slug`, `get_events`, `get_tags`,
  `get_sports`, `get_market_prices`, `get_clob_market_info`, `get_rewards`
"""

from __future__ import annotations

from loguru import logger
from datetime import timedelta
from tenacity import retry, wait_random

from s2cpy.exchange.polymarket_io import PublicSearchRequest, PublicSearchResponse
from s2cpy.infrastructure.http_client import HttpClient


class GammaAPI:
    BASE_URL = "https://gamma-api.polymarket.com"

    def __init__(self):
        """初始化 GammaAPI 客户端。

        - `session`: 可选的外部 `aiohttp.ClientSession`，如果传入则不会由本实例关闭。
        - `timeout`: 单次请求超时时间（秒）
        - `max_retries`: 失败时最大重试次数（包含首次尝试）
        """
        self._http_client = HttpClient()

    @retry(wait=wait_random(min=timedelta(milliseconds=100), max=timedelta(milliseconds=200)))
    async def public_search(self, request: PublicSearchRequest, timeout: float = 30) -> PublicSearchResponse:
        session = await self._http_client.get_session()

        try:
            async with session.get(
                    f"{GammaAPI.BASE_URL}/public-search",
                    params=request.model_dump(exclude_none=True),
                    timeout=timeout,
            ) as resp:
                if resp.status == 200:
                    return PublicSearchResponse.parse_raw(await resp.text())
                else:
                    logger.error(f"public-search fail,status code: {resp.status}")
                    raise RuntimeError(f"public-search fail,status code: {resp.status}")
        except Exception as e:
            logger.error(e)
            raise e


__all__ = ["GammaAPI"]
