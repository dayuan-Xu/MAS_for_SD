# 1. 参考资料：langchain内置的SubAgentMiddleware，位于.venv/Lib/site-packages/deepagents/middleware/subagents.py
# 2。 核心需求：
# 基于SubAgentMiddleware在src/custom_middleware/assign.py，
# 实现一个AssignMiddleware，提供一个assign工具，后续装配给leader（src/remote_dev_team/leader.py:66），
# 从而允许leader只做为一个协调组织者，负责将软件开发中的某个阶段性任务，信任地委派给其他成员智能体（比如David、Cindy、Alice、Eva）去完成。
# 同时配分配到阶段性任务地智能体，有些是必须具备长期记忆的，因此这些智能体在creat_agent创建时必须使checkpointer为True，
# 以此显式指明被调用的智能体专家可以使用，leader所用的那个thread id，以便它们在leader多次调用assign工具多次分配任务之间保持记忆。
# 即通过assign调用的团队专家，可以在多次assign间保持记忆。
import logging
from deepagents import CompiledSubAgent
from deepagents.middleware.subagents import _SubagentSpec, _EXCLUDED_STATE_KEYS
from langchain.agents.middleware.types import AgentMiddleware, ContextT, ModelRequest, ModelResponse, ResponseT
from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing import Any, Sequence, cast, Callable

from src.remote_dev_team.dev_team_wo_task_context.team_experts import team_experts_list


# 3. 需求产生原因：
# langchain内置的SubAgentMiddleware核心是为智能体提供task工具，用于主调智能体将一些复杂多步骤任务上下文交给一个短暂存在的subagent处理，同时隔离这部分上下文，只获取最终成果。
# 但是这个中间件对系统提示词的注入内容、提供的task工具的工具描述和工具参数schema中对task工具入参的描述，不太符合我想要的assign工具的特征！！！
# 满足我的需求的必须实现点：
# 实现AssignMiddleware，
# 重写：
# 1、task工具入参schema，表明只需要description一个简短的任务描述和expert_name专家名字。
# 2、系统提示词注入部分，介绍assign工具可分配任务的智能体专家的名字，替换SubAgen在提示词中t注入的available subagents。
# 4. 预期效果：
# AssignMiddleware实现的assign工具做为双智能体间（leader和其他智能体专家间）的交流工具，每次assign直接触发被分配的智能体的一次运行。
# 即不仅leader可以通过task和其他团队成员通信，engineer也可以通过该工具和其他团队成员（比如前驱成员）进行通讯。


# 3. 需求产生原因：
# langchain内置的SubAgentMiddleware核心是为智能体提供task工具，用于主调智能体将一些复杂多步骤任务上下文交给一个短暂存在的subagent处理，同时隔离这部分上下文，只获取最终成果。
# 但是这个中间件对系统提示词的注入内容、提供的task工具的工具描述和工具参数schema中对task工具入参的描述，不太符合我想要的assign工具的特征！！！
# 满足我的需求的必须实现点：
# 实现AssignMiddleware，
# 重写：
# 1、task工具入参schema，表明只需要description一个简短的任务描述和expert_name专家名字。
# 2、系统提示词注入部分，介绍assign工具可分配任务的智能体专家的名字，替换SubAgen在提示词中t注入的available subagents。


class AssignToolSchema(BaseModel):
    """Assign工具的输入参数Schema，简化为任务描述和专家名称。"""
    description: str = Field(
        description=("A concise description of the task to be assigned to the expert agent."
                     "如果是指派专家智能体产出文档交付物，不必明确指明文档的内容应该包含哪些章节，相信你的团队成员是专业的！")
    )
    expert_name: str = Field(
        description="The name of the expert agent to assign the task to (e.g., 'David', 'Eva', 'Alice')."
    )


ASSIGN_TOOL_DESCRIPTION = """Assign a task to a specific expert agent in the development team.

This tool allows you to assign specific development tasks to specialized team members.
The expert agent will execute the task and report the results.
Besides, you can also just use it as a communication tool.

Available experts:
{available_experts}

Usage notes:
1. Be clear and specific about what you want the expert to accomplish. 
2. Some expert agents can maintain context across multiple assignments.
3. Use this tool to leverage the specialized skills of each team member.
4. 目前不支持针对同一专家智能体并行化调用assign，你不能同时通过assign调用同一个专家智能体。
5."""  # noqa: E501

ASSIGN_SYSTEM_PROMPT = """## `assign` (team collaboration tool)

You have access to an `assign` tool to assign tasks to specialized expert agents in your development team.

When to use the assign tool:
- When a task requires specialized expertise (coding, testing, product management, etc.)
- When you need to assign a specific development (stage) task to a team member
- When you want to discuss or debate with one of your team members

How to use:
1. Specify the task clearly in the `description` parameter
2. Choose the appropriate expert by their `expert_name`

Remember: Some expert agents maintain memory across multiple assignments, so they can build on previous work."""  # noqa: E501


