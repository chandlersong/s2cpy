from py_clob_client_v2 import ClobClient, BalanceAllowanceParams, AssetType
from py_clob_client_v2.constants import POLYGON

from s2cpy.infrastructure.settings import PolyMarketRelayerAccount
from s2cpy.model.core_model import Account


class PolyMarketMarketMakerAccount(Account):
    """
    具体功能描述
    1. 同步仓位信息。
        - 启动时。同步订单信息
        - 没10分钟，同步一次新单信息。
    2. 同步订单信息。
        - 下达订单的信息。
        - 监听订单成功与否的信息。
    3. 发送消息给engine，进入bus
        - 订单成交与失败。包括订单和仓位变化。

    """

    def __init__(self, config: PolyMarketRelayerAccount):
        HOST = "https://clob.polymarket.com"
        client = ClobClient(
            host=HOST,
            chain_id=POLYGON,
            key=config.private_key,
            funder=config.funder_address,
            signature_type=3,  # POLY_1271 Deposit Wallet
        )
        self._api_creds = client.create_or_derive_api_key()
        client.set_api_creds(self._api_creds)
        balance_collateral = client.get_balance_allowance(
            BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        )
        usdc_balance = int(balance_collateral["balance"]) / 1_000_000
        usdc_allowance = balance_collateral["allowances"]

        print(f"USDC 余额: {usdc_balance:.4f}")
        print(f"allowances: {usdc_balance:.4f}")
        for key, value in usdc_allowance.items():
            print(f"{key}: {value}")
        open_orders = client.get_open_orders()
        print(f"open_orders: {open_orders}")


    def sync_account_position(self):
        """
        同步账户的订单信息。
        :return:
        """
        pass