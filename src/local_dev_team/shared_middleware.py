"""
共享的中间件实例模块

提供团队中所有专家智能体共享使用的中间件实例，确保一致的行为和配置。
"""
from deepagents import FilesystemMiddleware
from deepagents.middleware import SummarizationMiddleware
from langchain.agents.middleware import HumanInTheLoopMiddleware, TodoListMiddleware, ModelRetryMiddleware

from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.my_middleware_prompts import LOCAL_FILE_SYSTEM_MIDDLEWARE_SYSTEM_PROMPT, \
    LOCAL_EXECUTE_TOOL_DESCRIPTION, MY_WRITE_TODOS_SYSTEM_PROMPT, MY_WRITE_TODOS_TOOL_DESCRIPTION
from src.paths import LOCAL_AGENT_WORKSPACE
from src.utils.fixed_local_shell_backend import FixedLocalShellBackend

# 共享的文件系统
my_local_backend = FixedLocalShellBackend(root_dir=LOCAL_AGENT_WORKSPACE, virtual_mode=True, inherit_env=True)

# 共享的消息总结中间件实例
llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]

# ⭐ 关键配置：SummarizationMiddleware 必须设置 token_threshold 才能触发摘要
summarization_middleware = SummarizationMiddleware(
    llm=llm,
    backend=my_local_backend,
    token_threshold=1500,  # 当消息总 token 数超过 1500 时触发摘要
    keep_messages=5,  # 摘要后保留最近 5 条消息不被摘要
)

# 共享的待办事项中间件实例
todo_list_middleware = TodoListMiddleware(system_prompt=MY_WRITE_TODOS_SYSTEM_PROMPT,
                                          tool_description=MY_WRITE_TODOS_TOOL_DESCRIPTION)

# 共享的文件系统中间件，提供文件系统操作工具和shell命令执行工具
filesystem_middleware = FilesystemMiddleware(
    backend=my_local_backend,  # Optional: custom backend (defaults to StateBackend)
    system_prompt=LOCAL_FILE_SYSTEM_MIDDLEWARE_SYSTEM_PROMPT,
    custom_tool_descriptions={
        "execute": LOCAL_EXECUTE_TOOL_DESCRIPTION,
    }  # Optional: Custom descriptions for filesystem tools
)

# 共享的HITL中间件实例
HITL_middleware = HumanInTheLoopMiddleware(
    interrupt_on={
        "execute": True,
    }
)

# 共享的重试中间件实例（使用 LangChain 官方实现）
retry_middleware = ModelRetryMiddleware(
    max_retries=5,           # 最多重试 5 次
    backoff_factor=2.0,      # 指数退避基数
    initial_delay=2.0,       # 首次等待 2 秒
    max_delay=60.0,          # 最长等待 60 秒
    jitter=True,             # 启用随机抖动
)
