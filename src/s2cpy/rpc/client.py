import logging
from datetime import datetime

import grpc

from s2cpy.generated import message_pb2_grpc, message_pb2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run():
    """连接服务器并接收推送的消息"""

    # 连接到服务器
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = message_pb2_grpc.MessageServiceStub(channel)

        # 发送客户端信息
        client_info = message_pb2.ClientInfo(client_name="Python客户端")

        logger.info("连接到服务器...")

        # 接收服务器推送的消息流
        try:
            for message in stub.StreamMessages(client_info):
                timestamp = datetime.fromtimestamp(message.timestamp / 1000)
                logger.info(f"[{timestamp}] 收到消息: {message.content}")
        except grpc.RpcError as e:
            logger.error(f"RPC 错误: {e.code()}, {e.details()}")


if __name__ == '__main__':
    run()
