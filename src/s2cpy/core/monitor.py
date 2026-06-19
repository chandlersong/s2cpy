from typing import List

from s2cpy.model.core_model import Monitor, AssetLiveData
from s2cpy.model.polymarke_core import POLYMARKET_ACCOUNT_TOPICS


class LiquidityProviderTradeSnapshotMonitor(Monitor):
    """
    主要是用于记录一些围观需要接收的信息。以后慢慢的完善。
    计划
    - 当时的order book
    """

    def __init__(self, data_feed_name_list: List[str], account_list: List[str]):
        self._data_feed_name_list = data_feed_name_list
        self._account_list = account_list

    @property
    def name(self):
        return "LiquidityProviderTradeSnapshotMonitor"

    def data_list(self) -> List[str]:
        data_feed_topics = []
        account_topics = []
        for feed_name in self._data_feed_name_list:
            topics = [
                f"{feed_name}.book",
                f"{feed_name}.tick_size_change",
                f"{feed_name}.last_trade_price",
                f"{feed_name}.best_bid_ask",
            ]
            data_feed_topics.extend(topics)
        account_topics = []
        for account_name in self._account_list:
            topics = [
                template.format(name=account_name) for template in POLYMARKET_ACCOUNT_TOPICS.values()
            ]
            account_topics.extend(topics)
        return data_feed_topics + account_topics

    def on_live_change(self, data: AssetLiveData):
        """
        当外部数据任何变化时，被调用
        :param data:
        :return:
        """
        pass
