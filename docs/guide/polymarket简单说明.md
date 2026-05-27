# GLFT 策略示例使用指南

## 概述

本文档介绍了如何使用 `GLFT_example.py` 运行 Polymarket 上的 GLFT（Gamma Limit FOK Trading）策略。GLFT
是一个高级的市场做市策略，它基于订单簿数据和成交数据来计算最优的报价。

## 核心概念

### GLFT 策略

- **GLFT** 代表 Gamma Limit FOK Trading
- 这是一个根据市场微观结构（订单簿和成交指标）动态计算最优买卖价的策略
- 使用 60 分钟的滚动窗口来分析市场数据
- 每 3 秒计算一次最优价格

## 策略修改
在写一个策略当中，其实就解决三个问题。
1. 数据种类和来源。可以是K线，账户信息等
2. 根据这些数据做决策。
3. 根据决策，生成交易指令。
下面，就依据以上三点做具体介绍。 就[GLFT_example.py](../../examples/GLFT_example.py)

### 数据源
在做的时候，数据源按照不同纬度，可以做不同的分类。
比如按照来源分，一类是市场信息，比如说K线，订单簿等。另一类是账户信息，比如说持仓，余额等。
按照需求来分析，一类是有实时性的需求，比如说价格，交易等。一类是没有实时性的需求，比如说账户信息，持仓，因为这些你不做交易，就不会改变。

所以这里采用基本是订阅为主的数据交互模式。

#### 发布数据
下面以OneMarketDataFeed来介绍一下发布数据的过程。
1. 在supported_data_list方法，申明自己要发布信息的列表。例子中：是market_slug.type的类型
      - 建议唯一性标识+类型的方式。方便区分
2. 在subscribe中，添加订阅者。订阅者是一个回调函数，接收数据后，进行处理。例子中，是一个lambda函数，直接调用策略的on_market_data方法。
      - 原则上，具体的订阅发布，由engine去实现。这里只是作为一个钩子来实现。大部分情况，可以照抄。

#### 账户信息
账户信息的获取，原则上也是订阅发布的模式。因为账户信息的变化，可能会触发一些策略的决策。
以PolyMarketMarketMakerAccount来说明。
1. 其也会发布信息。基本逻辑和流程，可以参考上面的数据源的发布信息。策略订阅也是一样。
2. 一些信息，作为属性存在。策略当中直接调用。

### 策略决策
以PolyMarketGLFTStrategy例子来说明一下策略决策的过程。
其实策略无非两件事情。
1. 接收数据：
   - 实时数据，通过data_list这个方法，来返回自己需要数据的列表。这里的列表，要和datafeed中的在supported_data_list相对应。
   - 静态数据，比如说账户信息，这里通过持有account对象来获取。
2. 决策：
    - 实时决策。就是接收到数据后，进行决策。例子中，是在on_change方法中，接收数据后，进行决策。
    - 周期决策。理论自己来定义。在例子，我启动了一个后台的线程。具体参考_run_periodic
   
### 下单指令
因为下单的方式和手段可能会千差万别。所以我提供了一个统一的接口。
具体可以参照[core_model.py](../../src/s2cpy/model/core_model.py)中的Account类。定一个了3个方法
然后具体实现可以惨遭[polymarke_core.py](../../src/s2cpy/model/polymarke_core.py)中的PolyMarketMarketMakerAccount方法
调用相应方法即可

### 主要组件

1. **SingleNodeLivingTradingEngine** - 核心交易引擎
    - 管理事件循环和消息路由
    - 协调数据源、账户和策略的生命周期

2. **PolyMarketMarketMakerAccount** - 交易账户
    - 代表 Polymarket 上的交易账户
    - 负责维护账户信息和交易权限

3. **CryptoRepeatDataFeed** - 数据源
    - 订阅 Polymarket 的实时数据
    - 提供订单簿和成交数据

4. **PolyMarketGLFTStrategy** - GLFT 策略实现
    - 接收市场数据
    - 计算最优的买卖价
    - 生成交易信号

## 前置要求

### 1. 环境配置

需要在配置文件中设置交易账户信息。配置文件位于 `config/config.toml`：

```toml
instance_name = "s2cpy-instance"
proxy_url = "http://127.0.0.1:7891"

[log]
level = "INFO"

[accounts]
type = "polymarket_relayer_account"  # 账户类型，现在是 polymarket_relayer_account
name = "test"             # 打印在日志中
private_key = ""          # 放在 secrets.toml 更安全
funder_address = ""
deposit_wallet = ""
```

### 2. 账户配置

在配置文件中添加所需的 Polymarket 账户：
格式为accounts.账户名。例如下面就是账户main

```toml
[accounts.main]
# Polymarket Relayer 账户信息
# 需要提供有效的 API 密钥和其他认证信息
```

### 3. 环境变量

### profile设置

默认读取的config.toml文件，如果需要读取其他配置文件，可以设置环境变量：
如下配置，则会读取config下面的config.dev.toml中的配置信息
1. dev的配置文件，会覆盖掉config.toml中的配置

```bash
export ENV=dev
```

#### 代理设置

如果需要通过代理访问网络，可以设置代理环境变量：

```bash
export ENV=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890

```

> 注意：代码中已包含代理配置示例。如不需要，可将其注释掉。


### 4. 安装依赖

从项目根目录运行：

```bash
pip install -e .
```

或使用 uv：

```bash
uv sync
```


### 2. 启动示例

所有例子，都要

从项目根目录运行：

```bash
python examples/GLFT_example.py
```



### 3. 运行流程详解



#### 初始化阶段

