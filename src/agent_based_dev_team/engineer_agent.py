import uuid

from deepagents import FilesystemMiddleware, SubAgentMiddleware, CompiledSubAgent
from deepagents.middleware import SkillsMiddleware, SummarizationMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware, HumanInTheLoopMiddleware
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from src.Tools import get_current_time, get_weather_at_location
from src.agent_based_dev_team.my_middleware import TeamLeaderMiddleware, MyMonitorMiddleware
from src.agent_based_dev_team.my_middleware_prompts import MY_TASK_TOOL_DESCRIPTION, \
    MY_TASK_PROMPT, MY_WRITE_TODOS_SYSTEM_PROMPT, MY_EXECUTE_TOOL_DESCRIPTION, MY_FILE_SYSTEM_MIDDLEWARE_SYSTEM_PROMPT
from src.config.llm import LLMs
from src.paths import AGENT_WORKSPACE, AGENT_SYSTEM_PROMPTS_FILES
from src.utils.fixed_local_shell_backend import FixedLocalShellBackend
from src.utils.roles_prompt_manager import get_system_prompt

my_backend = FixedLocalShellBackend(root_dir=AGENT_WORKSPACE, virtual_mode=True, inherit_env=True)

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

weather_agent = create_agent(
    model=LLMs["gpt-4o-mini"],
    tools=[get_weather_at_location],
    system_prompt="你是一名乐于助人的助手",
    name="Windy",
)

weather_subagent = CompiledSubAgent(
    name="weather_subagent",
    description="一个用于获取某个城市的天气的助手",
    runnable=weather_agent,
)

mySubAgentMiddleware = SubAgentMiddleware(backend=my_backend,
                                          subagents=[weather_subagent],
                                          system_prompt=MY_TASK_PROMPT,
                                          task_description=MY_TASK_TOOL_DESCRIPTION)

mySummarizationMiddleware = SummarizationMiddleware(LLMs["minimax-m2.7"], backend=my_backend)

myTeamLeaderMiddleware = TeamLeaderMiddleware()

myHITLMiddleware = HumanInTheLoopMiddleware(
    interrupt_on={
        "execute": True,
    }
)

engineer_sys_prompt = get_system_prompt("engineer", prompts_dir=AGENT_SYSTEM_PROMPTS_FILES)

engineer = create_agent(
    model=LLMs["minimax-m2.7"],
    tools=[get_current_time],
    system_prompt=engineer_sys_prompt,
    middleware=[
        myTodoListMiddleware,
        mySkillsMiddleware,
        myFilesystemMiddleware,
        mySubAgentMiddleware,
        mySummarizationMiddleware,
        myTeamLeaderMiddleware,
        myHITLMiddleware,
    ],  # type: ignore[arg-type]  # LangChain中间件泛型协变误报
    checkpointer=True,
    name="David_Engineer",
)

engineer_subagent = CompiledSubAgent(
    name="David",  # 在主智能体地系统提示词中显示的名字
    description="一名软件工程师，可根据明确的编码任务需求，交付功能性代码文件和测试代码文件，同时完成代码调试、单元测试、集成测试。",
    runnable=engineer,
)

if __name__ == "__main__":
    from src.utils.deep_agents_utils import multi_turn_conversation

    engineer = create_agent(
        model=LLMs["minimax-m2.7"],
        tools=[get_current_time],
        system_prompt=engineer_sys_prompt,
        middleware=[
            myTodoListMiddleware,
            mySkillsMiddleware,
            myFilesystemMiddleware,
            mySubAgentMiddleware,
            mySummarizationMiddleware,
            myTeamLeaderMiddleware,
            myHITLMiddleware,
            MyMonitorMiddleware(enabled=False)
        ],  # type: ignore[arg-type]  # LangChain中间件泛型协变误报
        checkpointer=MemorySaver(),
        name="David_Engineer",
    )

    run_config: RunnableConfig = {
        "tags": ["agent_based_dev_team", "Engineer"],
        "run_name": "Engineer-测试",
        "configurable": {"thread_id": str(uuid.uuid4())}
    }

    # toy_game = """使用Python GUI开发一个简单的五子棋游戏。"""

    multi_turn_conversation(engineer, run_config)
