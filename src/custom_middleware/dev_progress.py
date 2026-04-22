from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from typing import Literal, Annotated
from typing_extensions import NotRequired


class TeamLeaderState(AgentState):
    current_iteration: NotRequired[Annotated[int, "必须从1开始"]]
    current_iteration_stage: NotRequired[
        Literal["requirement_analysis", "system_design", "detailed_design", "coding", "testing"]]


@tool
def update_dev_progress(current_iteration: int, current_iteration_stage: str, runtime: ToolRuntime) -> Command:
    """更新开发进度，进度包括当前迭代轮次和当前迭代阶段
    args:
    current_iteration: 当前迭代轮次，必须从 1 开始
    current_iteration_stage: 当前迭代阶段，可选值有：requirement_analysis, system_design, detailed_design, coding, testing
    """
    return Command(update={
        "current_iteration": current_iteration,
        "current_iteration_stage": current_iteration_stage,
        "messages": [ToolMessage(
            content=f"成功更新开发进度！当前迭代轮次为：{current_iteration}，当前迭代阶段为：{current_iteration_stage}",
            tool_call_id=runtime.tool_call_id)]
    })


class TeamLeaderMiddleware(AgentMiddleware[TeamLeaderState]):
    state_schema = TeamLeaderState
    tools = [update_dev_progress]
