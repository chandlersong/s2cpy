import asyncio

import grpc

from s2cpy.generated import history_data_pb2_grpc, history_data_pb2
from loguru import logger

from s2cpy.infrastructure.settings import get_global_config, setup_global_logging
from s2cpy.services.polymarket_service import HistoryDataService


def _initial_request(local_max_timestamp: int = 0):
    """Return a simple iterator that yields a single Initial ClientMessage.

    The gRPC bidi method expects an iterable of ClientMessage; passing a single
    message (not iterable) will raise errors like "Exception iterating requests".
    For simple clients we can just pass iter([msg]).
    """
    msg = history_data_pb2.ClientMessage()
    msg.initial.local_max_timestamp = local_max_timestamp
    yield msg


async def main():
    config = get_global_config()
    setup_global_logging(config.log)
    client_config = config.sync_client
    while True:
        server_url = f'{client_config.server_address}:{client_config.port}'
        logger.info(f"开始连接到{server_url}")
        with grpc.insecure_channel(server_url) as channel:

            stub = history_data_pb2_grpc.SyncServerStub(channel)
            db_service = HistoryDataService(client_config)
            max_timestamp = db_service.get_max_batch_timestamp()
            logger.info("连接到服务器...")
            try:
                # pass an iterator (generator) to the bidi-streaming RPC
                responses = stub.sync(_initial_request(max_timestamp))
                for message in responses:
                    if message.HasField("polymarket_history"):
                        history_list = message.polymarket_history
                        # history_list is a PolyMarketHistoryList; use its fields
                        logger.info(f"[{history_list.timestamp}] 收到消息: {len(history_list.history_list)}")
                        db_service.batch_insert(history_list)
            except grpc.RpcError as e:
                logger.error(f"RPC 错误: {e.code()}, {e.details()}")
        await asyncio.sleep(10)


if __name__ == '__main__':
    asyncio.run(main())
