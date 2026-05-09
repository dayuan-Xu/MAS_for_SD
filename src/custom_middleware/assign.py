# 1. 参考资料：langchain内置的SubAgentMiddleware，位于.venv/Lib/site-packages/deepagents/middleware/subagents.py
# 2。 核心需求：
# 基于SubAgentMiddleware在src/custom_middleware/assign.py，
# 实现一个AssignMiddleware，提供一个assign工具，后续装配给leader（src/dev_team/leader.py:66），
# 从而允许leader只做为一个协调组织者，负责将软件开发中的某个阶段性任务，信任地委派给其他成员智能体（比如David、Cindy、Alice、Eva）去完成。
# 同时配分配到阶段性任务地智能体，有些是必须具备长期记忆的，因此这些智能体在creat_agent创建时必须使checkpointer为True，
# 以此显式指明被调用的智能体专家可以使用，leader所用的那个thread id，以便它们在leader多次调用assign工具多次分配任务之间保持记忆。
# 即通过assign调用的团队专家，可以在多次assign间保持记忆。
import asyncio
import logging
import threading
from typing import Any, Sequence, Callable, NotRequired, TypedDict

from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware.types import AgentMiddleware, AgentState, ContextT, ModelRequest, ModelResponse, \
    ResponseT
from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import StructuredTool
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing_extensions import Annotated


class CompiledExpertAgent(TypedDict):
    """A pre-compiled agent spec.

    !!! note

        The runnable's state schema must include a 'messages' key.

        This is required for the expert agent to communicate results back to the main agent.

    When the sexpert agent completes, the final message in the 'messages' list will be
    extracted and returned as a `ToolMessage` to the leader agent.
    """

    name: str
    """Unique identifier for the expert agent."""

    description: str
    """What this expert agent does."""

    runnable: Runnable
    """A custom agent implementation.

    Create a custom agent using either:

    1. LangChain's [`create_agent()`](https://docs.langchain.com/oss/python/langchain/quickstart)
    2. A custom graph using [`langgraph`](https://docs.langchain.com/oss/python/langgraph/quickstart)

    If you're creating a custom graph, make sure the state schema includes a 'messages' key.
    This is required for the expert agent to communicate results back to the leader agent.
    """


def create_compiled_expert_agent(agent, description: str):
    return CompiledExpertAgent(
        name=agent.name,
        runnable=agent,
        description=description
    )


class _ExpertAgentSpec(TypedDict):
    """Internal spec for building the assign tool."""

    name: str
    description: str
    runnable: Runnable


def _merge_expert_states(left: dict, right: dict) -> dict:
    """合并两个专家状态字典。
    
    用于处理并行 assign 调用时的状态更新冲突。
    如果同一个专家的图状态在左右两个字典中都存在，右边字典中的会覆盖左边字典中的（后执行的获胜）。
    
    Args:
        left: 第一个状态字典
        right: 第二个状态字典，可能包含某个专家的最新图状态
        
    Returns:
        合并后的状态字典
    """
    merged = dict(left)
    merged.update(right)
    return merged


class AssignState(AgentState):
    """AssignMiddleware 的状态 Schema。
    
    包含一个 expert_states 字典，用于存储每个专家的完整状态。
    这样可以在多次 assign 调用之间保持专家的长期记忆，同时完全隔离不同专家的上下文。
    """
    expert_states: NotRequired[Annotated[dict[str, AgentState], _merge_expert_states]]
    """每个专家的完整状态字典。键为专家名称，值为 AgentState。使用自定义 reducer 支持并行更新。"""


# 3. 需求产生原因：
# langchain内置的SubAgentMiddleware核心是为智能体提供task工具，用于主调智能体将一些复杂多步骤任务上下文交给一个短暂存在的subagent处理，同时隔离这部分上下文，只获取最终成果。
# 但是这个中间件对系统提示词的注入内容、提供的task工具的工具描述和工具参数schema中对task工具入参的描述，不太符合我想要的assign工具的特征！！！
# 满足我的需求的必须实现点：
# 实现AssignMiddleware，
# 重写：
# 1、task工具入参schema，表明只需要private_message一个简短的任务描述和expert_name专家名字。
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
# 1、task工具入参schema，表明只需要private_message一个简短的任务描述和expert_name专家名字。
# 2、系统提示词注入部分，介绍assign工具可分配任务的智能体专家的名字，替换SubAgen在提示词中t注入的available subagents。


