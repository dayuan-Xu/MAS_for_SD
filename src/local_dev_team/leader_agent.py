import uuid
from deepagents import SubAgentMiddleware
from deepagents.middleware import SkillsMiddleware
from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from src.Tools import get_current_time
from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.dev_progress import TeamLeaderMiddleware
from src.custom_middleware.my_middleware_prompts import MY_TASK_PROMPT, \
    MY_TASK_TOOL_DESCRIPTION
from src.local_dev_team.shared_middleware import retry_middleware, my_local_backend, filesystem_middleware, \
    summarization_middleware, HITL_middleware, todo_list_middleware
from src.local_dev_team.team_experts import subagents
from src.paths import AGENT_SYSTEM_PROMPTS_FILES
from src.utils.roles_prompt_manager import get_system_prompt

mySkillsMiddleware = SkillsMiddleware(
    backend=my_local_backend,
    sources=["/skills/leader/"])

subagent_middleware = SubAgentMiddleware(backend=my_local_backend,
                                         subagents=subagents,
                                         system_prompt=MY_TASK_PROMPT,
                                         task_description=MY_TASK_TOOL_DESCRIPTION)

llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]

team_leader_middleware = TeamLeaderMiddleware()

leader_sys_prompt = get_system_prompt("team_leader", prompts_dir=AGENT_SYSTEM_PROMPTS_FILES)
leader = create_agent(
    model=llm,
    tools=[get_current_time],
    system_prompt=leader_sys_prompt,
    middleware=[
        todo_list_middleware,
        mySkillsMiddleware,
        filesystem_middleware,
        subagent_middleware,
        summarization_middleware,
        team_leader_middleware,
        HITL_middleware,
        retry_middleware,  # ⭐ 重试中间件放在最内层，紧贴 LLM API 调用
    ],  # type: ignore[arg-type]  # LangChain中间件泛型协变误报
    checkpointer=MemorySaver(),
    name="Tim",
)

if __name__ == "__main__":
    from src.utils.graph_running_utils import multi_turn_conversation

    run_config: RunnableConfig = {
        "tags": ["agent_based_dev_team", "Leader"],
        "run_name": "Leader-测试-五子棋",
        "configurable": {"thread_id": str(uuid.uuid4())}
    }

    # toy_game = """使用Python GUI开发一个简单的五子棋游戏。"""

    multi_turn_conversation(leader, run_config)
