from psycopg_pool import ConnectionPool

from src.config.settings import settings

_connection_pool = None


def get_connection_pool():
    global _connection_pool
    # 单例模式，确保整个应用生命周期内只创建一个连接池实例
    if _connection_pool is None:
        # 使用环境变量获取数据库连接信息，避免硬编码
        db_user = settings.POSTGRES_DB_USER
        db_password = settings.POSTGRES_DB_PASSWORD
        db_host = settings.POSTGRES_DB_HOST
        db_port = settings.POSTGRES_DB_PORT
        db_name = settings.POSTGRES_DB_NAME
        ssl_mode = settings.POSTGRES_DB_SSL_MODE

        DB_URI = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode={ssl_mode}"

        # 协议：postgresql:// 表示使用 PostgreSQL 协议。
        # 用户信息：postgres:postgres 表示用户名为 postgres，密码也为 postgres。
        # 主机：@localhost 表示数据库位于本地机器。
        # 端口：:5442 表示数据库服务运行在 5442 端口（默认是 5432）。
        # 数据库名：/postgres 表示连接的数据库名为 postgres。
        # SSL 模式：?sslmode=disable 表示禁用 SSL 加密连接。
        try:
            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": 0,
            }
            _connection_pool = ConnectionPool(
                conninfo=DB_URI,
                max_size=8,
                kwargs=connection_kwargs,
            )
        except Exception as e:
            raise RuntimeError("无法初始化Postgres数据库连接池，请检查相应 Docker 容器是否启动！") from e
    return _connection_pool
