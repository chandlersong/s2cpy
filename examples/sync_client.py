import grpc

from s2cpy.generated import history_data_pb2_grpc, history_data_pb2
from loguru import logger


def _initial_request(local_max_timestamp: int = 0):
    """Return a simple iterator that yields a single Initial ClientMessage.

    The gRPC bidi method expects an iterable of ClientMessage; passing a single
    message (not iterable) will raise errors like "Exception iterating requests".
    For simple clients we can just pass iter([msg]).
    """
    msg = history_data_pb2.ClientMessage()
    msg.initial.local_max_timestamp = local_max_timestamp
    yield msg


def main():
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = history_data_pb2_grpc.SyncServerStub(channel)

        logger.info("连接到服务器...")
        try:
            # pass an iterator (generator) to the bidi-streaming RPC
            responses = stub.sync(_initial_request(0))
            for message in responses:
                if message.HasField("polymarket_history"):
                    history_list = message.polymarket_history
                    # history_list is a PolyMarketHistoryList; use its fields
                    logger.info(f"[{history_list.timestamp}] 收到消息: {len(history_list.history_list)}")
        except grpc.RpcError as e:
            logger.error(f"RPC 错误: {e.code()}, {e.details()}")


if __name__ == '__main__':
    main()
