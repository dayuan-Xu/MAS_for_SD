from deepagents import FilesystemMiddleware
from langchain.agents.middleware import SummarizationMiddleware, TodoListMiddleware

from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.my_middleware_prompts import MY_WRITE_TODOS_SYSTEM_PROMPT, MY_WRITE_TODOS_TOOL_DESCRIPTION
from src.custom_middleware.my_sandbox import MySandbox

my_sandbox_backend = MySandbox()

# 文件系统中间件，提供文件系统操作工具和shell命令执行工具
filesystem_middleware = FilesystemMiddleware(
    backend=my_sandbox_backend,  # Optional: custom backend (defaults to StateBackend)
    system_prompt=None,
    custom_tool_descriptions=None
)

# TodoList中间件
todo_list_middleware = TodoListMiddleware(system_prompt=MY_WRITE_TODOS_SYSTEM_PROMPT,
                                          tool_description=MY_WRITE_TODOS_TOOL_DESCRIPTION)

# 总结中间件
llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]
summarization_middleware = SummarizationMiddleware(llm, backend=my_sandbox_backend)
