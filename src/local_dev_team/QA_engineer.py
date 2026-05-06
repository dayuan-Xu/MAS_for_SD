import uuid

from deepagents import CompiledSubAgent
from deepagents.middleware import SkillsMiddleware
from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from src.Tools import get_current_time
from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.dev_progress import TeamLeaderMiddleware
from src.custom_middleware.system_prompt_monitor import MyMonitorMiddleware
from src.local_dev_team.shared_middleware import retry_middleware, todo_list_middleware, filesystem_middleware, \
    summarization_middleware, HITL_middleware, my_local_backend
from src.paths import AGENT_SYSTEM_PROMPTS_FILES
from src.utils.roles_prompt_manager import get_system_prompt

mySkillsMiddleware = SkillsMiddleware(
    backend=my_local_backend,
    sources=["/skills/engineer"])

llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]

QA_engineer_sys_prompt = get_system_prompt("QA_engineer", prompts_dir=AGENT_SYSTEM_PROMPTS_FILES)

QA_engineer = create_agent(
    model=llm,
    tools=[get_current_time],
    system_prompt=QA_engineer_sys_prompt,
    middleware=[
        todo_list_middleware,
        mySkillsMiddleware,
        filesystem_middleware,
        summarization_middleware,
        HITL_middleware,
        retry_middleware,  # ⭐ 重试中间件放在最内层，重试中间件放在最内层，紧贴 LLM API 调用
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
    from src.utils.graph_running import multi_turn_conversation

    QA_engineer = create_agent(
        model=llm,
        tools=[get_current_time],
        system_prompt=QA_engineer_sys_prompt,
        middleware=[
            retry_middleware,  # ⭐ 重试中间件放在最外层，优先处理
            todo_list_middleware,
            mySkillsMiddleware,
            filesystem_middleware,
            summarization_middleware,
            TeamLeaderMiddleware(),
            HITL_middleware,
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
