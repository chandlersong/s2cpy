import dataclasses
import datetime
import os
from typing import List, Union

try:
    import psycopg
except ImportError:  # pragma: no cover - defensive fallback for test environments
    class _PsycopgFallback:
        @staticmethod
        def connect(*args, **kwargs):
            raise ImportError("psycopg is required to open PostgreSQL connections")

    psycopg = _PsycopgFallback()

@dataclasses.dataclass
class PostgresqlInfo:
    user: str
    password: str
    host: str
    port: int
    dbname: str

    def to_connect_url(self, driver: str = "psycopg2") -> str:
        """构建 SQLAlchemy PostgreSQL 连接字符串"""
        return f"postgresql+{driver}://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"

    @classmethod
    def from_env(cls):
        db_user = os.getenv("DB_USER", "username")
        db_pass = os.getenv("DB_PASS", "password")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = int(os.getenv("DB_PORT", "5432"))
        db_name = os.getenv("DB_NAME", "mydb")
        return PostgresqlInfo(
            user=db_user,
            password=db_pass,
            host=db_host,
            port=db_port,
            dbname=db_name,
        )



