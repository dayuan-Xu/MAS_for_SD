# 本模块负责提供基于setting中的PostgreSQL URL创建的全局唯一 LangGraph checkpointer、store对象。
import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

from src.config.database import get_connection_pool
from src.config.settings import settings

logger = logging.getLogger(__name__)


def _is_database_initialized(pool) -> bool:
    """检查数据库是否已经初始化

    Returns:
        bool: True 表示已初始化，False 表示未初始化
    """
    try:
        with pool.connection() as conn:
            result = conn.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'checkpoint_migrations'
                );
            """)
            return result.fetchone()[0]
    except Exception as e:
        logger.warning(f"检查数据库状态失败: {e}")
        return False


def _get_migration_version(pool) -> int:
    """获取当前数据库的迁移版本号

    Returns:
        int: 当前版本号，如果表不存在则返回 -1
    """
    try:
        with pool.connection() as conn:
            result = conn.execute("SELECT COALESCE(MAX(v), -1) FROM checkpoint_migrations")
            row = result.fetchone()
            return row[0] if row else -1
    except Exception:
        return -1


if settings.USE_POSTGRES_CHECKPOINTER:
    pool = get_connection_pool()
    my_checkpointer = PostgresSaver(pool)

    # 智能初始化：主动判断是否需要执行 setup
    if not _is_database_initialized(pool):
        logger.info("🔧 检测到未初始化的数据库，执行 setup...")
        my_checkpointer.setup()
        logger.info("✅ Postgres checkpointer 的数据库表结构初始化成功。")
    else:
        # 检查版本是否需要升级
        current_version = _get_migration_version(pool)
        latest_version = len(my_checkpointer.MIGRATIONS) - 1

        if current_version < latest_version:
            logger.info(f"🔧 检测到 Postgres 旧版本 ({current_version})，需要升级到 {latest_version}...")
            my_checkpointer.setup()
            logger.info(f"✅ Postgres 数据库升级完成 (v{current_version} → v{latest_version})")
        else:
            logger.info(f"ℹ️ Postgres 数据库已是最新版本 (v{current_version})，跳过 setup")

    logger.info("Postgres checkpointer实例成功创建。")
else:
    my_checkpointer = MemorySaver()
    print("Memory checkpointer实例成功创建。")
