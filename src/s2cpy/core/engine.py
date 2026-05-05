"""

# Engine的作用
1. 作为消息分发的中心。

## 计划中
1. 风控。
2. 订单维护。比如挂单了一个，然后再弄。

# 消息的种类
1. 市场信息，比如说价格，盘口，ticker
2. 账户信息，比如说账户中的资产，挂单数量，成交信息。
3. 下单信息。


'''mermaid
flowchart TD
    A[PM Market] --> B(Engine)
    C[PM Account Data] --> B
    D[other excahnge] --> B
    B-->E(strategies)
    E-->F[order execute]
'''
"""
from typing import Dict, Any

from blinker import Namespace, NamedSignal

from s2cpy.model.core_model import Engine, DataFeed, Strategy
from loguru import logger


class SingleNodeLivingTradingEngine(Engine):
    """
    主要用于单点实盘运行的engine
    1. 他的运行状态为，ready，running，stopped
    """
    STATUS_READY = "ready"
    STATUS_RUNNING = "running"
    STATUS_STOPPED = "stopped"

    def __init__(self):
        self._namespace = Namespace()
        self._signals: Dict[str, NamedSignal] = {}
        self._strategies: Dict[str, Strategy] = {}
        self._data_feeds: Dict[str, DataFeed] = {}
        self._status = self.STATUS_READY

    async def register_strategy(self, strategy: Strategy):
        self._strategies[strategy.get_name()] = strategy
        data_list = strategy.data_list()

        logger.info(f"注册策略: {strategy.get_name()}")
        for topic in data_list:
            signal = self._signals.get(topic)
            if signal:
                signal.connect(strategy.on_change)
                logger.info(f"策略: {strategy.get_name()} 订阅了数据: {topic}")
            else:
                logger.warning(f"没有找到数据: {topic} 的信号，策略: {strategy.get_name()} 无法订阅")



    async def start(self):
        logger.info(f"开始运行交易的engine")
        for data_feed in self._data_feeds.values():
            logger.info(f"data feed: {data_feed.get_name()} 启动")
            await data_feed.start()

    async def register_data_feed(self, data_feed: DataFeed):
        self._data_feeds[data_feed.get_name()] = data_feed
        logger.info(f"data feed: {data_feed.get_name()} 注册")
        support_topic = data_feed.supported_data_identify()
        data_feed.subscribe(self._message_handler)
        for topic in support_topic:
            self._signals[topic] = self._namespace.signal(topic)
            logger.info(f"data identify: {topic} 加入总线")
        if self._status == self.STATUS_RUNNING:
            await data_feed.start()
            logger.info(f"data feed: {data_feed.get_name()} 启动")

    def _message_handler(self, topic: str, data: Any):
        signal = self._signals.get(topic)
        if signal:
            signal.send(data)
        else:
            logger.warning(f"没有找到topic: {topic} 的信号，消息被丢弃")
