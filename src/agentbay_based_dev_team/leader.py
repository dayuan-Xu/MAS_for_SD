import uuid
from deepagents import SubAgentMiddleware
from deepagents.middleware import SkillsMiddleware
from deepagents.middleware.subagents import SubAgent
from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from src.Tools import get_current_time
from src.agentbay_based_dev_team.shared_middleware import my_sandbox_backend, filesystem_middleware, \
    summarization_middleware, todo_list_middleware
from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.my_sandbox import LEADER_SKILL_PATH
from src.custom_middleware.system_prompt_monitor import MyMonitorMiddleware
from src.local_dev_team.shared_middleware import retry_middleware
from src.paths import AGENTBAY_SYSTEM_PROMPTS_FILES
from src.utils.roles_prompt_manager import get_system_prompt

leader_skills_middleware = SkillsMiddleware(
    backend=my_sandbox_backend,
    sources=[LEADER_SKILL_PATH])

# 设置主干模型
llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]

# 让David也有一个短暂的子智能体可以委派
DEFAULT_GENERAL_PURPOSE_DESCRIPTION = ("General-purpose agent for "
                                       "researching complex questions, "
                                       "searching for files and content,"
                                       " and executing multi-step tasks. "
                                       "When you are searching for a keyword or file "
                                       "and are not confident that you will find the right match in the first few tries "
                                       "use this agent to perform the search for you. "
                                       "This agent has access to all tools as the main agent.")  # noqa: E501

DEFAULT_SUBAGENT_PROMPT = "In order to complete the objective that the user asks of you, you have access to a number of standard tools."

# 在向SubAgentMiddleware通过字典传入的子智能体时必须指明model和tools
GENERAL_PURPOSE_SUBAGENT: SubAgent = {
    "model": llm,
    "tools": [],
    "name": "general-purpose",
    "description": DEFAULT_GENERAL_PURPOSE_DESCRIPTION,
    "system_prompt": DEFAULT_SUBAGENT_PROMPT,
    "middleware": [
        filesystem_middleware,
        leader_skills_middleware,
        summarization_middleware,
        # myHITLMiddleware,
        retry_middleware,
    ],
}

subagent_middleware = SubAgentMiddleware(backend=my_sandbox_backend, subagents=[GENERAL_PURPOSE_SUBAGENT])

leader_sys_prompt = get_system_prompt("team_leader", prompts_dir=AGENTBAY_SYSTEM_PROMPTS_FILES)

leader = create_agent(
    model=llm,
    tools=[get_current_time],
    system_prompt=leader_sys_prompt,
    middleware=[
        todo_list_middleware,
        leader_skills_middleware,
        filesystem_middleware,
        subagent_middleware,
        summarization_middleware,
        retry_middleware,
    ],
    checkpointer=MemorySaver(),  # 后续可以是postgres checkpointer
    name="Tim_Leader",
)

if __name__ == "__main__":
    from src.utils.graph_running_utils import multi_turn_conversation

    leader = create_agent(
        model=llm,
        tools=[get_current_time],
        system_prompt=leader_sys_prompt,
        middleware=[
            todo_list_middleware,
            leader_skills_middleware,
            filesystem_middleware,
            subagent_middleware,
            summarization_middleware,
            MyMonitorMiddleware(enabled=False),
            retry_middleware,
        ],
        checkpointer=MemorySaver(),
        name="Tim_Leader",
    )

    run_config: RunnableConfig = {
        "tags": ["AgentBay Team"],
        "run_name": "Tim-测试",
        "configurable": {"thread_id": str(uuid.uuid4())}
    }

    # toy_game = """使用Python GUI开发一个简单的五子棋游戏。"""

    multi_turn_conversation(leader, run_config)
