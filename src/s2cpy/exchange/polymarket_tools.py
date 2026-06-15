"""
主要是polymarket的一些工具类方法
"""
import os

import time
from typing import Dict, get_args

from eth_abi import encode
from eth_utils import keccak, to_checksum_address
from py_builder_relayer_client.client import RelayClient
from py_builder_relayer_client.models import Transaction, RelayerTxType, SafeTransaction, OperationType, \
    DepositWalletCall, TransactionType
from py_clob_client_v2 import TickSize

from s2cpy.exchange.polymarket_api import RestfulAPI
from s2cpy.infrastructure.time import str_iso_datetime_to_unix_seconds
from s2cpy.model.core_model import Asset
from s2cpy.model.polymarket_io import Market, MarketGetByIdRequest
from loguru import logger

# 合约地址
# Polymarket 合约地址
CTF_ADDRESS = to_checksum_address("0x4D97DCd97eC945f40cF65F87097ACe5EA0476045")
PUSDT_ADDRESS = to_checksum_address("0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB")
PARENT_COLLECTION_ID = "0x" + "0" * 64  # 通常为 zero bytes32
ADAPTER = to_checksum_address("0xAdA100Db00Ca00073811820692005400218FcE1f")  # ← 必须用这个
NEG_RISK_ADAPTER = to_checksum_address("0xAdA2005600Dec949baf300f4C6120000bDB6eAab")  # 选举类市场

PUSD_DECIMALS = 6


def pusd_to_units(pusd_amount: float) -> int:
    """Convert pUSD amount to 6-decimal integer units."""
    if pusd_amount <= 0:
        raise ValueError("pusd_amount must be positive")
    return int(pusd_amount * 10 ** PUSD_DECIMALS)


def get_function_selector(signature: str) -> str:
    """获取函数选择器"""
    selector = keccak(text=signature)[:4].hex()
    return selector


# ────────────────────────────────────────────────────────────────────────
# 合约交互函数
# ────────────────────────────────────────────────────────────────────────

def encode_split_calldata(
        collateral_token: str,
        parent_collection_id: str,
        condition_id: str,
        partition: list,
        amount: int
) -> str:
    """编码 splitPosition 调用数据"""

    try:
        # Expect `amount` to be the raw integer amount in smallest units (e.g. already scaled by 1e6).
        function_selector = get_function_selector("splitPosition(address,bytes32,bytes32,uint256[],uint256)")

        # Ensure bytes32 params are bytes
        parent_bytes = parent_collection_id if isinstance(parent_collection_id, (bytes, bytearray)) else bytes.fromhex(
            parent_collection_id[2:])
        encoded_params = encode(
            ["address", "bytes32", "bytes32", "uint256[]", "uint256"],
            [
                collateral_token,
                parent_bytes,
                condition_id_to_bytes32(condition_id),
                partition,
                int(amount)
            ]
        )

        calldata = "0x" + function_selector + encoded_params.hex()
        return calldata

    except Exception as e:
        logger.error(f"  ❌ 编码失败: {e}")
        raise


def wait_tx(response, max_attempts=40):
    logger.debug("⏳ 等待交易确认...")
    for i in range(max_attempts):
        try:
            status = response.get_transaction()
            if status and len(status) > 0:
                txn = status[0]
                state = txn.get("state")
                tx_hash = txn.get("transactionHash") or txn.get("txHash")
                logger.debug(f"[{i + 1}/{max_attempts}] State: {state} | Hash: {tx_hash}")

                if state in ["STATE_MINED", "STATE_CONFIRMED"]:
                    logger.debug("✅ 成功！")
                    return tx_hash
                elif state == "STATE_FAILED":
                    logger.error("❌ 失败")
                    logger.error("Error:", txn.get("errorMsg"))
                    return None
        except Exception as e:
            logger.error(f"查询错误: {e}")
        time.sleep(3)
    logger.error("⚠️ 超时")
    return None


