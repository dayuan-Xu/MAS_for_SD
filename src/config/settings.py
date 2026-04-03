from pydantic_settings import BaseSettings, SettingsConfigDict  # 专门管纯固定的配置（纯静态数据），只会随软件开发环节（开发、测试、上线）而发生一定变化
from src.paths import DOT_ENV_FILE

"""
BaseSettings 按这个 优先级 从各种来源 加载配置到Settings单例：
    命令行参数
    系统环境变量
    .env 文件中的变量
    代码里写的默认值（最低）

为什么代码里一定要给字段写默认值？    
它按这个顺序找值：
先找系统环境变量
再找 .env 文件

最后找你写的默认值
所以代码中的：
                默认值 = 最后的安全垫！
                没有默认值 = 没有安全垫 = 必崩！
"""

# 这是全局唯一的配置类,可以为其他全局唯一资源提供静态配置数据
class Settings(BaseSettings):
    # 你项目所有配置写这里
    APP_NAME: str = "多智能体软件开发"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite:///test.db"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    MAX_WORKERS: int = 10
    LANGSMITH_TRACING: bool = False
    LANGSMITH_ENDPOINT: str = ""
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = ""
    TAVILY_API_KEY: str = ""
    POSTGRESQL_URL: str = ""
    JAVA_HOME: str = ""

    model_config = SettingsConfigDict(
        env_file=DOT_ENV_FILE,
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",         # 忽略 .env 文件中存在但当前Settings中未定义的字段
    )



# 🔥 全局唯一单例（整个项目只创建这一个对象）
settings = Settings()
print("\n全局静态配置settings已加载！")

# 加载LangSmith相关配置到环境变量
import os
os.environ["LANGSMITH_TRACING"] = "true" if settings.LANGSMITH_TRACING else "false"
os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
print("\nLangSmith配置已加载到环境变量中，可以通过LangSmith继续跟踪监控！")