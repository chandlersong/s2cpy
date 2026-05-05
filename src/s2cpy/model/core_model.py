"""
主要是用来定义一些核心的功能类。方便后续的改变。
"""
import abc
import dataclasses
from typing import Protocol, Optional, Callable, Any, Dict

from aiohttp.payload import Order

"""
用户发出一些
"""


@dataclasses.dataclass
class Asset:
    id: str
    external_id: str
    validate_before: Optional[int] = None  # None代表永久有效，UTC的unix timestamp。精确到毫秒


@dataclasses.dataclass
class OrderInfo:
    asset: Asset
    quantity: float


@dataclasses.dataclass
class Data:
    """
    表示具体的数据
    """
    asset: Asset
    asset_type: str
    data: Any


DataHandler = Callable[[str, Any], Any]


class DataFeed(Protocol):
    """
    # 关于DataFeed的一些想法
    1. 只有在调用start的之后，其才能正式开始工作。
    2. 其要提供一个支持的信息列表，方便strategy订阅


    设想的是一个数据源。包括但不限于以下一些情况
    1. K线，盘口这些市场信息。
    2. 账户信息，比如账户余额。
    3. 一些计算过的因子。比如说MA，截面因子等
    """

    @abc.abstractmethod
    def subscribe(self, handler: DataHandler):
        pass

    @abc.abstractmethod
    async def start(self):
        pass

    @abc.abstractmethod
    def supported_data_identify(self) -> list[str]:
        """
        提供本dataFeed支持的数据类型
        :return:
        """
        pass

    @abc.abstractmethod
    def get_name(self) -> str:
        """
        提供dataFeed的名字，方便后续的管理
        :return:
        """
        pass


class OrderEngine(Protocol):

    def execute_immediately(self, order: OrderInfo):
        pass


class Strategy(Protocol):

    def register_data_list(self) -> Dict[str, str]:
        """
        定义需要哪些数据，返回一个dict，分别为assert_id和data_type
        :return:
        """
        pass

    def on_change(self, data: Data):
        """
        当外部数据任何变化时，被调用
        :param data:
        :return:
        """
        pass

    def on_history_change(self, data: Data):
        pass


class Engine(Protocol):

    @abc.abstractmethod
    async def register_data_feed(self, data_feed: DataFeed):
        pass

    @abc.abstractmethod
    async def register_strategy(self, strategy: Strategy):
        pass

    @abc.abstractmethod
    async def start(self):
        pass
