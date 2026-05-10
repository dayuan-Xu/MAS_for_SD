from psycopg_pool import ConnectionPool, AsyncConnectionPool

from src.config.settings import settings

_sync_connection_pool = None
_async_connection_pool = None


def get_connection_pool():
    """获取同步连接池（单例）"""
    global _sync_connection_pool
    if _sync_connection_pool is None:
        db_user = settings.POSTGRES_DB_USER
        db_password = settings.POSTGRES_DB_PASSWORD
        db_host = settings.POSTGRES_DB_HOST
        db_port = settings.POSTGRES_DB_PORT
        db_name = settings.POSTGRES_DB_NAME
        ssl_mode = settings.POSTGRES_DB_SSL_MODE

        DB_URI = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode={ssl_mode}"

        try:
            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": 0,
            }
            _sync_connection_pool = ConnectionPool(
                conninfo=DB_URI,
                max_size=8,
                kwargs=connection_kwargs,
            )
        except Exception as e:
            raise RuntimeError("无法初始化Postgres数据库连接池，请检查相应 Docker 容器是否启动！") from e
    return _sync_connection_pool


def get_async_connection_pool():
    """获取异步连接池（单例）"""
    global _async_connection_pool
    if _async_connection_pool is None:
        db_user = settings.POSTGRES_DB_USER
        db_password = settings.POSTGRES_DB_PASSWORD
        db_host = settings.POSTGRES_DB_HOST
        db_port = settings.POSTGRES_DB_PORT
        db_name = settings.POSTGRES_DB_NAME
        ssl_mode = settings.POSTGRES_DB_SSL_MODE

        DB_URI = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode={ssl_mode}"

        try:
            # 创建未打开的连接池（避免弃用警告）
            _async_connection_pool = AsyncConnectionPool(
                conninfo=DB_URI,
                min_size=5,
                max_size=20,
                open=False,  # 不自动打开，稍后手动打开
            )
        except Exception as e:
            raise RuntimeError("无法初始化Postgres异步数据库连接池，请检查相应 Docker 容器是否启动！") from e
    return _async_connection_pool
