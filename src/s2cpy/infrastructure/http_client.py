import aiohttp
import asyncio
from typing import Optional

from s2cpy.infrastructure.settings import get_global_config


class HttpClient:
    _session: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        """懒加载 + 单例模式"""
        if cls._session is None or cls._session.closed:
            # 可以在这里统一配置超时、代理、headers 等
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            config = get_global_config()
            cls._session = aiohttp.ClientSession(
                timeout=timeout,
                proxy=config.proxy_url,  # 如果需要全局代理
            )
        return cls._session

    @classmethod
    async def close(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None
