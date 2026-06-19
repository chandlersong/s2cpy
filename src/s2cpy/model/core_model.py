"""
主要是用来定义一些核心的功能类。方便后续的改变。
"""
import abc
import dataclasses
from typing import Protocol, Optional, Callable, Any, List

"""
用户发出一些
"""


@dataclasses.dataclass
class Order:
    id: str
    asset_id: str
    side: int  # 1:long/buy -1:short/sell
    quantity: float
    quantity_match: float
    price: float
    status: str
    extra_info: Optional[dict] = None  # 主要存放一些交易所的特有数据，因为每个交易所有其独特额数据。


@dataclasses.dataclass
class Position:
    latest_price: float
    quantity: float
    avg_price: Optional[float] = None
    extra_info: Optional[dict] = None  # 主要存放一些交易所的特有数据，因为每个交易所有其独特额数据。


@dataclasses.dataclass(eq=False)
class Asset:
    """
    identify: 应该是有意义的。方便用户去处理一些特殊逻辑。比如说多资产的时候，通过字段去区分。
    external_id：看情况，有些有，有些没有，最好是在交易所的标识。
    validate_before: 有效期。
    FUTURE：
    1. 加入一些其他信息，比如最ticker size这类
    2. 加入一些字段，方便实盘的统计
    """
    identify: str
    mini_ticker_size: float = None
    external_id: Optional[str] = None
    validate_before: Optional[int] = None  # None代表永久有效，UTC的unix timestamp。精确到毫秒
    extra_info: Optional[dict] = None  # 主要存放一些交易所的特有数据，因为每个交易所有其独特额数据。

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Asset):
            return NotImplemented
        # Assets are considered equal if their id is equal. Other metadata
        # (external_id, validate_before) is not part of identity used for
        # hashing/keying.
        return self.identify == other.identify

    def __hash__(self) -> int:
        # Use the unique id string as the basis for the hash so Asset can be
        # safely used as a dict key or in sets.
        return hash(self.identify)


@dataclasses.dataclass
class OrderInfo:
    asset: Asset
    quantity: float


class LiveData(Protocol):
    """
    placeholder
    """
    pass


@dataclasses.dataclass
class AssetLiveData:
    """
    表示具体的数据
    """
    topic: str
    asset: Asset
    data: Any


DataHandler = Callable[[str, LiveData], Any]


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
    def supported_data_list(self) -> list[str]:
        """
        提供本dataFeed支持的数据类型
        :return:
        """
        pass

    @property
    def name(self) -> str:
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

    @abc.abstractmethod
    def supported_data_list(self) -> list[str]:
        """
        提供本dataFeed支持的数据类型
        :return:
        """
        pass

    async def start_sync(self, handler: Optional[DataHandler] = None, interval_seconds: int = 600):
        """
        表示账户开始工作。
        因为本质上来说，本地的账户和服务器的账户，都是同步关系，本地需要和服务器保持同步。
        :param handler: 消息的发送，为None表示不监听
        :param interval_seconds: 同步周期
        :return:
        """
        pass

    def create_order(self, asset: Asset, **kwargs) -> Optional[str]:
        """
        placeHolder的方法，因为要支持多交易所的支持。
        过早的统一参数，太麻烦。
        所以暂时负责每隔交易所单独的参数
        :param asset: 交易的标的物
        :param kwargs: 各个交易所自己独立的参数
        :return: order_id
        """
        pass

    def cancel_order(self, order_ids: list[str]):
        pass

    @property
    def name(self) -> str:
        raise NotImplementedError("请给你的账户定义名字")


class Strategy(Protocol):
    @abc.abstractmethod
    def data_list(self) -> List[str]:
        """
        定义需要哪些数据，返回一个dict，分别为assert_id和data_type
        :return:
        """
        pass

    def on_live_change(self, data: LiveData):
        """
        当外部数据任何变化时，被调用
        :param data:
        :return:
        """
        pass

    def on_history_change(self, data: Any):
        """
        FUTURE：以后实现，接收历史数据，一般在启动或者批量接收大批数据
        :param data:
        :return:
        """
        pass

    @property
    def name(self):
        raise NotImplementedError("策略的name方法为实现")

    async def start(self):
        """
        一些策略开始运行时候的初始化方法，并不是每个策略都需要。
        同时因为一些异步方法，需要从这里来调用
        :return:
        """
        pass


class Monitor(Strategy):
    """
    纯粹是一个placeholder的interface。
    主要是为了一些记录用的
    """

    @abc.abstractmethod
    def data_list(self) -> List[str]:
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
