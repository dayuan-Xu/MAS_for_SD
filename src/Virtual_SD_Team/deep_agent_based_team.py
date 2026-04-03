import uuid
from typing import Literal, Annotated

from deepagents import create_deep_agent, CompiledSubAgent
from deepagents.backends import FilesystemBackend, LocalShellBackend
from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from typing_extensions import NotRequired

from src.Tools import internet_search, get_current_time
from src.Virtual_SD_Team.manager import get_all_system_prompts
from src.config.llm import LLMs
from src.paths import DEEP_AGENT_WORKSPACE
from src.utils.deep_agents_utils import multi_turn_conversation

team_system_prompts = get_all_system_prompts()

product_manager_graph = create_deep_agent(
    model=LLMs["gpt-4o-mini"],
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["product_manager"],
    backend=FilesystemBackend(DEEP_AGENT_WORKSPACE, virtual_mode=True),
    interrupt_on={
        "internet_search": True,
    },
    name="Alice_ProductManager"
)
product_manager_subagent = CompiledSubAgent(
    name="product_manager_subagent",
    description="一名资深产品经理，可根据需求描述，产出一份产品需求文档。",
    runnable=product_manager_graph,
)

architect_graph = create_deep_agent(
    model=LLMs["gpt-4o-mini"],
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["architect"],
    backend=FilesystemBackend(DEEP_AGENT_WORKSPACE, virtual_mode=True),
    name="Bob_Architect"
)
architect_subagent = CompiledSubAgent(
    name="architect_subagent",
    description="一名资深架构师，可根据需求，进行技术框架选型，产出软件架构设计文档。",
    runnable=architect_graph,
)

project_manager_graph = create_deep_agent(
    model=LLMs["gpt-5-mini"],
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["project_manager"],
    backend=FilesystemBackend(DEEP_AGENT_WORKSPACE, virtual_mode=True),
    name="Cindy_ProjectManager"
)
project_manager_subagent = CompiledSubAgent(
    name="project_manager_subagent",
    description="一名资深项目经理，负责软件系统的详细设计，产出详细的接口文档。",
    runnable=project_manager_graph,
)

engineer_graph = create_deep_agent(
    model=LLMs["gpt-4o-mini"],
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["engineer"],
    backend=LocalShellBackend(root_dir=DEEP_AGENT_WORKSPACE, virtual_mode=True, inherit_env=True),
    interrupt_on={
        "execute": True,  # 为终端命令执行工具设置中断，如果虚拟文件系统是沙盒的话，可以不用指定interrupt_on，应该让智能体自由在沙盒中执行 execute 工具。
    },
    name="David_Engineer",
)
engineer_subagent = CompiledSubAgent(
    name="engineer_subagent",
    description="一名软件工程师，可根据明确的编码任务需求，产出功能性代码文件和测试代码文件，同时负责代码调试、单元测试、集成测试。",
    runnable=engineer_graph,
)

QA_engineer_graph = create_deep_agent(
    model=LLMs["gpt-4o-mini"],
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["QA_engineer"],
    backend=LocalShellBackend(root_dir=DEEP_AGENT_WORKSPACE, virtual_mode=True, inherit_env=True),
    interrupt_on={
        "execute": True,  # 为终端命令执行工具设置中断，如果虚拟文件系统是沙盒的话，可以不用指定interrupt_on，应该让智能体自由在沙盒中执行 execute 工具。
    },
    name="Eva_QA_Engineer",
)
QA_engineer_subagent = CompiledSubAgent(
    name="QA_engineer_subagent",
    description="一名软件测试员，可对指定的软件项目进行系统测试，并给出测试报告。",
    runnable=QA_engineer_graph,
)

subagents = [product_manager_subagent, architect_subagent, project_manager_subagent, engineer_subagent,
             QA_engineer_subagent]


class TeamLeaderState(AgentState):
    current_iteration: NotRequired[Annotated[int, "必须从1开始"]]
    current_iteration_stage: NotRequired[
        Literal["requirement_analysis", "system_design", "detailed_design", "code", "test"]]


class TeamLeaderMiddleware(AgentMiddleware[TeamLeaderState]):
    state_schema = TeamLeaderState


@tool
def update_dev_progress(current_iteration: int, current_iteration_stage: str, runtime: ToolRuntime) -> Command:
    """更新开发进度，进度包括当前迭代轮次和当前迭代阶段
    args:
    current_iteration: 当前迭代轮次，必须从 1 开始
    current_iteration_stage: 当前迭代阶段，可选值有：requirement_analysis, system_design, detailed_design, code, test
    """
    return Command(update={
        "current_iteration": current_iteration,
        "current_iteration_stage": current_iteration_stage,
        "messages": [ToolMessage(
            content=f"成功更新开发进度！当前迭代轮次为：{current_iteration}，当前迭代阶段为：{current_iteration_stage}",
            tool_call_id=runtime.tool_call_id)]
    })


leader = create_deep_agent(
    model=LLMs["gpt-5-mini"],
    tools=[get_current_time, update_dev_progress],
    system_prompt=team_system_prompts["team_leader"],
    middleware=[TeamLeaderMiddleware()],
    checkpointer=MemorySaver(),
    backend=LocalShellBackend(root_dir=DEEP_AGENT_WORKSPACE, virtual_mode=True, inherit_env=True),
    interrupt_on={
        "execute": True,  # 为终端命令执行工具设置中断，如果虚拟文件系统是沙盒的话，可以不用指定interrupt_on，应该让智能体自由在沙盒中执行 execute 工具。
    },
    subagents=subagents,
    skills=["/skills/solution-evaluation"],
    name="Tim_Leader",
)

run_config: RunnableConfig = {
    "tags": ["Virtual_Dev_Team"],
    "run_name": "简单五子棋",
    "configurable": {"thread_id": str(uuid.uuid4())}
}

if __name__ == "__main__":
    # toy_game = """使用Python GUI开发一个简单的五子棋游戏。"""

    multi_turn_conversation(leader, run_config)
