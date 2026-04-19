import uuid
from deepagents import FilesystemMiddleware, CompiledSubAgent
from deepagents.middleware import SkillsMiddleware, SummarizationMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware, HumanInTheLoopMiddleware
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from src.Tools import get_current_time
from src.agent_based_dev_team.my_middleware import TeamLeaderMiddleware, MyMonitorMiddleware
from src.agent_based_dev_team.my_middleware_prompts import MY_WRITE_TODOS_SYSTEM_PROMPT, MY_EXECUTE_TOOL_DESCRIPTION, \
    MY_FILE_SYSTEM_MIDDLEWARE_SYSTEM_PROMPT
from src.agent_based_dev_team.shared_middleware import shared_retry_middleware
from src.config.llm import LLMs
from src.config.settings import settings
from src.paths import LOCAL_AGENT_WORKSPACE, AGENT_SYSTEM_PROMPTS_FILES
from src.utils.fixed_local_shell_backend import FixedLocalShellBackend
from src.utils.roles_prompt_manager import get_system_prompt

my_backend = FixedLocalShellBackend(root_dir=LOCAL_AGENT_WORKSPACE, virtual_mode=True, inherit_env=True)

myTodoListMiddleware = TodoListMiddleware(system_prompt=MY_WRITE_TODOS_SYSTEM_PROMPT)

mySkillsMiddleware = SkillsMiddleware(
    backend=my_backend,
    sources=["/skills/engineer"])

# Middleware for providing filesystem and optional execution tools to an agent.
myFilesystemMiddleware = FilesystemMiddleware(
    backend=my_backend,  # Optional: custom backend (defaults to StateBackend)
    system_prompt=MY_FILE_SYSTEM_MIDDLEWARE_SYSTEM_PROMPT,
    custom_tool_descriptions={
        "execute": MY_EXECUTE_TOOL_DESCRIPTION,
    }  # Optional: Custom descriptions for filesystem tools
)

llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]

mySummarizationMiddleware = SummarizationMiddleware(llm, backend=my_backend)

myTeamLeaderMiddleware = TeamLeaderMiddleware()

myHITLMiddleware = HumanInTheLoopMiddleware(
    interrupt_on={
        "execute": True,
    }
)

QA_engineer_sys_prompt = get_system_prompt("QA_engineer", prompts_dir=AGENT_SYSTEM_PROMPTS_FILES)

QA_engineer = create_agent(
    model=llm,
    tools=[get_current_time],
    system_prompt=QA_engineer_sys_prompt,
    middleware=[
        myTodoListMiddleware,
        mySkillsMiddleware,
        myFilesystemMiddleware,
        mySummarizationMiddleware,
        myTeamLeaderMiddleware,
        myHITLMiddleware,
        shared_retry_middleware,  # ⭐ 重试中间件放在最内层，重试中间件放在最内层，紧贴 LLM API 调用
    ],  # type: ignore[arg-type]  # LangChain中间件泛型协变误报
    checkpointer=True,
    name="Eva_QA_Engineer",
)

QA_engineer_subagent = CompiledSubAgent(
    name="Eva",
    description="一名软件测试员，可对指定的软件项目进行系统测试，交付一份系统测试报告。",
    runnable=QA_engineer,
)

if __name__ == "__main__":
    from src.utils.graph_running_utils import multi_turn_conversation

    QA_engineer = create_agent(
        model=llm,
        tools=[get_current_time],
        system_prompt=QA_engineer_sys_prompt,
        middleware=[
            shared_retry_middleware,  # ⭐ 重试中间件放在最外层，优先处理
            myTodoListMiddleware,
            mySkillsMiddleware,
            myFilesystemMiddleware,
            mySummarizationMiddleware,
            myTeamLeaderMiddleware,
            myHITLMiddleware,
            MyMonitorMiddleware(enabled=False)
        ],  # type: ignore[arg-type]  # LangChain中间件泛型协变误报
        checkpointer=MemorySaver(),
        name="Eva",
    )

    run_config: RunnableConfig = {
        "tags": ["agent_based_dev_team", "QA-Engineer"],
        "run_name": "QA_Engineer-测试",
        "configurable": {"thread_id": str(uuid.uuid4())}
    }

    # toy_game = """使用Python GUI开发一个简单的五子棋游戏。"""

    multi_turn_conversation(QA_engineer, run_config)
