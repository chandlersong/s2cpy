# AGENTS: How to be productive in this repository

This file gives an AI coding agent a concise, practical orientation to the s2cpy codebase so you can be productive quickly.

- Quick architecture (big picture)
  - Source root: /Users/chandlersong/quant/s2cpy/src/s2cpy
  - Major components:
    - core: /src/s2cpy/core/engine.py — orchestration, run-loop and engine-level logic. Responsibilities: process event loops, manage feed/strategy lifecycle, coordinate message routing and global state.
    - data_feeds: /src/s2cpy/data_feeds/ploymarket_feed.py — ingest Polymarket feed messages. Responsibilities: adapt external feeds into internal events, perform validation/normalization, handle reconnection/backpressure.
    - exchange: /src/s2cpy/exchange/* — REST/WS clients (polymarket_api.py, polymarket_ws.py). Responsibilities: API layer that talks to external trading services — place/cancel orders, query REST endpoints, maintain WS subscriptions, surface retries/rate-limits and ACK/response semantics. (交易所交互的 API 层)
    - infrastructure: /src/s2cpy/infrastructure/* — async helpers, http client, settings loader. Responsibilities: shared primitives (http client, async utilities, time helpers), settings and environment loading, retry/backoff strategies and instrumentation.
    - model: /src/s2cpy/model/* — domain models and IO translators (polymarket_io.py, polymarket_ws_io.py). Responsibilities: pydantic domain schemas, conversion between raw JSON and internal typed objects, serialization for persistence/REST.
    - algorithms / strategy: algorithm implementations and strategies under /src/s2cpy/algorithms and /src/s2cpy/strategy. Responsibilities: encapsulate trading/decision logic, stateless algorithm modules and stateful strategy implementations that plug into the engine.

- Data flow / boundaries (typical path)
  - External Polymarket WS/REST -> exchange/polymarket_ws.py or exchange/polymarket_api.py
  - -> data_feeds/ploymarket_feed.py (adapter) -> model.polymarket_ws_io / polymarket_io (translate raw payloads -> domain objects)
  - -> core/engine.py and strategy modules (decision logic) -> exchange (place orders, calls)
  - Use these files as canonical examples when tracing flows: /src/s2cpy/exchange/polymarket_ws.py, /src/s2cpy/data_feeds/ploymarket_feed.py, /src/s2cpy/core/engine.py

- Project-specific conventions to follow
  - Packaging: pyproject.toml at project root defines dependencies and test config. See /Users/chandlersong/quant/s2cpy/pyproject.toml — tests run with pytest and pytest-asyncio.
  - Typing: package ships type hints (py.typed in /src/s2cpy). Prefer typed APIs when available (pydantic models used in /src/s2cpy/model).
  - Async-first: many modules are async (infrastructure/async_tools.py, exchange/polymarket_ws.py, infrastructure/http_client.py). Prefer async implementations and use asyncio-safe patterns.
  - Config: TOML files in /Users/chandlersong/quant/s2cpy/config (*.toml). Settings loader: /src/s2cpy/infrastructure/settings.py — read these for environment-specific behavior.
  - Tests: most tests live in /Users/chandlersong/quant/s2cpy/tests. Manual tests are marked with pytest marker "manual"; default addopts excludes them.

- Developer workflows & commands
  - Install deps & build: pyproject.toml uses uv_build (see [build-system] in pyproject.toml).
  - Run tests: from project root run `pytest` (pyproject.toml provides defaults: -m "not manual"). For async tests pytest-asyncio is configured.
  - Run example scripts: `python examples/single_server_live_example.py` or `python examples/GLFT_example.py` from repo root.
  - Debugging: follow the message flow (WS -> data_feeds -> model -> engine) and add log calls (loguru is a dependency). The code uses blinker for eventing in places — search for blinker usage when tracing signals.

- Integration points and external deps
  - Polymarket REST/WebSocket — adapters in /src/s2cpy/exchange (polymarket_api.py, polymarket_ws.py)
  - py-clob-client-v2 is listed in pyproject.toml (line 17) — used for order placement or market IO
  - Network code uses aiohttp (line 11)

- Patterns and examples to copy
  - Settings pattern: read /src/s2cpy/infrastructure/settings.py to see how Pydantic/Pydantic-Settings is used with config/*.toml.
  - IO translation: /src/s2cpy/model/polymarket_ws_io.py and /src/s2cpy/model/polymarket_io.py show how raw JSON payloads map into domain models.
  - Engine entrypoints: /src/s2cpy/core/engine.py demonstrates lifecycle and how feeds + strategies plug into the engine.

- What agents should do first (checklist)
  1. Read /Users/chandlersong/quant/s2cpy/pyproject.toml to understand deps and test config.
  2. Trace a message: open /src/s2cpy/exchange/polymarket_ws.py -> /src/s2cpy/data_feeds/ploymarket_feed.py -> /src/s2cpy/model/*.py -> /src/s2cpy/core/engine.py
  3. Run `pytest -q` from repo root; skip manual tests if needed via markers (default already excludes manual).
  4. Use examples in /Users/chandlersong/quant/s2cpy/examples to run live/demo flows.

- Quick references
  - pyproject: /Users/chandlersong/quant/s2cpy/pyproject.toml
  - settings loader: /Users/chandlersong/quant/s2cpy/src/s2cpy/infrastructure/settings.py
  - engine: /Users/chandlersong/quant/s2cpy/src/s2cpy/core/engine.py
  - websocket adapter: /Users/chandlersong/quant/s2cpy/src/s2cpy/exchange/polymarket_ws.py
  - feed adapter: /Users/chandlersong/quant/s2cpy/src/s2cpy/data_feeds/ploymarket_feed.py

Keep this file short — use references above when you need more context.
