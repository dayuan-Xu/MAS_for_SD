import logging

from langchain.agents.middleware import SummarizationMiddleware, TodoListMiddleware, ModelRetryMiddleware, \
    ToolRetryMiddleware

from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.message_sequence_validator import MessageSequenceValidator
from src.custom_middleware.my_middleware_prompts import MY_WRITE_TODOS_SYSTEM_PROMPT, MY_WRITE_TODOS_TOOL_DESCRIPTION

# from src.config.config_logging import setup_logging
#
# setup_logging()  # 自动配置日志

logger = logging.getLogger(__name__)

# TodoList中间件（可以共享，不依赖 sandbox）
shared_todo_list_middleware = TodoListMiddleware(
    system_prompt=MY_WRITE_TODOS_SYSTEM_PROMPT,
    tool_description=MY_WRITE_TODOS_TOOL_DESCRIPTION
)
logger.debug("共享 待办事项列表中间件 TodoList 创建成功")

# 总结中间件（可以共享，不依赖 sandbox）
llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]
# pprint(vars(llm))  # 打印对象的所有字段的名称和值
shared_summarization_middleware = SummarizationMiddleware(
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

    logger.error(f"model call retry 遇到未知错误，将不对该错误类型重试model call，请查看日志检查错误详情")
    logger.error(f"❌ model call 遇到的未知错误的名称: {type(exc).__name__}")
    logger.error(f"model call 遇到的未知错误的具体信息: {str(exc)}")

    return False


# ModelRetryMiddleware，配置自定义的重试判断逻辑
shared_model_retry_middleware = ModelRetryMiddleware(
    retry_on=should_retry_minimax_529,  # 使用自定义函数判断是否为可重试的异常
    # on_failure='continue',  # when all retries are exhausted, return an `AIMessage` with error details, allowing the agent to continue with an error response.
    on_failure='error',  # when all retries are exhausted, re-raise the exception, stopping agent execution.
)
logger.debug("共享 模型调用重试中间件 ModelRetryMiddleware (自动识别可重试的异常) 创建成功")

# ToolRetryMiddleware
tool_retry_middleware = ToolRetryMiddleware(
    on_failure='continue',
    # when all retries are exhausted, return an `ToolMessage` with error details, allowing the LLM to handle the failure and potentially recover.
    # on_failure='error',  # when all retries are exhausted, re-raise the exception, stopping agent execution.
)
logger.debug("共享 工具重试中间件 ToolRetryMiddleware 创建成功")

shared_message_sequence_validator = MessageSequenceValidator()
logger.debug("共享 消息序列验证中间件 MessageSequenceValidator 创建成功")

logger.debug("所有共享中间件创建成功")
