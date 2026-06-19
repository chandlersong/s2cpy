import grpc
import time
from concurrent import futures
import logging

from s2cpy.generated import message_pb2_grpc, message_pb2

# 修复导入路径

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessageServicer(message_pb2_grpc.MessageServiceServicer):
    """实现服务器消息推送"""

    def StreamMessages(self, request, context):
        """
        服务器向客户端流式推送消息
        """
        client_name = request.client_name
        logger.info(f"客户端 '{client_name}' 已连接")

        # 推送 5 条消息给客户端
        for i in range(5):
            time.sleep(1)  # 每秒推送一条

            message = message_pb2.Message(
                content=f"来自服务器的消息 #{i + 1}，你好 {client_name}！",
                timestamp=int(time.time() * 1000)
            )

            logger.info(f"向 {client_name} 推送: {message.content}")
            yield message

        logger.info(f"已完成向 '{client_name}' 的消息推送")


def serve():
    """启动 gRPC 服务器"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    message_pb2_grpc.add_MessageServiceServicer_to_server(
        MessageServicer(), server
    )

    server.add_insecure_port('[::]:50051')
    logger.info("服务器启动在 [::]:50051")
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