class AssignToolSchema(BaseModel):
    """Assign工具的输入参数Schema，简化为专家名称和消息。"""
    expert_name: str = Field(
        description="The name of the expert agent to assign the task to (e.g., 'David', 'Eva', 'Alice')."
    )

    private_message: str = Field(
        description=("A message containing the concise task description that will be sent to the expert agent."
                     "If是指派专家智能体产出文档交付物，不必明确指明文档的内容应该包含哪些章节，相信你的团队成员的老道经验！")
    )


ASSIGN_TOOL_DESCRIPTION = """Assign a task to a specific expert agent in the development team.

This tool allows you to assign specific development tasks to specialized team members.
The expert agent will execute the task and report the results.
Besides, you can also just use it as a communication tool between you and the other.

Available experts:
{available_experts}

Usage notes:
1. Be clear and specific about what you want the expert to accomplish. 
2. All expert agents can maintain context across multiple assignments.
3. Use this tool to leverage the specialized skills of each team member.
4. 目前不支持针对同一专家智能体并行调用assign，即你不能同时多次assign同一个专家智能体，但是你具备同时assign不同专家智能体的能力。"""  # noqa: E501

ASSIGN_SYSTEM_PROMPT = """## `assign` (team collaboration tool)

You have access to an `assign` tool to assign tasks to specialized expert agents in your development team.

When to use the assign tool:
- When a task requires specialized expertise (coding, testing, product management, etc.)
- When you need to assign a specific development (stage) task to a team member
- When you want to discuss or debate with one of your team members, use it as a communication tool

How to use:
1. Specify the task clearly in the `private_message` parameter
2. Choose the appropriate expert by their `expert_name`

Remember: All expert agents maintain memory across multiple assignments, so they can build on previous work."""  # noqa: E501


