import logging

from langchain.agents.middleware import (
    SummarizationMiddleware,
    TodoListMiddleware,
    ModelRetryMiddleware,
    ToolRetryMiddleware,
)

from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.message_sequence_validator import MessageSequenceValidator
from src.custom_middleware.my_middleware_prompts import (
    MY_WRITE_TODOS_SYSTEM_PROMPT,
    MY_WRITE_TODOS_TOOL_DESCRIPTION,
)

# from src.config.config_logging import setup_logging
#
# setup_logging()  # 自动配置日志

logger = logging.getLogger(__name__)

# TodoList中间件（可以共享，不依赖 sandbox）
shared_todo_list_middleware = TodoListMiddleware(
    system_prompt=MY_WRITE_TODOS_SYSTEM_PROMPT,
    tool_description=MY_WRITE_TODOS_TOOL_DESCRIPTION,
)
logger.debug("共享 待办事项列表中间件 TodoList 创建成功")

# 总结中间件（可以共享，不依赖 sandbox）
llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]
# pprint(vars(llm))  # 打印对象的所有字段的名称和值
shared_summarization_middleware = SummarizationMiddleware(llm, trigger=("fraction", 0.8))
logger.debug(
    f"共享 总结中间件 Summarization 创建成功，使用模型: {llm.model_name} ，温度: {llm.temperature}"
)


# ⭐ 定义 MiniMax 529 错误的重试判断函数
def model_call_should_retry_for(exc: Exception) -> bool:
    """判断是否为可重试的模型调用错误。

    Args:
        exc: 捕获的异常对象

    Returns:
        True 如果应该重试，False 否则
    """
    import httpx
    import httpcore
    from openai import InternalServerError, APIError, APIStatusError

    # 1. 检查 MiniMax 服务过载错误，已知 MiniMax 使用 OpenAI SDK
    if isinstance(exc, (InternalServerError, APIError)):
        status_code = getattr(exc, "status_code", None)
        if status_code == 529:
            logger.warning(f"🔄 检测到 MiniMax 服务过载 (HTTP 529)，将重试")
            return True
        if status_code and 500 <= status_code < 600:
            logger.warning(f"🔄 检测到服务器错误 (HTTP {status_code})，将重试")
            return True

    # 2. 检查 MiniMax 账户余额不足错误，已知 MiniMax 使用 OpenAI SDK
    if isinstance(exc, APIStatusError):
        status_code = getattr(exc, "status_code", None)
        if status_code == 402:
            logger.error(f"❌ 检测到MiniMax账户余额不足错误 (HTTP 402)，不重试")
            return False
        if status_code and 400 <= status_code < 500:
            logger.error(f"❌ 检测到客户端错误 (HTTP {status_code})，不重试")
            return False

    # 3. 检查错误消息中的关键词
    error_str = str(exc).lower()
    if any(
        keyword in error_str
        for keyword in [
            "529",
            "overloaded",
            "负载较高",
            "服务繁忙",
            "service overloaded",
        ]
    ):
        logger.warning(f"🔄 检测到服务过载关键词，将重试")
        return True

    # 4. 超时错误也应该重试
    if isinstance(exc, (httpx.TimeoutException, httpcore.TimeoutException)):
        logger.warning(f"🔄 检测到超时错误，将重试")
        return True

    # 5. 其他网络错误
    if isinstance(exc, (httpx.NetworkError, httpcore.NetworkError)):
        logger.warning(f"🔄 检测到网络错误，将重试")
        return True

    logger.error(
        f"model call retry 遇到未知错误，将不对该错误类型重试model call，请查看日志检查错误详情"
    )
    logger.error(f"❌ model call 遇到的未知错误的名称: {type(exc).__name__}")
    logger.error(f"model call 遇到的未知错误的具体信息: {str(exc)}")

    return False


# ModelRetryMiddleware，配置自定义的重试判断逻辑
shared_model_retry_middleware = ModelRetryMiddleware(
    retry_on=model_call_should_retry_for,  # 使用自定义函数判断是否为可重试的异常
    # on_failure='continue',  # when all retries are exhausted, return an `AIMessage` with error details, allowing the agent to continue with an error response.
    on_failure="error",  # when all retries are exhausted, re-raise the exception, stopping agent execution.
)
logger.debug(
    "共享 模型调用重试中间件 ModelRetryMiddleware (自动识别可重试的异常) 创建成功"
)

