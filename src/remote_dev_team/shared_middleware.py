import logging
from deepagents import FilesystemMiddleware
from langchain.agents.middleware import SummarizationMiddleware, TodoListMiddleware

from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.model_call_retry import MyRetryMiddleware
from src.custom_middleware.my_middleware_prompts import MY_WRITE_TODOS_SYSTEM_PROMPT, MY_WRITE_TODOS_TOOL_DESCRIPTION
from src.remote_dev_team.agent_config import my_composite_backend

logger = logging.getLogger(__name__)

# 文件系统中间件，提供文件系统操作工具和shell命令执行工具
logger.debug("创建文件系统中间件")
filesystem_middleware = FilesystemMiddleware(
    backend=my_composite_backend,  # Optional: custom backend (defaults to StateBackend)
    system_prompt=None,
    custom_tool_descriptions=None
)

# TodoList中间件
logger.debug("创建 TodoList 中间件")
todo_list_middleware = TodoListMiddleware(system_prompt=MY_WRITE_TODOS_SYSTEM_PROMPT,
                                          tool_description=MY_WRITE_TODOS_TOOL_DESCRIPTION)

# 总结中间件
llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]
logger.debug(f"创建总结中间件，使用模型: {llm}")
summarization_middleware = SummarizationMiddleware(llm)

# 共享的重试中间件实例
# 配置说明：
# - max_retries=5: 最多重试5次（应对临时服务过载）
# - initial_wait=2.0: 首次等待2秒（给服务器恢复时间）
# - max_wait=60.0: 最长等待60秒（避免无限等待）
# - exponential_base=2.0: 指数退避基数（2s → 4s → 8s → 16s → 32s）
# - jitter=True: 启用随机抖动（±25%，避免惊群效应）
# - enabled=True: 默认启用重试功能
retry_middleware = MyRetryMiddleware(
    max_retries=5,
    initial_wait=2.0,
    max_wait=60.0,
    exponential_base=2.0,
    jitter=True,
    enabled=True
)

logger.debug("共享中间件初始化完成")