def _build_assign_tool(
        experts: list[_ExpertAgentSpec],
) -> StructuredTool:
    """构建assign工具，支持向专家团队委派任务。
    
    Args:
        experts: 专家智能体规格列表
        
    Returns:
        结构化的assign工具
    """
    logger = logging.getLogger(__name__)

    # ⭐ 为每个专家创建一个线程锁，用于防止同一专家的并行调用
    expert_locks: dict[str, threading.Lock] = {spec["name"]: threading.Lock() for spec in experts}
    # ⭐ 为每个专家创建一个 asyncio 锁，用于异步版本
    expert_async_locks: dict[str, asyncio.Lock] = {spec["name"]: asyncio.Lock() for spec in experts}

    # 构建专家图谱字典和描述字符串
    expert_graphs: dict[str, Any] = {spec["name"]: spec["runnable"] for spec in experts}
    expert_description_str = "\n".join(f"- {s['name']}: {s['description']}" for s in experts)

    # 格式化描述文本
    description = ASSIGN_TOOL_DESCRIPTION.format(available_experts=expert_description_str)

    def _return_command_with_state_update(expert_name, expert_state: dict, runtime: ToolRuntime) -> Command:
        """处理专家执行结果并返回Command对象。
        
        ⭐ 关键修复：只返回当前专家的更新，而不是整个 expert_states 字典
        这样 LangGraph 的 reducer 函数可以正确合并多个并行调用的结果
        """
        if "messages" not in expert_state:
            error_msg = (
                "Expert agent must return a state containing a 'messages' key. "
                "Custom StateGraphs used with CompiledExpertAgent should include 'messages' "
                "in their state schema to communicate results back to the main agent."
            )
            raise ValueError(error_msg)

        # 提取最后一条消息的文本内容，作为返回给主调智能体
        last_message = expert_state["messages"][-1]
        message_text = getattr(last_message, 'content', '') or getattr(last_message, 'text', '')
        if message_text:
            message_text = message_text.rstrip()

        # ⭐ 关键修复：只返回当前专家的键值对，让 reducer 函数合并
        return Command(
            update={
                "expert_states": {expert_name: expert_state},  # 只返回单个专家的更新
                "messages": [ToolMessage(message_text, tool_call_id=runtime.tool_call_id)],
            }
        )

    def _validate_and_prepare_state(expert_name: str, private_message: str, runtime: Any) -> tuple[Any, dict[Any, Any]]:
        """验证专家名称并准备调用状态。
        
        ⭐ 关键：直接从 Leader 状态的 expert_states 中读取专家的完整状态
        
        Returns:
            tuple: (expert runnable, expert state, expert config)
        """
        if expert_name not in expert_graphs:
            allowed_names = ", ".join([f"`{k}`" for k in expert_graphs])
            raise ValueError(
                f"Expert '{expert_name}' does not exist. Available experts: {allowed_names}"
            )

        expert = expert_graphs[expert_name]

        # ⭐ 关键：直接从 Leader 状态中读取当前专家的完整状态
        expert_states = runtime.state.get("expert_states", {})
        expert_saved_state = expert_states.get(expert_name)

        if expert_saved_state:
            # 专家有保存的状态，直接引用以复用
            expert_state = expert_saved_state
            existing_messages = expert_state.get("messages", [])
            expert_state["messages"] = existing_messages + [HumanMessage(content=private_message)]
        else:
            # 第一次调用该专家，创建空状态
            expert_state = {"messages": [HumanMessage(content=private_message)]}

        return expert, expert_state

    def assign(
            private_message: str,
            expert_name: str,
            runtime: ToolRuntime,
    ) -> str | Command:
        """同步版本的assign函数。
        
        ⭐ 使用线程锁防止同一专家的并行调用，如果检测到并发则直接返回错误
        """
        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for expert assignment")

        # ⭐ 获取该专家的锁
        lock = expert_locks.get(expert_name)
        if not lock:
            raise ValueError(f"Expert '{expert_name}' not found in locks")

        # ⭐ 尝试非阻塞获取锁，如果失败说明有并发调用，直接返回错误
        acquired = lock.acquire(blocking=False)
        if not acquired:
            logger.warning(
                f"⚠️ 检测到并发调用：专家 '{expert_name}' 正在执行另一个任务。"
                f"不支持对同一专家智能体并行调用 assign，请顺序调用。"
            )
            # 直接返回错误消息，不阻塞等待
            return Command(
                update={
                    "messages": [ToolMessage(
                        content=f"❌ 错误：专家 '{expert_name}' 正在执行另一个任务。不支持对同一专家智能体并行调用 assign。请等待当前任务完成后再调用，或指派其他专家。",
                        tool_call_id=runtime.tool_call_id
                    )]
                }
            )

        try:
            expert, expert_state = _validate_and_prepare_state(expert_name, private_message, runtime)
            logger.debug(f"开始执行专家 {expert_name} 的任务...")

            # 值得注意的是，expert是一个编译时没有传入checkpointer的已编译状态图，所以每次运行完全可以视为是**单论对话**！
            # 因此此处传入的 runtime.config中是否包含thread_id对于本次expert的invoke来说没有意义！
            # 其中别的配置可能有意义
            expert_state = expert.invoke(expert_state, config=runtime.config)

            logger.debug(f"专家 {expert_name} 任务执行完成")
            return _return_command_with_state_update(expert_name, expert_state, runtime)
        except Exception as e:
            logger.error(f"专家 {expert_name} 执行失败: {e}", exc_info=True)
            return Command(
                update={
                    "messages": [ToolMessage(
                        f"专家 {expert_name} 执行失败: {str(e)}",
                        tool_call_id=runtime.tool_call_id
                    )]
                }
            )
        finally:
            # ⭐ 释放锁
            lock.release()

    async def aassign(
            private_message: str,
            expert_name: str,
            runtime: ToolRuntime,
    ) -> str | Command:
        """异步版本的assign函数。
        
        ⭐ 使用 asyncio 锁防止同一专家的并行调用
        """

        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for expert assignment")

        # ⭐ 获取该专家的 asyncio 锁
        lock = expert_async_locks.get(expert_name)
        if not lock:
            raise ValueError(f"Expert '{expert_name}' not found in async locks")

        # ⭐ 尝试获取锁，如果锁已被占用，说明有并发调用
        try:
            acquired = lock.acquire(False)  # 非阻塞尝试
            if not acquired:
                logger.warning(
                    f"⚠️ 检测到并发调用：专家 '{expert_name}' 正在执行另一个任务。"
                    f"当前调用将被阻塞，直到前一个任务完成。建议避免同时多次 assign 同一个专家。"
                )
                # 阻塞等待锁释放
                await lock.acquire()
            else:
                # 成功获取锁，需要手动释放（因为 acquire(False) 返回 True 时不会自动管理）
                pass
        except Exception:
            # 如果 acquire(False) 抛出异常，直接等待
            await lock.acquire()

        try:
            expert, expert_state = _validate_and_prepare_state(expert_name, private_message, runtime)
            logger.debug(f"开始异步执行专家 {expert_name} 的任务...")
            expert_state = await expert.ainvoke(expert_state, config=runtime.config)
            logger.debug(f"专家 {expert_name} 异步任务执行完成")
            return _return_command_with_state_update(expert_name, expert_state, runtime)
        except Exception as e:
            logger.error(f"专家 {expert_name} 异步执行失败: {e}", exc_info=True)
            return Command(
                update={
                    "messages": [ToolMessage(
                        f"专家 {expert_name} 执行失败: {str(e)}",
                        tool_call_id=runtime.tool_call_id
                    )]
                }
            )
        finally:
            # ⭐ 释放锁
            lock.release()

    return StructuredTool.from_function(
        name="assign",
        func=assign,
        coroutine=aassign,
        description=description,
        infer_schema=False,
        args_schema=AssignToolSchema,
    )


