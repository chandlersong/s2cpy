from functools import lru_cache
from pathlib import Path
from typing import Optional
import os
import tomllib
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogSetting(BaseModel):
    log_level: str = "INFO"  # DEBUG / INFO / WARNING / ERROR
    log_to_file: bool = False
    log_file_path: str = "logs/app_{time:YYYY-MM-DD}.log"  # 支持日期占位符
    log_rotation: str = "10 MB"  # 支持 "500 MB", "1 week", "00:00"
    log_retention: str = "30 days"
    log_compression: str = "zip"
    log_serialize: bool = False  # True=输出JSON格式（生产环境推荐）


# ====================== 主配置类 ======================
class AppSettings(BaseSettings):
    instance_name: str = "测试项目"
    environment: str = "development"  # development / production
    proxy_url: Optional[str] = None
    log: LogSetting = LogSetting()
    # pydantic-settings 配置
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",  # 支持 DATABASE__HOST=xxx 这种环境变量
        case_sensitive=False,
        extra="ignore",
    )

    # ====================== 自定义加载多个 TOML 文件 ======================
    @classmethod
    def load_config(cls) -> "AppSettings":
        """支持从环境变量指定配置文件路径 + 多文件分层覆盖"""

        # 1. 从环境变量获取配置文件路径（用户最关心的问题）
        custom_path = os.getenv("CONFIG_PATH")  # 例如: CONFIG_PATH=/path/to/myconfig.toml

        # 默认配置文件路径（按优先级顺序）
        base_dir = Path(__file__).parent.parent.parent.parent / "config"
        running_env = os.getenv('ENV', 'dev')

        default_files = [
            base_dir / "config.toml",  # 基础配置（最低优先级）
            base_dir / f"config.{running_env}.toml",  # 环境特定配置
            base_dir / "secrets.toml",  # 敏感配置（最高文件优先级）
        ]

        # 如果用户通过环境变量指定了配置文件，就只用这个（或把它加到最前面）
        if custom_path and Path(custom_path).exists():
            config_files = [Path(custom_path)] + [f for f in default_files if f.exists()]
        else:
            config_files = [f for f in default_files if f.exists()]

        # 开始合并配置
        merged_config: dict = {}

        for file_path in config_files:
            if file_path.exists():
                try:
                    with open(file_path, "rb") as f:
                        data = tomllib.load(f)
                        # 深层合并（后来的覆盖前面的）
                        _deep_update(merged_config, data)
                    print(f"已加载配置文件: {file_path}")
                except Exception as e:
                    print(f"警告：加载 {file_path} 失败: {e}")

        # 使用合并后的字典创建配置实例
        # 环境变量优先级最高（会自动覆盖文件中的值）
        res = cls(**merged_config)
        res.environment = running_env
        return res


# 辅助函数：深层字典合并（让嵌套的 database、redis 等也能正确覆盖）
def _deep_update(target: dict, source: dict):
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


# ====================== 使用方式 ======================
@lru_cache
def get_config() -> AppSettings:
    """整个项目统一使用这个函数获取配置（单例推荐）"""
    return AppSettings.load_config()


from loguru import logger
import sys
from pathlib import Path


def setup_logging(log_config: LogSetting):
    """根据配置初始化 Loguru（项目启动时调用一次）"""

    # 先移除默认的处理器（避免重复输出）
    logger.remove()

    # 1. 输出到控制台（带颜色）
    logger.add(
        sys.stdout,
        level=log_config.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
        enqueue=True,  # 线程安全
    )

    # 2. 输出到文件（如果开启）
    if log_config.log_to_file:
        log_dir = Path(log_config.log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_config.log_file_path,
            level=log_config.log_level,
            rotation=log_config.log_rotation,  # 自动切割日志
            retention=log_config.log_retention,  # 自动清理旧日志
            compression=log_config.log_compression,
            serialize=log_config.log_serialize,  # True = 输出 JSON 格式，便于日志系统采集
            enqueue=True,
            encoding="utf-8",
        )

    logger.info(f"日志系统初始化完成，日志级别: {log_config.log_level}")


# 测试用（直接运行此文件可测试）
if __name__ == "__main__":
    config = get_config()
    setup_logging(config.log)
    logger.info(f"应用名称: {config.instance_name}")
    logger.info(f"运行环境: {config.environment}")
    logger.info(f"代理地址: {config.proxy_url}")
    # print(config.model_dump_json(indent=2))   # 查看完整配置
