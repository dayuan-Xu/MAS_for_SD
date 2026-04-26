"""
统一的日志配置模块

这是多模块项目中推荐的做法：
- 集中管理所有日志配置
- 避免在每个模块重复配置
- 方便统一修改日志格式、级别、输出位置等
"""

import logging
from logging.handlers import RotatingFileHandler

from src.paths import LOG_PATH


def setup_logging(
        log_level: int = logging.DEBUG,
        log_file: str = "app.log",
        max_bytes: int = 5 * 1024 * 1024,  # 5MB
        backup_count: int = 3,
        console_output: bool = True,
):
    """
    配置全局日志系统
    
    参数:
        log_level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        log_dir: 日志文件目录
        log_file: 日志文件名
        max_bytes: 单个日志文件最大字节数（用于轮转）
        backup_count: 保留的备份文件数量
        console_output: 是否输出到控制台
    """

    # 创建日志目录
    log_path = LOG_PATH
    log_path.mkdir(parents=True, exist_ok=True)
    log_file_path = log_path / log_file

    # 创建根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除已有的 handlers（避免重复添加）
    if root_logger.handlers:
        root_logger.handlers.clear()

    # 定义日志格式
    # 详细格式：时间 - 级别 - 模块名 - 函数名 - 行号 - 消息
    detailed_format = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 简洁格式：时间 - 级别 - 消息
    simple_format = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. 文件 Handler（使用轮转，避免日志文件无限增长）
    file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别的日志
    file_handler.setFormatter(detailed_format)
    root_logger.addHandler(file_handler)

    # 2. 控制台 Handler（可选）
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)  # 控制台只显示 INFO 及以上级别
        # console_handler.setFormatter(simple_format)
        console_handler.setFormatter(detailed_format)
        root_logger.addHandler(console_handler)

    # 3. 错误日志单独记录（可选）
    error_log_path = log_path / "error.log"
    error_handler = RotatingFileHandler(
        filename=error_log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)  # 只记录 ERROR 及以上级别
    error_handler.setFormatter(detailed_format)
    root_logger.addHandler(error_handler)

    # 4. 抑制第三方库的日志输出（避免干扰）
    fully_suppressed_loggers = [
        "urllib3",  # HTTP 请求库
        "httpx",  # HTTP 客户端
        "openai",  # OpenAI SDK
        "langchain",  # LangChain
        "langgraph",  # LangGraph
        "langsmith",  # ⭐ LangSmith（会产生大量 DEBUG 日志）
        "httpcore",  # HTTP 核心库
    ]

    for logger_name in fully_suppressed_loggers:
        third_party_logger = logging.getLogger(logger_name)
        third_party_logger.setLevel(logging.CRITICAL)
        third_party_logger.propagate = False

    # AgentBay 的标准 logging 部分（Loguru 由 my_sandbox.py 处理）
    agentbay_logger = logging.getLogger("agentbay")
    agentbay_logger.setLevel(logging.CRITICAL)
    agentbay_logger.propagate = False

    _logger = logging.getLogger(__name__)
    _logger.info(f"✓ 日志系统已配置")
    _logger.info(f"  - 日志目录: {log_path.absolute()}")
    _logger.info(f"  - 日志文件: {log_file}")
    _logger.info(f"  - 日志级别: {logging.getLevelName(log_level)}")
    _logger.info(f"  - 控制台输出: {'开启' if console_output else '关闭'}")
    _logger.info(f"  - 已抑制 {len(fully_suppressed_loggers)} 个第三方库的日志")


if __name__ == "__main__":
    # 测试配置
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.debug("这是一条调试信息")
    logger.info("这是一条一般信息")
    logger.warning("这是一条警告信息")
    logger.error("这是一条错误信息")

    try:
        result = 1 / 0
    except Exception as e:
        logger.error(f"发生异常: {e}", exc_info=True)