def condition_id_to_bytes32(condition_id: str) -> bytes:
    """Convert 0x-prefixed condition id hex string to bytes32."""
    raw = condition_id.lower()
    if raw.startswith("0x"):
        raw = raw[2:]
    if len(raw) != 64:
        raise ValueError(f"condition_id must be 32 bytes: {condition_id}")
    return bytes.fromhex(raw)


def split_pusdt(client: RelayClient, condition_id: str, amount: int, wallet_address: str, deposit_wallet: str,
                is_neg_risk: bool = False, ):
    """High-level helper to approve + setApprovalForAll + split pUSDT via the chosen adapter.

    If `adapter` is None, default to `ADAPTER` (regular markets). For neg-risk markets pass
    `NEG_RISK_ADAPTER` explicitly.
    """
    # 第一步：创建批准交易（如果需要）
    split_amount = amount * (10 ** 6)

    # # choose adapter
    chosen_adapter = NEG_RISK_ADAPTER if is_neg_risk else ADAPTER
    try:
        nonce_payload = client.get_nonce(
            deposit_wallet,
            TransactionType.WALLET.value
        )

        current_nonce = str(nonce_payload["nonce"])

        split_call_data = encode_split_calldata(
            collateral_token=PUSDT_ADDRESS,
            parent_collection_id=PARENT_COLLECTION_ID,
            condition_id=condition_id,
            partition=[1, 2],
            amount=split_amount,
        )

        split_call = DepositWalletCall(target=to_checksum_address(chosen_adapter), value="0", data=split_call_data)
        safe_deadline = str(int(time.time()) + 600)
        split_resp = client.execute_deposit_wallet_batch([split_call], wallet_address=wallet_address,
                                                         nonce=current_nonce,
                                                         deadline=safe_deadline)
    except Exception as e:
        print(f"wallet address:{wallet_address},Split RPC error: {e}")
        return
    tx3 = wait_tx(split_resp)
    if tx3 is None:
        logger.warning(f"Split failed or reverted — see relayer logs for details,wallet address:{wallet_address}")
        return
    logger.debug(f"wallet address:{wallet_address},Split sent successfully, tx: {tx3}")


def convert_markets_2_assets(market: Market) -> Dict[str, Asset]:
    """
    把market转换成assert
    :param market:
    :return:
    """
    if market.endDate is None:
        raise ValueError(f"market:{market.slug} market.endDate is None")
    validate_before = str_iso_datetime_to_unix_seconds(market.endDate)
    result: Dict[str, Asset] = {}
    outcomes = market.outcomes
    slug = market.slug
    for index, token_id in enumerate(market.clobTokenIds or []):
        result[token_id] = Asset(
            identify=f"{slug}-{outcomes[index]}",
            external_id=token_id,
            mini_ticker_size=float(market.orderPriceMinTickSize or 0.01),
            validate_before=validate_before,
            extra_info={"market": market},
        )
    return result

async def asserts_by_market_id(market_id: str) -> Dict[str, Asset]:
    """
    把market转换成assert
    :param market_id: market id
    :return:
    """
    api = RestfulAPI()
    market = await api.get_market_by_id(MarketGetByIdRequest(id=market_id))
    return convert_markets_2_assets(market)

def is_valid_tick_size(s: str) -> bool:
    # First, if TickSize is a typing.Literal (common in py_clob_client_v2),
    # `get_args(TickSize)` returns the allowed literal values at runtime.
    try:
        args = get_args(TickSize)
        if args:
            # normalize to string for comparison
            allowed = {str(a) for a in args}
            return s in allowed
    except Exception:
        pass

    # If TickSize is an Enum-like or iterable, try to iterate its members
    try:
        for member in TickSize:
            val = getattr(member, "value", member)
            if str(val) == s:
                return True
    except Exception:
        pass

    # If TickSize is a module/class with constant attributes, check uppercase attrs
    try:
        for name in dir(TickSize):
            if name.isupper():
                if str(getattr(TickSize, name)) == s or name == s:
                    return True
    except Exception:
        pass

    # As a last resort, try constructing TickSize (works for some Enum implementations)
    try:
        TickSize(s)
        return True
    except Exception:
        pass

    return False
