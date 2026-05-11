"""
主要是用来定义一些核心的功能类。方便后续的改变。
"""
import abc
import dataclasses
import time
from copy import deepcopy
from typing import Protocol, Optional, Callable, Any, List

"""
用户发出一些
"""


@dataclasses.dataclass
class Asset:
    """
    FUTURE：
    1. 加入一些其他信息，比如最ticker size这类
    """
    id: str
    external_id: Optional[str] = None
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


class Account(Protocol):
    """
    做为一个简单的PlaceHolder。因为主要的原因合格和交易所还是很相关的。
    主要是下单等操作。这个类主要是做以下几类操作
    1. 获得账户信息。包括Balance，挂单情况，成交情况等。
    2. 执行具体的交易（这个我想以后是否分离出去）

    # V1版本所有规则。
    1. 所有的order都是同步，不是异步的，不需要返回订单成功与否的信息。
    """

    def create_order(self, asset: Asset, **kwargs) -> int:
        """
        placeHolder的方法，因为要支持多交易所的支持。
        过早的统一参数，太麻烦。
        所以暂时负责每隔交易所单独的参数
        :param asset: 交易的资产
        :param kwargs: 各个交易所自己独立的参数
        :return: order_id
        """
        pass

    def cancel_order(self, order_id: int):
        pass

    def cancel_all_orders(self):
        pass


class Strategy(Protocol):
    @abc.abstractmethod
    def data_list(self) -> List[str]:
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

    @abc.abstractmethod
    def get_name(self):
        pass

    @abc.abstractmethod
    def register_account(self, account_names: List[Account]):
        """
        #FUTURE
        1. 支持策略多账户。一个策略可以支持多个账户。
        2. 账户并不与具体交易所绑定。比如说我在binance上面看到了BTC的变动，我应该可以马上在polymarket这类下单。这点没有完全想好。
        :param account_names: None的话，就是默认账户。这个先是placeholder吧。主要account体系没有想好。
        :return:
        """
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
