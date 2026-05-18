from typing import List

from s2cpy.model.core_model import Strategy, Account


class PolyMarketRepeatDemoStrategy(Strategy):
    def data_list(self) -> List[str]:
        pass

    def get_name(self):
        pass

    def register_account(self, account_names: List[Account]):
        pass