def _build_assign_tool(
        experts: list[_SubagentSpec],
) -> StructuredTool:
    """构建assign工具，支持向专家团队委派任务。
    
    Args:
        experts: 专家智能体规格列表
        
    Returns:
        结构化的assign工具
    """
    # 构建专家图谱字典和描述字符串
    expert_graphs: dict[str, Any] = {spec["name"]: spec["runnable"] for spec in experts}
    expert_description_str = "\n".join(f"- {s['name']}: {s['description']}" for s in experts)

    # 格式化描述文本
    description = ASSIGN_TOOL_DESCRIPTION.format(available_experts=expert_description_str)

    def _return_command_with_state_update(result: dict, tool_call_id: str) -> Command:
        """处理专家执行结果并返回Command对象。"""
        if "messages" not in result:
            error_msg = (
                "Expert agent must return a state containing a 'messages' key. "
                "Custom StateGraphs used with CompiledSubAgent should include 'messages' "
                "in their state schema to communicate results back to the main agent."
            )
            raise ValueError(error_msg)

        # 过滤掉不需要传递的状态键
        state_update = {k: v for k, v in result.items() if k not in _EXCLUDED_STATE_KEYS}

        # 提取最后一条消息的文本内容
        message_text = result["messages"][-1].text.rstrip() if result["messages"][-1].text else ""

        return Command(
            update={
                **state_update,
                "messages": [ToolMessage(message_text, tool_call_id=tool_call_id)],
            }
        )

    def _validate_and_prepare_state(expert_name: str, description: str, runtime: Any) -> tuple[Any, dict]:
        """验证专家名称并准备调用状态。"""
        if expert_name not in expert_graphs:
            allowed_names = ", ".join([f"`{k}`" for k in expert_graphs])
            raise ValueError(
                f"Expert '{expert_name}' does not exist. Available experts: {allowed_names}"
            )

        expert = expert_graphs[expert_name]

        # 创建新的状态字典，避免修改原始状态
        expert_state = {k: v for k, v in runtime.state.items() if k not in _EXCLUDED_STATE_KEYS}
        expert_state["messages"] = [HumanMessage(content=description)]

        return expert, expert_state

    def assign(
            description: str,
            expert_name: str,
            runtime: ToolRuntime,
    ) -> str | Command:
        """同步版本的assign函数。"""
        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for expert assignment")

        expert, expert_state = _validate_and_prepare_state(expert_name, description, runtime)
        result = expert.invoke(expert_state)
        return _return_command_with_state_update(result, runtime.tool_call_id)

    async def aassign(
            description: str,
            expert_name: str,
            runtime: ToolRuntime,
    ) -> str | Command:
        """异步版本的assign函数。"""
        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for expert assignment")

        expert, expert_state = _validate_and_prepare_state(expert_name, description, runtime)
        result = await expert.ainvoke(expert_state)
        return _return_command_with_state_update(result, runtime.tool_call_id)

    return StructuredTool.from_function(
        name="assign",
        func=assign,
        coroutine=aassign,
        description=description,
        infer_schema=False,
        args_schema=AssignToolSchema,
    )


class AssignMiddleware(AgentMiddleware[Any, ContextT, ResponseT]):
    """自定义的任务委派中间件，提供assign工具用于向专家团队委派任务。
    
    与标准的SubAgentMiddleware不同，AssignMiddleware:
    1. 使用简化的参数schema（description + expert_name）
    2. 提供更适合团队协作的系统提示词
    3. 专门针对具有长期记忆的专家智能体优化
    
    Example:
        ```python
        from src.custom_middleware.assign import AssignMiddleware
        from src.remote_dev_team.team_experts import team_experts
        
        leader = create_agent(
            model=llm,
            middleware=[
                AssignMiddleware(
                    backend=my_backend,
                    experts=team_experts,
                ),
                # ... other middleware
            ],
        )
        ```
    """

    def __init__(
            self,
            *,
            experts: Sequence[CompiledSubAgent] | None = None,
            system_prompt: str | None = ASSIGN_SYSTEM_PROMPT,
            **kwargs: Any,
    ) -> None:
        """初始化AssignMiddleware。
        
        Args:
            experts: 专家团队列表，默认为team_experts中定义的所有专家
            system_prompt: 自定义系统提示词，默认为ASSIGN_SYSTEM_PROMPT
            **kwargs: 传递给父类SubAgentMiddleware的其他参数
        """
        self.logger = logging.getLogger(__name__)

        # 如果没有提供专家列表，使用默认的team_experts
        if experts is None:
            experts = team_experts_list

        # 将CompiledSubAgent转换为内部规格格式
        expert_specs: list[_SubagentSpec] = []
        for expert in experts:
            compiled = cast("CompiledSubAgent", expert)
            expert_specs.append({
                "name": compiled["name"],
                "description": compiled["description"],
                "runnable": compiled["runnable"]
            })

        # 构建assign工具
        assign_tool = _build_assign_tool(expert_specs)

        self.logger.info(f"✅ AssignMiddleware 初始化完成，已注册 {len(expert_specs)} 个专家")

        # 构建系统提示词
        if system_prompt and expert_specs:
            experts_desc = "\n".join(f"- {s['name']}: {s['description']}" for s in expert_specs)
            self.system_prompt = system_prompt + "\n\nAvailable experts:\n" + experts_desc
        else:
            self.system_prompt = system_prompt

        # 设置工具列表
        self.tools = [assign_tool]

    def wrap_model_call(
            self,
            request: ModelRequest[ContextT],
            handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        """更新系统消息以包含assign工具的使用说明。"""
        from deepagents.middleware._utils import append_to_system_message

        if self.system_prompt is not None:
            new_system_message = append_to_system_message(request.system_message, self.system_prompt)
            return handler(request.override(system_message=new_system_message))
        return handler(request)

    async def awrap_model_call(
            self,
            request: ModelRequest[ContextT],
            handler: Callable[[ModelRequest[ContextT]], Any],
    ) -> ModelResponse[ResponseT]:
        """(异步) 更新系统消息以包含assign工具的使用说明。"""
        from deepagents.middleware._utils import append_to_system_message

        if self.system_prompt is not None:
            new_system_message = append_to_system_message(request.system_message, self.system_prompt)
            return await handler(request.override(system_message=new_system_message))
        return await handler(request)
