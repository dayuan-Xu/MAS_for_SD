# 本模块负责提供基于setting中的PostgreSQL URL创建的全局唯一 LangGraph checkpointer、store对象。
from time import sleep

from langgraph.checkpoint.postgres import PostgresSaver

from src.config.database import get_connection_pool
from src.config.settings import settings

DB_URI = "postgresql://postgres:postgres@localhost:5442/postgres?sslmode=disable"

pool = get_connection_pool()
checkpointer = PostgresSaver(pool)

choice = settings.USE_POSTGRES_CHECKPOINTER_FIRST_TIME
if choice:
    checkpointer.setup()
    sleep(5)  # 等待数据库表结构初始化完成
    print("Postgres checkpointer的数据库表结构初始化成功。")
else:
    print("Postgres checkpointer实例成功创建。")
