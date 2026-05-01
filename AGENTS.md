# AGENTS（供 AI 代码代理使用）

本文件记录了 AI 代码代理在此仓库中立刻上手所需的简明、可执行信息。

快速检查清单（给代理的要点）
- 理解三个主要子系统：`infrastructure`（配置、HTTP 客户端、日志）、`exchange`（Polymarket Gamma API 客户端）和 `model`（Pydantic v2 的请求/响应模型）。
- 修改运行时行为时优先查看 `/src/s2cpy/infrastructure/settings.py` 和 `/src/s2cpy/infrastructure/http_client.py`。
- 新增 API 或编写测试时，优先使用 `/src/s2cpy/model/polymarket_io.py` 中的 Pydantic 模型，以及 `/src/s2cpy/exchange/polymarket_api.py` 中的 `GammaAPI` 客户端。
- 默认 pytest 会排除标记为 `manual` 的测试（见 `pyproject.toml`），CI/本地测试使用的环境为 `untest`。

仓库总体结构与核心职责（big picture）
- `src/s2cpy/infrastructure`
  - `settings.py`：全局配置加载器与单例。它会从 `config/` 目录按优先级合并多个 TOML 配置文件（例如 `config.toml`、`config.<ENV>.toml`、`secrets.toml`），并支持由环境变量 `CONFIG_PATH` 覆盖。使用 `get_global_config()` 获取进程级配置实例；在测试中可用 `reset_global_config()` 重新初始化。
  - `http_client.py`：基于 `aiohttp.ClientSession` 的懒加载单例封装。通过 `await HttpClient.get_session()` 获取可复用会话；长期运行或测试结束时调用 `await HttpClient.close()` 清理。
- `src/s2cpy/model/polymarket_io.py`
  - 包含对 `/public-search` 的请求（`PublicSearchRequest`）和响应（`PublicSearchResponse`）的 Pydantic v2 模型，以及 Market、Event、Series 等大量嵌套域模型。模型常用 `model_dump`、`model_validate`、`Field`、`field_validator` 等模式。
  - 提供 `PublicSearchRequest.build(...)` 工厂方法，用于在 IDE 中避免 Pydantic 可选字段导致的误报（tests/示例广泛使用）。
- `src/s2cpy/exchange/polymarket_api.py`
  - `GammaAPI`：一个小型异步客户端，使用 `HttpClient.get_session()` 发起请求并用 Pydantic 模型解析响应（调用示例见 tests）。
  - 内置简单重试（`tenacity.wait_random`），响应解析使用 `PublicSearchResponse.parse_raw` 或模型提供的辅助方法。

重要的开发者工作流（命令与环境）
- 运行单元测试（推荐）:
  - 仓库在 `pyproject.toml` 中配置了 pytest（启用 async 测试，默认排除 `manual`）。在项目根目录运行：

    PYTHONPATH=src pytest

  - 若要包含手工测试（标记 `@pytest.mark.manual`），运行：

    PYTHONPATH=src pytest -m manual

  - 可选：安装为可编辑包以获得类似已安装包的导入行为：

    python -m pip install -e .
    pytest

- 配置与环境提示：
  - 配置加载按优先级合并 `config/` 中的 TOML：`config.toml` <- `config.<ENV>.toml` <- `secrets.toml`。测试默认使用的 ENV 为 `untest`（见 `pyproject.toml` 的 env 配置）。
  - 可通过设定 `CONFIG_PATH=/path/to/file.toml` 来覆盖要加载的配置文件。
  - 日志通过 `setup_gobal_logging(config.log)` 初始化（参见 `tests/test_settings.py`），项目使用 `loguru`。

项目特定约定与模式
- Pydantic v2 的使用要点：
  - 构造 GET 请求参数时使用 `.model_dump(exclude_none=True)`（见 `GammaAPI.public_search`）。
  - 解析响应可使用 `.model_validate(...)` 或 `.parse_raw(...)`。`PublicSearchResponse.from_api_response` 已处理 API 常见的多种返回形态（直接数组、`data` 包裹、或包含命名键的对象）。
- 单例与生命周期管理：
  - `get_global_config()` 返回进程级 `AppSettings` 单例；测试需要改变配置时请调用 `reset_global_config()`。
  - `HttpClient.get_session()` 是懒加载的 `aiohttp.ClientSession` 单例；在脚本退出或测试 teardown 时应调用 `await HttpClient.close()` 避免资源警告。
- 测试标记约定：
  - 手工/网络相关测试用 `@pytest.mark.manual` 标记，CI 与默认本地运行会排除此类测试。若变更涉及网络行为，请保留 `manual` 标签或用可控的 mock 替代真实请求。

集成点与外部依赖
- 外部 HTTP：Polymarket Gamma API（https://gamma-api.polymarket.com），由 `GammaAPI.public_search` 使用。
- 配置驱动的网络行为：`AppSettings.proxy_url` 会注入到 `aiohttp.ClientSession` 的 `proxy` 字段（见 `http_client.py`），因此代理与网络相关设置通过 `config/*.toml` 控制。
- 关键第三方库（见 `pyproject.toml`）：`aiohttp`、`loguru`、`pydantic`（v2）、`pydantic-settings`、`tenacity`。测试依赖 `pytest-asyncio`。

可直接复用的代码示例（来自仓库）
- 构造请求并调用 API（tests 中的模式）：

  from s2cpy.model.polymarket_io import PublicSearchRequest
  from s2cpy.exchange.polymarket_api import GammaAPI

  params = PublicSearchRequest.build(q="btc")
  gamma = GammaAPI()
  resp = await gamma.public_search(params)

- 获取全局配置并初始化日志（tests 示例）：

  cfg = get_global_config()
  setup_gobal_logging(cfg.log)

代码中需注意的点（Notes & gotchas）
- 配置加载器会打印所加载的文件并做深度合并；如果你只想依赖环境变量，请通过 `CONFIG_PATH` 指向一个单一文件以避免多文件合并干扰。
- `PublicSearchResponse.from_api_response` 与 `PublicSearchRequest.build` 用于统一 API 的多种返回/构造习惯，优先使用这些 helper 而非手写 dict。
- 本项目要求 Python >= 3.13（见 `pyproject.toml`），在执行或运行测试前请确保运行环境符合此要求。

优先阅读的文件（建议顺序）
- `src/s2cpy/infrastructure/settings.py`（配置与日志）
- `src/s2cpy/infrastructure/http_client.py`（网络会话生命周期）
- `src/s2cpy/model/polymarket_io.py`（域模型与响应解析）
- `src/s2cpy/exchange/polymarket_api.py`（客户端调用示例）
- `pyproject.toml`（测试运行配置、依赖、pytest 标记）

如果你更改了网络行为或配置加载，请同时更新 `tests/`：优先添加可确定性的单元测试（对 `HttpClient.get_session()` 做 mock），而不是开启真实网络的手工测试。

---

Generated on: 2026-05-01

