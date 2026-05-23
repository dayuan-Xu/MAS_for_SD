import logging

from psycopg_pool import ConnectionPool, AsyncConnectionPool

from src.config.settings import settings

logger = logging.getLogger(__name__)

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

        logger.info("✅ PostgreSQL连接池已初始化")
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
                min_size=2,  # 减少最小连接数
                max_size=10,  # 减少最大连接数
                open=False,  # 不自动打开，稍后手动打开
                timeout=30,  # 连接超时时间（秒）
                reconnect_timeout=5,  # 重连超时时间（秒）
                max_lifetime=1800,  # 连接最大生命周期30分钟（秒）
                check=AsyncConnectionPool.check_connection,  # 启用连接健康检查
            )
        except Exception as e:
            raise RuntimeError("无法初始化Postgres异步数据库连接池，请检查相应 Docker 容器是否启动！") from e
        logger.info("✅ PostgreSQL异步连接池已初始化")
    return _async_connection_pool


async def reset_async_connection_pool():
    """重置异步连接池（用于恢复失效的连接）"""
    global _async_connection_pool

    if _async_connection_pool is not None:
        try:
            logger.info("🔄 正在重置异步PostgreSQL连接池...")
            await _async_connection_pool.close()
            logger.info("✅ 旧连接池已关闭")
        except Exception as e:
            logger.warning(f"⚠️ 关闭旧连接池时出错: {e}")
        finally:
            _async_connection_pool = None
            logger.info("✅ 连接池已重置，下次调用将创建新连接池")
