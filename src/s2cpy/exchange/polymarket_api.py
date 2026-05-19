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

from datetime import timedelta
from typing import List

from tenacity import retry, wait_random, stop_after_attempt

from s2cpy.infrastructure.http_client import HttpClient
from s2cpy.model.polymarket_io import (
    PublicSearchRequest,
    PublicSearchResponse,
    Series,
    Event,
    Market,
    SeriesGetRequest,
    EventGetBySlugRequest,
    EventGetByIdRequest,
    MarketGetBySlugRequest,
    MarketGetByIdRequest,
    PositionsResponse,
    parse_positions_response, parse_market_response, ListMarketsRequest, parse_to_json,
)


class RestfulAPI:
    BASE_URL = "https://gamma-api.polymarket.com"
    DATA_URL = "https://data-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"

    def __init__(self):
        """初始化 GammaAPI 客户端。

        - `session`: 可选的外部 `aiohttp.ClientSession`，如果传入则不会由本实例关闭。
        - `timeout`: 单次请求超时时间（秒）
        - `max_retries`: 失败时最大重试次数（包含首次尝试）
        """
        self._http_client = HttpClient()

    # ---------------------
    # Simple resource getters
    # ---------------------

    async def get_and_parse(self, url: str, parser, params: dict | None = None, timeout: float = 30):
        """Public helper to perform GET and parse JSON using provided parser.

        This is intentionally public to allow callers to reuse the client's session
        and status handling. `params` should be a dict of query parameters.
        """
        session = await self._http_client.get_session()

        async with session.get(url, params=params, timeout=timeout) as resp:
            if resp.status == 200:
                # If caller passed a Pydantic model class, prefer parsing from
                # the raw JSON text to avoid an intermediate dict when the
                # model provides `model_validate_json`.
                if isinstance(parser, type) and hasattr(parser, "model_validate_json"):
                    text = await resp.text()
                    return parser.model_validate_json(text)

                # If parser is a Pydantic model that only supports dict parsing
                # use resp.json()
                if isinstance(parser, type) and hasattr(parser, "model_validate"):
                    data = await resp.json()
                    return parser.model_validate(data)

                # Fallback: existing behavior for parser functions / callables
                data = await resp.json()
                return parser(data)
            elif resp.status == 404:
                raise PolymarketNotFoundError(f"Not found: {url}")
            elif 500 <= resp.status < 600:
                raise PolymarketServerError(f"Server error {resp.status}: {url}")
            else:
                raise PolymarketAPIError(f"Unexpected status {resp.status} for {url}")

    @retry(stop=stop_after_attempt(5),
           wait=wait_random(min=timedelta(milliseconds=100), max=timedelta(milliseconds=200)))
    async def public_search(self, request: PublicSearchRequest, timeout: float = 30) -> PublicSearchResponse:
        url = f"{RestfulAPI.BASE_URL}/public-search"
        params = request.model_dump(exclude_none=True)
        params.pop("id", None)
        # Pass the Pydantic model class directly so get_and_parse can
        # construct the model (via model_validate_json / model_validate).
        return await self.get_and_parse(url, PublicSearchResponse, params=params, timeout=timeout)

    async def list_markets(self, request: ListMarketsRequest, timeout: float = 30) -> List[Market]:
        """Helper to find a market by its CLOB token ID.

        Since Gamma API doesn't provide a direct endpoint for this, we perform a search
        and filter results. This is less efficient than a direct lookup, so should be
        used judiciously (e.g., caching results if doing multiple lookups).
        """

        url = f"{RestfulAPI.BASE_URL}/markets"
        params = request.model_dump(exclude_none=True)
        # Use the helper parser which accepts arrays, wrapped {data: [...]},
        # or single-market payloads and returns either Market or list[Market].
        resp = await self.get_and_parse(url, parse_market_response, params=params, timeout=timeout)
        # normalize to List[Market]
        if isinstance(resp, list):
            return resp
        if isinstance(resp, Market):
            return [resp]
        # Fallback: if parser returned something unexpected, raise
        raise PolymarketAPIError("Unexpected response shape from /markets")

    async def get_series_by_id(self, request: SeriesGetRequest, timeout: float = 30) -> "Series":
        """GET /series/{id} -> Series

        Raises PolymarketNotFoundError on 404, PolymarketServerError on 5xx.
        """
        url = f"{RestfulAPI.BASE_URL}/{f"series/{request.id}".lstrip('/')}"
        params = request.model_dump(exclude_none=True)
        params.pop("id", None)
        return await self.get_and_parse(url, Series, params=params, timeout=timeout)

    async def get_event_by_slug(self, request: EventGetBySlugRequest, timeout: float = 30) -> Event:
        """GET /events/{slug} -> Event"""
        url = f"{RestfulAPI.BASE_URL}/{f"events/slug/{request.slug}".lstrip('/')}"
        params = request.model_dump(exclude_none=True)
        params.pop("slug", None)
        return await self.get_and_parse(url, Event, params=params, timeout=timeout)

    async def get_market_by_slug(self, request: MarketGetBySlugRequest, timeout: float = 30) -> "Market":
        """GET /markets/{slug} -> Market"""
        url = f"{RestfulAPI.BASE_URL}/{f"markets/slug/{request.slug}".lstrip('/')}"
        params = request.model_dump(exclude_none=True)
        params.pop("slug", None)
        return await self.get_and_parse(url, Market, params=params, timeout=timeout)

    async def get_market_by_id(self, request: MarketGetByIdRequest, timeout: float = 30) -> "Market":
        """GET /markets/{id} -> Market"""
        url = f"{RestfulAPI.BASE_URL}/{f"markets/{request.id}".lstrip('/')}"
        params = request.model_dump(exclude_none=True)
        params.pop("id", None)
        return await self.get_and_parse(url, Market, params=params, timeout=timeout)

    async def get_event_by_id(self, request: EventGetByIdRequest, timeout: float = 30) -> "Event":
        """GET /events/{id} -> Event"""
        url = f"{RestfulAPI.BASE_URL}/{f"events/{request.id}".lstrip('/')}"
        params = request.model_dump(exclude_none=True)
        params.pop("id", None)
        return await self.get_and_parse(url, Event, params=params, timeout=timeout)

    async def positions(self, user: str | None = None, size_threshold: int | None = 1,
                        limit: int | None = 100, offset: int | None = None,
                        timeout: float = 30) -> PositionsResponse:
        """GET https://data-api.polymarket.com/positions

        Only exposes the following query parameters to callers: `user`, `sizeThreshold`, `limit`, `offset`.
        Returns a `PositionsResponse` parsed from the response. Raises existing Polymarket* errors on non-200.
        """
        url = f"{self.DATA_URL}/positions"
        params = {"user": user, "sizeThreshold": size_threshold, "limit": limit, "offset": offset}
        # remove None values
        params = {k: v for k, v in params.items() if v is not None}
        # Use parse_positions_response helper so we can accept array or wrapped formats
        return await self.get_and_parse(url, parse_positions_response, params=params, timeout=timeout)

    async def mini_ticker(self, token_id,
                          timeout: float = 30) -> float:
        """GET https://data-api.polymarket.com/positions

        Only exposes the following query parameters to callers: `user`, `sizeThreshold`, `limit`, `offset`.
        Returns a `PositionsResponse` parsed from the response. Raises existing Polymarket* errors on non-200.
        """
        url = f"{self.CLOB_URL}/tick-size"
        params = {"token_id": token_id}
        # remove None values
        params = {k: v for k, v in params.items() if v is not None}
        # Use parse_positions_response helper so we can accept array or wrapped formats
        response: dict = await self.get_and_parse(url, parse_to_json, params=params, timeout=timeout)
        value: str = response['minimum_tick_size']
        return float(value)


# -----------------
# Exception classes
# -----------------


class PolymarketAPIError(RuntimeError):
    """Base exception for Polymarket API client errors."""


class PolymarketNotFoundError(PolymarketAPIError):
    """Raised when API returns HTTP 404."""


class PolymarketServerError(PolymarketAPIError):
    """Raised when API returns 5xx server error."""


@retry(wait=wait_random(min=timedelta(milliseconds=100), max=timedelta(milliseconds=200)))
async def _noop_retry_wrapper():
    """A small wrapper to enable using retry on per-method bases if needed.

    (Kept as placeholder — individual getters currently do not use tenacity.)
    """
    return None


__all__ = ["RestfulAPI", "PolymarketAPIError", "PolymarketNotFoundError", "PolymarketServerError"]
