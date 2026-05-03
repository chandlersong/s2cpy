from s2cpy.infrastructure.time import TimeInterval
from s2cpy.model.core_model import DataFeed


class CryptoRepeatDataFeed(DataFeed):
    """
    主要是代表那些BTC，一段时间内猜涨跌的数据连接
    """

    def __init__(self, coin_name="btc", interval: TimeInterval = TimeInterval.FifteenMinute):
        pass
