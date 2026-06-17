import asyncio
import json
from typing import Any, Callable, Optional, List

import aiohttp
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from s2cpy.infrastructure.settings import get_global_config

MessageHandler = Callable[[dict], Any]


class PolymarketWS:
    """A small, resilient WebSocket client tailored for Polymarket realtime data.

    Design notes:
    - Default behavior creates its own aiohttp.ClientSession. You can inject a
      session for tests or advanced usage.
    - Uses a background reader loop + heartbeat loop. Handlers are scheduled
      as tasks so they don't block the reader.
    - Reconnects with exponential backoff (tenacity).

    [refer to](https://docs.polymarket.com/market-data/websocket/overview)

    """

    def __init__(
            self,
            url: str,
            session: Optional[aiohttp.ClientSession] = None,
            heartbeat_interval: float = 9.5,  # 要求是10s，9.5s保险
            reconnect_attempts: Optional[int] = 5,
    ):
        self.url = url
        self._external_session = session is not None
        self._session = session
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._heartbeat_interval = heartbeat_interval
        self._reconnect_attempts = reconnect_attempts
        self._recv_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        # Use a simple list of handlers (no topic/type routing)
        self._handlers: List[MessageHandler] = []
        self._closed = asyncio.Event()
        self._connected = asyncio.Event()
        self._commands_on_reconnect = []

    async def _ensure_session(self):
        if self._session is None:
            cfg = get_global_config()
            timeout = aiohttp.ClientTimeout(total=None)
            # do not set proxy here; ws_connect supports proxy argument if needed
            self._session = aiohttp.ClientSession(timeout=timeout)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential_jitter(initial=0.1, max=10))
    async def _connect_once(self):
        await self._ensure_session()
        logger.info(f"WS connecting to {self.url}")
        # aiohttp's ws_connect supports heartbeat param
        cfg = get_global_config()
        proxy = cfg.proxy_url if getattr(cfg, "proxy_url", None) else None
        self._ws = await self._session.ws_connect(self.url, heartbeat=self._heartbeat_interval, proxy=proxy)

    async def connect(self):
        """Connect (with retries)."""
        if self._closed.is_set():
            self._closed.clear()

        try:
            await self._connect_once()
            logger.info(f"websocket connected to {self.url} successfully")
        except Exception as e:
            logger.exception(f"initial connect failed,err is {e}")
            raise

        self._connected.set()
        self._recv_task = asyncio.create_task(self._reader_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _reader_loop(self):
        try:
            assert self._ws is not None
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_text(msg.data)
                elif msg.type == aiohttp.WSMsgType.PING:
                    logger.debug("ws ping")
                elif msg.type == aiohttp.WSMsgType.PONG:
                    logger.debug("ws pong")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error("ws error %s", self._ws.exception())
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("ws reader exception")
        finally:
            self._connected.clear()
            if not self._closed.is_set():
                logger.info("ws disconnected, attempting reconnect")
                await self._reconnect_loop()

    async def _handle_text(self, data: str):
        try:
            payload = json.loads(data)
        except Exception:
            logger.exception("invalid ws json")
            return

        # Dispatch payload to all registered handlers. We no longer route by
        # `topic` and simply deliver every message to every handler.
        handlers = list(self._handlers)
        for h in handlers:
            asyncio.create_task(self._maybe_call(h, payload))

    async def _maybe_call(self, handler, payload):
        try:
            res = handler(payload)
            if asyncio.iscoroutine(res):
                await res
        except Exception:
            logger.exception("ws handler raised")

    async def _heartbeat_loop(self):
        while not self._closed.is_set() and self._ws is not None and not self._ws.closed:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                await self._ws.ping()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("heartbeat failed")
                break

    async def send(self, obj: Any, send_on_reconnection: bool = True):
        if not self._ws or self._ws.closed:
            raise RuntimeError("ws not connected")
        data = obj if isinstance(obj, str) else json.dumps(obj)
        await self._ws.send_str(data)
        if send_on_reconnection:
            self._commands_on_reconnect.append(data)

    def register_handler(self, handler: MessageHandler):
        """Register a handler to receive all incoming messages.

        Previously handlers were keyed by topic/type. Handlers are now a
        flat list and will receive every message.
        """
        self._handlers.append(handler)

    async def close(self):
        self._closed.set()
        if self._recv_task:
            self._recv_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._external_session:
            await self._session.close()
        self._connected.clear()

    async def _reconnect_loop(self):
        attempts = 0
        max_attempts = self._reconnect_attempts if self._reconnect_attempts is not None else 999999
        while not self._closed.is_set() and attempts < max_attempts:
            attempts += 1
            try:
                await self._connect_once()
                self._connected.set()
                self._recv_task = asyncio.create_task(self._reader_loop())
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                for command in self._commands_on_reconnect:
                    logger.info(f"sending command {command} at reconnect")
                    await self._ws.send_str(command)
                logger.info(
                    f"reconnected after {attempts} attempts,handler num:{len(self._handlers)},resend command num:{len(self._commands_on_reconnect)}")
                return
            except Exception:
                logger.exception(f"reconnect attempt {attempts} failed", )
                await asyncio.sleep(min(2 ** attempts, 30))
