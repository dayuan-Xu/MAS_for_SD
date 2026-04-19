import uuid
from deepagents import FilesystemMiddleware, SubAgentMiddleware, CompiledSubAgent
from deepagents.middleware import SkillsMiddleware, SummarizationMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from src.Tools import get_current_time, get_weather_at_location
from src.agent_based_dev_team.my_middleware import MyMonitorMiddleware
from src.agent_based_dev_team.my_middleware_prompts import MY_TASK_TOOL_DESCRIPTION, \
    MY_TASK_PROMPT, MY_WRITE_TODOS_SYSTEM_PROMPT
from src.agent_based_dev_team.shared_middleware import shared_retry_middleware
from src.agentbay_based_dev_team.my_sandbox import MySandbox
from src.config.llm import LLMs
from src.config.settings import settings
from src.paths import AGENT_SYSTEM_PROMPTS_FILES
from src.utils.roles_prompt_manager import get_system_prompt

my_sandbox_backend = MySandbox()

myTodoListMiddleware = TodoListMiddleware(system_prompt=MY_WRITE_TODOS_SYSTEM_PROMPT)

mySkillsMiddleware = SkillsMiddleware(
    backend=my_sandbox_backend,
    sources=["/tmp/persistent/team_skills/engineer"])

# Middleware for providing filesystem and optional execution tools to an agent.
myFilesystemMiddleware = FilesystemMiddleware(backend=my_sandbox_backend)

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

mySubAgentMiddleware = SubAgentMiddleware(backend=my_sandbox_backend,
                                          subagents=[weather_subagent],
                                          system_prompt=MY_TASK_PROMPT,
                                          task_description=MY_TASK_TOOL_DESCRIPTION)

# 设置主干模型
llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]

mySummarizationMiddleware = SummarizationMiddleware(llm, backend=my_sandbox_backend)

engineer_sys_prompt = get_system_prompt("engineer", prompts_dir=AGENT_SYSTEM_PROMPTS_FILES)

engineer = create_agent(
    model=llm,
    tools=[get_current_time],
    system_prompt=engineer_sys_prompt,
    middleware=[
        myTodoListMiddleware,
        mySkillsMiddleware,
        myFilesystemMiddleware,
        mySubAgentMiddleware,
        mySummarizationMiddleware,
        shared_retry_middleware,  # ⭐ 重试中间件放在最内层，紧贴 LLM API 调用
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
    from src.utils.graph_running_utils import multi_turn_conversation

    engineer = create_agent(
        model=llm,
        tools=[get_current_time],
        system_prompt=engineer_sys_prompt,
        middleware=[
            myTodoListMiddleware,
            mySkillsMiddleware,
            myFilesystemMiddleware,
            mySubAgentMiddleware,
            mySummarizationMiddleware,
            MyMonitorMiddleware(enabled=False),
            shared_retry_middleware,  # ⭐ 重试中间件放在最内层，重试中间件放在最内层，紧贴 LLM API 调用
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
