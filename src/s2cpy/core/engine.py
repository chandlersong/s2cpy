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


class LivingTradingEngine:
    pass
