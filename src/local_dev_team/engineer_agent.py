import uuid
from deepagents import SubAgentMiddleware, CompiledSubAgent
from deepagents.middleware import SkillsMiddleware
from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from src.Tools import get_current_time, get_weather_at_location
from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.my_middleware_prompts import MY_TASK_TOOL_DESCRIPTION, \
    MY_TASK_PROMPT
from src.custom_middleware.system_prompt_monitor import MyMonitorMiddleware
from src.local_dev_team.shared_middleware import retry_middleware, todo_list_middleware, filesystem_middleware, \
    summarization_middleware, HITL_middleware, my_local_backend
from src.paths import AGENT_SYSTEM_PROMPTS_FILES
from src.utils.roles_prompt_manager import get_system_prompt

mySkillsMiddleware = SkillsMiddleware(
    backend=my_local_backend,
    sources=["/skills/engineer"])

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

mySubAgentMiddleware = SubAgentMiddleware(backend=my_local_backend,
                                          subagents=[weather_subagent],
                                          system_prompt=MY_TASK_PROMPT,
                                          task_description=MY_TASK_TOOL_DESCRIPTION)

# 设置主干模型
llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]

engineer_sys_prompt = get_system_prompt("engineer", prompts_dir=AGENT_SYSTEM_PROMPTS_FILES)

engineer = create_agent(
    model=llm,
    tools=[get_current_time],
    system_prompt=engineer_sys_prompt,
    middleware=[
        todo_list_middleware,
        mySkillsMiddleware,
        filesystem_middleware,
        mySubAgentMiddleware,
        summarization_middleware,
        HITL_middleware,
        retry_middleware,  # ⭐ 重试中间件放在最内层，紧贴 LLM API 调用
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
            todo_list_middleware,
            mySkillsMiddleware,
            filesystem_middleware,
            mySubAgentMiddleware,
            summarization_middleware,
            HITL_middleware,
            MyMonitorMiddleware(enabled=False),
            retry_middleware,  # ⭐ 重试中间件放在最内层，重试中间件放在最内层，紧贴 LLM API 调用
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