```python
# 1. 读取全局配置
config = get_global_config()
setup_global_logging(config.log)

# 2. 获取账户信息
account_list = config.accounts
polymarket_account = account_list.get("main")

# 3. 验证账户类型
if not isinstance(polymarket_account, PolyMarketRelayerAccount):
    logger.error("第一个账户必须是PolyMarketRelayerAccount")
    return
```

#### 引擎启动阶段

```python
# 1. 创建交易引擎
engine = SingleNodeLivingTradingEngine()

# 2. 注册账户
account = PolyMarketMarketMakerAccount(polymarket_account)
await engine.register_account(account)

# 3. 注册数据源
one_market_data_feed = CryptoRepeatDataFeed()
await engine.register_data_feed(one_market_data_feed)

# 4. 注册策略
glft_strategy = PolyMarketGLFTStrategy(account, one_market_data_feed.domain_key)
await engine.register_strategy(glft_strategy)

# 5. 启动引擎
engine_task = asyncio.create_task(engine.start())
```

#### 优雅关闭机制

```python
# 监听信号 (SIGINT/SIGTERM)
loop.add_signal_handler(signal.SIGINT, lambda: stop_event.set())
loop.add_signal_handler(signal.SIGTERM, lambda: stop_event.set())

# 收到信号后取消引擎任务
engine_task.cancel()
```

### 4. 停止程序

按 `Ctrl+C` 发送 SIGINT 信号，程序会：

1. 捕获信号
2. 设置停止事件
3. 取消引擎任务
4. 等待数据源清理连接
5. 优雅地退出

## 关键参数说明

### CryptoRepeatDataFeed 相关

| 参数           | 说明                 |
|--------------|--------------------|
| `domain_key` | 由数据源自动生成的市场标识符     |
| 支持事件类型       | 订单簿更新、最佳买卖价、最后成交价等 |

### PolyMarketGLFTStrategy 相关

| 参数                      | 默认值  | 说明                 |
|-------------------------|------|--------------------|
| `window_period_seconds` | 3600 | 滚动窗口时间（秒），用于计算市场指标 |
| `update_cycle_seconds`  | 3    | 更新周期（秒），多久计算一次最优价格 |
| `p`                     | 5    | GLFT 算法参数          |
| `min_tick`              | 0.01 | 最小价格跳跃，用于价格规范化     |

## 日志和调试

### 启用详细日志

在配置文件中设置日志级别：

```toml
[log]
level = "DEBUG"  # 从 INFO 改为 DEBUG
```

### 常见日志消息

| 日志消息                            | 含义         |
|---------------------------------|------------|
| `Engine started`                | 引擎已启动      |
| `market id: {id}, slug: {slug}` | 策略已连接到指定市场 |
| `ask: {price}, bid: {price}`    | 计算出的最优买卖价  |
| `KeyboardInterrupt received`    | 程序收到中断信号   |
| `Engine task cancelled`         | 引擎已停止      |

## 常见问题

### Q: 程序启动后一直不报价怎么办？

**A:** 可能原因：

1. 市场没有实时成交数据
2. 数据源未正确连接
3. GLFT 算法还在积累足够的历史数据

解决方法：

- 检查日志输出是否有错误
- 确保网络连接正常
- 等待足够的初始数据积累（通常几分钟）

### Q: 如何修改报价参数？

**A:** 修改 `PolyMarketGLFTStrategy._run_periodic()` 方法中的参数：

```python
ask, bid = self._glft.glft_calculate(
    p=5,  # 调整此值（通常 1-10）
    min_tick=0.01  # 调整最小价格跳跃
)
```

### Q: 支持多个市场同时运行吗？

**A:** 当前示例只支持单市场。要支持多市场，需要：

1. 注册多个 `CryptoRepeatDataFeed` 实例
2. 为每个市场注册对应的 `PolyMarketGLFTStrategy`
3. 共用同一个 `engine` 和 `account`

### Q: 如何连接到仿真市场？

**A:** 修改配置文件中的 API 端点设置：

```toml
[polymarket]
api_endpoint = "https://clob-staging.polymarket.com"  # 改为测试环境
```

## 扩展示例

### 添加多市场支持

```python
# 创建多个数据源和策略
markets = ["bitcoin", "ethereum", "doge"]
feeds = []
strategies = []

for market in markets:
    feed = CryptoRepeatDataFeed(market)
    await engine.register_data_feed(feed)
    feeds.append(feed)

    strategy = PolyMarketGLFTStrategy(account, feed.domain_key)
    await engine.register_strategy(strategy)
    strategies.append(strategy)
```

### 添加自定义日志处理

```python
from loguru import logger
import sys

# 移除默认处理器并添加自定义处理
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("trading_{time}.log", level="DEBUG", rotation="100 MB")
```

## 性能优化建议

1. **调整窗口大小**：较短的窗口对市场变化反应更快，但噪声更大
2. **调整更新频率**：增加更新间隔可降低 CPU 使用率
3. **使用 uvloop**：对于 I/O 密集型任务，可以提升性能
4. **添加连接池**：复用 HTTP 连接以提高吞吐量

## 参考资源

- **核心引擎**：`src/s2cpy/core/engine.py`
- **策略实现**：`src/s2cpy/strategy/glft_market_strategy.py`
- **GLFT 算法**：`src/s2cpy/algorithms/glfts.py`
- **数据源**：`src/s2cpy/data_feeds/ploymarket_feed.py`
- **配置加载**：`src/s2cpy/infrastructure/settings.py`

## 下一步

1. 阅读 `src/s2cpy/algorithms/glfts.py` 了解 GLFT 算法细节
2. 查看 `src/s2cpy/strategy/demo_strategies.py` 了解其他策略示例
3. 运行测试验证环境配置：`pytest -q`
4. 根据需要自定义策略和参数

---

**最后更新**：2026年5月
**版本**：v1.0

