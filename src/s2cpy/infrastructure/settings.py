from typing import Optional, Dict, Any, Union, Annotated, Literal
import os
import tomllib
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger
import sys
from pathlib import Path


class LogSetting(BaseModel):
    log_level: str = "INFO"  # DEBUG / INFO / WARNING / ERROR
    log_to_file: bool = False
    log_file_path: str = "logs/app_{time:YYYY-MM-DD}.log"  # 支持日期占位符
    log_rotation: str = "10 MB"  # 支持 "500 MB", "1 week", "00:00"
    log_retention: str = "30 days"
    log_compression: str = "zip"
    log_serialize: bool = False  # True=输出JSON格式（生产环境推荐）


class AccountBase(BaseModel):
    """基础账户模型，所有具体账户类型应继承自此类。

    设计目的：为不同类型的账户（API key / OAuth 等）提供共同字段。
    扩展点：可继承并添加特定类型的字段（例如 websocket token、ssh key 等）。
    业务规范：所有子类必须包含一个 `type` 字段用于区分具体子类型。
    """
    type: str
    name: Optional[str] = None
    enabled: bool = True


class PolyMarketRelayerAccount(AccountBase):
    type: Literal["polymarket_relayer_account"] = "polymarket_relayer_account"
    private_key: str = None
    funder_address: str = None
    deposit_wallet: str = None
    builder_api: str = None
    builder_secret: str = None
    builder_pass_phrase: str = None


class SyncSetting(BaseModel):
    sync_cache_folder: str = "/app/cache"  # DEBUG / INFO / WARNING / ERROR


# 兼容命名：保留原来的占位符名（如果外部引用了 AccountSettings ）
AccountSettings = AccountBase


# ====================== 主配置类 ======================
class AppSettings(BaseSettings):
    instance_name: str = "测试项目"
    environment: str = "development"  # development / production
    debug: bool = False
    proxy_url: Optional[str] = None
    log: LogSetting = LogSetting()
    sync: SyncSetting = SyncSetting()
    # pydantic-settings 配置
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",  # 支持 DATABASE__HOST=xxx 这种环境变量
        case_sensitive=False,
        extra="ignore",
    )

    # 多账户支持（使用 pydantic 的 discriminated union 以区分不同类型账户）
    accounts: Dict[str, Annotated[Union[PolyMarketRelayerAccount], Field(discriminator="type")]] = {}
    # 指定默认的账户名称（可通过环境变量 ACCOUNT_DEFAULT 或 ACCOUNTS__<name>__ 覆盖）
    default_account: Optional[str] = None

    # ====================== 自定义加载多个 TOML 文件 ======================
    @classmethod
    def load_config(cls) -> "AppSettings":
        """支持从环境变量指定配置文件路径 + 多文件分层覆盖"""

        # 1. 从环境变量获取配置文件路径（用户最关心的问题）
        custom_path = os.getenv("CONFIG_PATH")  # 例如: CONFIG_PATH=/path/to/myconfig.toml
        log_folder = os.getenv("LOG_FOLDER")

        # 默认配置文件路径（按优先级顺序）
        if log_folder is None:
            base_dir = Path(__file__).parent.parent.parent.parent / "config"
        else:
            base_dir = Path(log_folder)

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
        logger.info("激活的配置文件为：{}".format(config_files))
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

    @model_validator(mode="after")
    def _validate_default_account(self) -> "AppSettings":
        """校验 default_account 是否存在于 accounts 中（若设置）。

        规则：
        - 如果 `default_account` 不为空，但不在 `accounts` 中 -> 抛出 ValueError。
        """
        if self.default_account:
            if self.default_account not in (self.accounts or {}):
                raise ValueError(f"default_account '{self.default_account}' not found in accounts")
        return self

    def get_account(self, name: Optional[str] = None) -> Union[PolyMarketRelayerAccount]:
        """获取命名账户；如果 name 为 None，则走默认选择逻辑（见 get_default_account）。"""
        if name is None:
            return self.get_default_account()
        try:
            return self.accounts[name]
        except KeyError:
            raise KeyError(f"Account '{name}' not found")

    def get_default_account(self) -> Union[PolyMarketRelayerAccount]:
        """默认账户选择策略：

        - 若 `default_account` 已设置且存在，则返回对应账户。
        - 若未设置但仅有一个账户配置，则返回唯一账户。
        - 否则抛出 ValueError（需调用者明确指定要使用的账户）。
        """
        if self.default_account:
            return self.accounts[self.default_account]

        if not self.accounts:
            raise ValueError("No accounts configured")

        if len(self.accounts) == 1:
            return next(iter(self.accounts.values()))

        raise ValueError("Multiple accounts present but no default_account set")

    @classmethod
    def get_instance(cls) -> "AppSettings":
        """进程内单例入口，首次调用时通过 load_config 初始化。"""
        global _global_settings
        if _global_settings is None:
            _global_settings = cls.load_config()
        assert _global_settings is not None
        return _global_settings


# 辅助函数：深层字典合并（让嵌套的 database、redis 等也能正确覆盖）
def _deep_update(target: dict, source: dict):
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


_global_settings: AppSettings | None = None


def get_global_config() -> AppSettings:
    """对外提供全局配置单例。"""
    return AppSettings.get_instance()


def reset_global_config() -> None:
    """重置全局配置单例（主要用于测试场景）。"""
    global _global_settings
    _global_settings = None


def setup_global_logging(log_config: LogSetting):
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
