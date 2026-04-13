import uuid

from deepagents import FilesystemMiddleware, SubAgentMiddleware
from deepagents.middleware import SkillsMiddleware, SummarizationMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware, HumanInTheLoopMiddleware
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from src.Tools import get_current_time
from src.agent_based_dev_team.my_middleware import TeamLeaderMiddleware
from src.agent_based_dev_team.my_middleware_prompts import MY_EXECUTE_TOOL_DESCRIPTION, MY_TASK_PROMPT, \
    MY_TASK_TOOL_DESCRIPTION, \
    MY_WRITE_TODOS_SYSTEM_PROMPT, MY_FILE_SYSTEM_MIDDLEWARE_SYSTEM_PROMPT
from src.agent_based_dev_team.team_experts import subagents
from src.config.llm import LLMs
from src.paths import AGENT_WORKSPACE, AGENT_SYSTEM_PROMPTS_FILES
from src.utils.fixed_local_shell_backend import FixedLocalShellBackend
from src.utils.roles_prompt_manager import get_system_prompt

my_backend = FixedLocalShellBackend(root_dir=AGENT_WORKSPACE, virtual_mode=True, inherit_env=True)

myTodoListMiddleware = TodoListMiddleware(system_prompt=MY_WRITE_TODOS_SYSTEM_PROMPT)

mySkillsMiddleware = SkillsMiddleware(
    backend=my_backend,
    sources=["/skills/leader/"])

# Middleware for providing filesystem and optional execution tools to an agent.
myFilesystemMiddleware = FilesystemMiddleware(
    backend=my_backend,  # Optional: custom backend (defaults to StateBackend)
    system_prompt=MY_FILE_SYSTEM_MIDDLEWARE_SYSTEM_PROMPT,
    custom_tool_descriptions={
        "execute": MY_EXECUTE_TOOL_DESCRIPTION,
    }  # Optional: Custom descriptions for filesystem tools
)

mySubAgentMiddleware = SubAgentMiddleware(backend=my_backend,
                                          subagents=subagents,
                                          system_prompt=MY_TASK_PROMPT,
                                          task_description=MY_TASK_TOOL_DESCRIPTION)

mySummarizationMiddleware = SummarizationMiddleware(LLMs["minimax-m2.7"], backend=my_backend)

myTeamLeaderMiddleware = TeamLeaderMiddleware()

myHITLMiddleware = HumanInTheLoopMiddleware(
    interrupt_on={
        "execute": True,
    }
)
leader_sys_prompt = get_system_prompt("team_leader", prompts_dir=AGENT_SYSTEM_PROMPTS_FILES)
leader = create_agent(
    model=LLMs["minimax-m2.7"],
    tools=[get_current_time],
    system_prompt=leader_sys_prompt,
    middleware=[
        myTodoListMiddleware,
        mySkillsMiddleware,
        myFilesystemMiddleware,
        mySubAgentMiddleware,
        mySummarizationMiddleware,
        myTeamLeaderMiddleware,
        myHITLMiddleware
    ],  # type: ignore[arg-type]  # LangChain中间件泛型协变误报
    checkpointer=MemorySaver(),
    name="Tim",
)

if __name__ == "__main__":
    from src.utils.deep_agents_utils import multi_turn_conversation

    run_config: RunnableConfig = {
        "tags": ["agent_based_dev_team", "Leader"],
        "run_name": "Leader-测试-五子棋",
        "configurable": {"thread_id": str(uuid.uuid4())}
    }

    # toy_game = """使用Python GUI开发一个简单的五子棋游戏。"""

    multi_turn_conversation(leader, run_config)
