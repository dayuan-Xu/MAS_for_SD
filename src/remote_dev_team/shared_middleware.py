import logging

from langchain.agents.middleware import SummarizationMiddleware, TodoListMiddleware

from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.agent_activity_monitor import AgentActivityMonitor
from src.custom_middleware.model_call_retry import MyRetryMiddleware
from src.custom_middleware.my_middleware_prompts import MY_WRITE_TODOS_SYSTEM_PROMPT, MY_WRITE_TODOS_TOOL_DESCRIPTION

# ⚠️ 注意：不再从 agent_config 导入 my_composite_backend
# CompositeBackend 应该在 AgentBayBasedDevTeam 中根据具体任务动态创建

logger = logging.getLogger(__name__)

# ⚠️ 注意：文件系统中间件不再在模块级别创建
# 因为 FilesystemMiddleware 需要依赖具体的 sandbox 实例
# filesystem_middleware 应该在 AgentBayBasedDevTeam 中动态创建

# TodoList中间件（可以共享，不依赖 sandbox）
logger.debug("创建 TodoList 中间件")
todo_list_middleware = TodoListMiddleware(system_prompt=MY_WRITE_TODOS_SYSTEM_PROMPT,
                                          tool_description=MY_WRITE_TODOS_TOOL_DESCRIPTION)

# 总结中间件（可以共享，不依赖 sandbox）
llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]
logger.debug(f"创建总结中间件，使用模型: {llm}")
summarization_middleware = SummarizationMiddleware(llm)

# 共享的重试中间件实例（可以共享，不依赖 sandbox）
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

agent_activity_monitor = AgentActivityMonitor()