class AssignMiddleware(AgentMiddleware[AssignState, ContextT, ResponseT]):
    """自定义的任务委派中间件，提供assign工具用于向专家团队委派任务。
    
    与标准的SubAgentMiddleware不同，AssignMiddleware:
    1. 使用简化的参数schema（private_message + expert_name）
    2. 提供更适合团队协作的系统提示词
    3. 通过 expert_states 状态字段管理专家的长期记忆
    
    Example:
        ```python
        from src.custom_middleware.assign import AssignMiddleware
        from src.dev_team.team_experts import team_experts
        
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

    state_schema = AssignState  # ⭐ 声明新的状态 Schema

    def before_agent(self, state: AssignState, runtime) -> dict | None:
        """在 Agent 执行前初始化 expert_states（如果不存在）。
        
        参考 SkillsMiddleware 的实现，在 before_agent 钩子中初始化新的 state key。
        """
        # 如果 expert_states 已经存在，不重复初始化
        if "expert_states" in state:
            return None

        # 初始化为空字典
        return {"expert_states": {}}

    async def abefore_agent(self, state: AssignState, runtime) -> dict | None:
        """异步版本的 before_agent。"""
        return self.before_agent(state, runtime)

    def __init__(
            self,
            *,
            experts: Sequence[CompiledExpertAgent] | None = None,
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
            raise ValueError("Please provide a list of experts  for AssignMiddleware Instance")

        # 将CompiledExpertAgent转换为内部规格格式
        expert_specs: list[_ExpertAgentSpec] = []
        for expert in experts:
            compiled = expert
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
        if self.system_prompt is not None:
            new_system_message = append_to_system_message(request.system_message, self.system_prompt)
            return await handler(request.override(system_message=new_system_message))
        return await handler(request)


def test_assign_middleware():
    import uuid

    from langchain_core.runnables import RunnableConfig

    from src.dev_team.team_with_sandbox import DevTeamWithLinuxSandboxAndMCP
    from src.utils.graph_running import multi_turn_conversation
    from src.dev_team.my_backend import LinuxSandboxBackend
    # 创建与当前任务关联的沙盒实例
    sandbox = LinuxSandboxBackend(task_name="Dev team test")

    # 创建dev_team实例
    dev_team = DevTeamWithLinuxSandboxAndMCP(sandbox)

    run_config: RunnableConfig = {
        "tags": ["agentbay_based_dev_team", "Leader"],
        "run_name": "assign中间件测试",
        "configurable": {"thread_id": str(uuid.uuid4())}
    }

    multi_turn_conversation(dev_team, run_config)


if __name__ == "__main__":
    test_assign_middleware()
