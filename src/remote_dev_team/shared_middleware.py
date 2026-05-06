import logging

from langchain.agents.middleware import SummarizationMiddleware, TodoListMiddleware, ModelRetryMiddleware, \
    ToolRetryMiddleware

from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.agent_activity_monitor import AgentActivityMonitor
from src.custom_middleware.my_middleware_prompts import MY_WRITE_TODOS_SYSTEM_PROMPT, MY_WRITE_TODOS_TOOL_DESCRIPTION

# from src.config.config_logging import setup_logging
#
# setup_logging()  # 自动配置日志

logger = logging.getLogger(__name__)

# ⚠️ 注意：文件系统中间件不再在模块级别创建
# 因为 FilesystemMiddleware 需要依赖具体的 sandbox 实例
# filesystem_middleware 应该在 DevTeamWithLinuxSandbox 中动态创建

# TodoList中间件（可以共享，不依赖 sandbox）
todo_list_middleware = TodoListMiddleware(system_prompt=MY_WRITE_TODOS_SYSTEM_PROMPT,
                                          tool_description=MY_WRITE_TODOS_TOOL_DESCRIPTION)
logger.debug("共享 待办事项列表中间件 TodoList 创建成功")

# 总结中间件（可以共享，不依赖 sandbox）
llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]
# pprint(vars(llm))  # 打印对象的所有字段的名称和值
summarization_middleware = SummarizationMiddleware(
    llm,
    triger=('fraction', 0.8)
)
logger.debug(f"共享 总结中间件 Summarization 创建成功，使用模型: {llm.model_name} ，温度: {llm.temperature}")


# ⭐ 定义 MiniMax 529 错误的重试判断函数
def should_retry_minimax_529(exc: Exception) -> bool:
    """判断是否为可重试的 MiniMax 错误（特别是 HTTP 529 服务过载）。
    
    Args:
        exc: 捕获的异常对象
        
    Returns:
        True 如果应该重试，False 否则
    """
    import httpx
    import httpcore
    from openai import InternalServerError, APIError

    # 1. 检查 OpenAI 兼容的错误（MiniMax 使用 OpenAI SDK）
    if isinstance(exc, (InternalServerError, APIError)):
        status_code = getattr(exc, 'status_code', None)
        if status_code == 529:
            logger.warning(f"🔄 检测到 MiniMax 服务过载 (HTTP 529)，将重试")
            return True
        if status_code and 500 <= status_code < 600:
            logger.warning(f"🔄 检测到服务器错误 (HTTP {status_code})，将重试")
            return True

    # 2. 检查错误消息中的关键词
    error_str = str(exc).lower()
    if any(keyword in error_str for keyword in [
        '529', 'overloaded', '负载较高', '服务繁忙', 'service overloaded'
    ]):
        logger.warning(f"🔄 检测到服务过载关键词，将重试")
        return True

    # 3. 超时错误也应该重试
    if isinstance(exc, (httpx.TimeoutException, httpcore.TimeoutException)):
        logger.warning(f"🔄 检测到超时错误，将重试")
        return True

    # 4. 其他网络错误
    if isinstance(exc, (httpx.NetworkError, httpcore.NetworkError)):
        logger.warning(f"🔄 检测到网络错误，将重试")
        return True

    return False


# 官方的 ModelRetryMiddleware，但配置自定义的重试判断逻辑
model_retry_middleware = ModelRetryMiddleware(
    max_retries=5,  # 最多重试 5 次
    retry_on=should_retry_minimax_529,  # ⭐ 使用自定义函数判断是否重试
    backoff_factor=2.0,  # 指数退避基数（1s → 2s → 4s → 8s → 16s）
    initial_delay=2.0,  # 首次等待 2 秒
    max_delay=60.0,  # 最长等待 60 秒
    jitter=True,  # 启用随机抖动（±25%，避免惊群效应）
    on_failure='continue',  # 失败后返回 AIMessage，让智能体继续
)
logger.debug("共享 模型调用重试中间件 ModelRetryMiddleware (官方 + MiniMax 529 支持) 创建成功")

# 共享的重试中间件实例（可以共享，不依赖 sandbox）
# 配置说明：
# - max_retries=5: 最多重试5次（应对临时服务过载）
# - initial_wait=2.0: 首次等待2秒（给服务器恢复时间）
# - max_wait=60.0: 最长等待60秒（避免无限等待）
# - exponential_base=2.0: 指数退避基数（2s → 4s → 8s → 16s → 32s）
# - jitter=True: 启用随机抖动（±25%，避免惊群效应）
# - enabled=True: 默认启用重试功能
# model_retry_middleware = MyRetryMiddleware(
#     max_retries=5,
#     initial_wait=2.0,
#     max_wait=60.0,
#     exponential_base=2.0,
#     jitter=True,
#     enabled=True
# )
logger.debug("共享 模型调用重试中间件 ModelRetryMiddleware (官方) 创建成功")

# 智能体活动（AIMessage、ToolMessage）监控中间件实例（可以共享，不依赖 sandbox）
agent_activity_monitor = AgentActivityMonitor()
logger.debug("共享 智能体活动监控中间件 AgentActivityMonitor 初始化完成")

# 官方工具重试中间件实例（可以共享，不依赖 sandbox）
# 使用默认配置：
# - max_retries=2: 最多重试2次（共3次尝试：1次初始 + 2次重试）
# - retry_on=(Exception,): 对所有异常进行重试
# - on_failure='continue': 失败后返回 ToolMessage，让智能体继续处理
# - backoff_factor=2.0: 指数退避基数（1s → 2s → 4s）
# - initial_delay=1.0: 首次等待1秒
# - max_delay=60.0: 最长等待60秒
# - jitter=True: 启用随机抖动（±25%，避免惊群效应）
tool_retry_middleware = ToolRetryMiddleware()
logger.debug("共享 工具重试中间件 ToolRetryMiddleware (官方) 创建成功")

logger.debug("所有共享中间件创建成功")