# ToolRetryMiddleware


def tool_exec_should_retry_for(exc: Exception) -> bool:
    """判断是否应该重试工具调用

    对于沙盒会话过期异常，不应该重试（会话已被清理），直接返回 False。
    对于任务中止异常，不应该重试，直接返回 False。
    对于余额不足等客户端错误，不应该重试，直接返回 False。
    对于其他可重试异常，返回 True。
    """
    from src.dev_team.my_backend import SandboxSessionExpiredError

    if isinstance(exc, SandboxSessionExpiredError):
        logger.warning(f"⚠️ 沙盒会话已过期，跳过内部使用了它的工具的执行重试")
        return False

    try:
        from backend.app.services.custom_agent_middleware.human_cancel import (
            TaskCancelledException,
        )

        if isinstance(exc, TaskCancelledException):
            logger.info(f"🛑 检测到任务中止，不重试工具调用")
            return False
    except ImportError:
        pass

    try:
        from openai import APIStatusError

        if isinstance(exc, APIStatusError):
            status_code = getattr(exc, "status_code", None)
            if status_code == 402:
                logger.error(f"❌ 工具调用中检测到MiniMax账户余额不足错误 (HTTP 402)，不重试")
                return False
            if status_code and 400 <= status_code < 500:
                logger.error(f"❌ 工具调用中检测到客户端错误 (HTTP {status_code})，不重试")
                return False
    except ImportError:
        pass

    return True


def handle_tool_failure(exc: Exception) -> str:
    """处理工具调用失败，生成定制化的错误消息

    Args:
        exc: 捕获的异常，尤其是send message工具执行过程中可能会遇到的异常

    Returns:
        格式化的错误消息，用于 ToolMessage
    """
    from src.dev_team.my_backend import SandboxSessionExpiredError

    if isinstance(exc, SandboxSessionExpiredError):
        return (
            "❌ 沙盒会话已过期！\n"
            "当前开发会话已达到最长运行时间限制，所有以sandbox开头的工具将失效！沙盒中的软件成果物已被自动下载到服务器。\n"
            "请你立即总结当前进度并立即给出回复。"
            "如果你是智能体Alice，则在请示新的用户指令之后继续开发。"
        )

    try:
        from backend.app.services.custom_agent_middleware.human_cancel import (
            TaskCancelledException,
        )

        if isinstance(exc, TaskCancelledException):
            return (
                "用户已手动请求中止当前任务的执行。"
                "请立即总结当前进度并立即给出回复。"
            )
    except ImportError:
        pass

    try:
        from openai import APIStatusError

        if isinstance(exc, APIStatusError):
            status_code = getattr(exc, "status_code", None)
            if status_code == 402:
                return (
                    "❌ 当前接收到你的消息的智能体已经中止运行，因为其使用的模型调用因用户账户余额不足而中止运行。\n"
                    "请你提示用户充值。\n"
                    "请在请示新的用户指令之后继续工作。"
                )
            if status_code and 400 <= status_code < 500:
                return (
                    f"❌ 当前接收到你的消息的智能体已经中止运行，因为其使用的LLM API 遇到 客户端错误（HTTP {status_code}）：{str(exc)}。\n"
                    "请你提示用户检查LLM API调用客户端。\n"
                    "请在请示新的用户指令之后继续工作。"
                )
    except ImportError:
        pass

    return f"工具调用失败: {type(exc).__name__}: {str(exc)}"


tool_retry_middleware = ToolRetryMiddleware(
    retry_on=tool_exec_should_retry_for,
    on_failure=handle_tool_failure,
)
logger.debug("共享 工具重试中间件 ToolRetryMiddleware 创建成功")

shared_message_sequence_validator = MessageSequenceValidator()
logger.debug("共享 消息序列验证中间件 MessageSequenceValidator 创建成功")

logger.debug("所有共享中间件创建成功")
