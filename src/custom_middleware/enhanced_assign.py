# EnhancedAssignMiddleware - 增强版任务委派中间件
# 
# 核心特性：
# 1. 专家智能体编译时传入 checkpointer，实现独立的状态持久化
# 2. 通过 EnhancedAssignMiddleware UserAgent state中的expert_thread_ids 字典（每个thread_id可视为文件名）管理每个专家的 thread_id，
# 同时结合checkpoint_ns（可视为文件夹）完成专家图状态的正确访问
# 3. assign 工具调用时自动检测并生成 thread_id（懒加载策略）
# 4. 专家状态与 Leader 状态完全解耦
# 5. 目前只有Leader Agent使用了EnhancedAssignMiddleware
#
# 缺陷：
# 1. 被调用的专家智能体的短期记忆，即thread id依旧完全依附于主调智能体状态中的expert_thread_ids 字典
#    这样的话，一个智能体在同一个软件开发任务中的短期记忆，无法被多个不同的智能体提供assign注入，并且不同智能体发消息必须是同步调用收消息的智能体。
# 2. 缺陷产生原因：EnhancedAssignMiddleware 或者说 想发消息的智能体 ，它们直接拥有智能体对象而不是智能体的InBox
#   同时团队中每个智能体的运行是由assign工具出发的
# 3. 缺陷解决办法：
# 每个智能体都拥有一个 CollaborateMiddleware，该中间件为智能体提供一个 Tasks/Attentions 列表、一个 send_message  工具
# sender message只会为目标智能体创建一个关注点，并不会立即触发该智能体的运行
# InBox中每条消息包含task_name-决定当前智能体启用哪条短期记忆、sender_name-告知接受任务的智能体完成任务后该向谁响应、private_message
# 五个智能体并行运行，只要有关注点存在，就触发当前智能体的一次运行
# 只要有关注点存在触，就定期触发一次当前智能体的一次运行，发消息者发消息时不需要专门传入task_name

# 理想情况：
import asyncio
import logging
import threading
import uuid
from typing import Any, Sequence, Callable, NotRequired, TypedDict, Annotated

from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware.types import AgentMiddleware, AgentState, ContextT, ModelRequest, ModelResponse, \
    ResponseT
from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import StructuredTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CompiledExpertAgent(TypedDict):
    """A pre-compiled agent spec.

    !!! note

        The runnable's state schema must include a 'messages' key.

        This is required for the expert agent to communicate results back to the main agent.

    When the expert agent completes, the final message in the 'messages' list will be
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
    runnable: CompiledStateGraph


def merge_expert_thread_ids(left: dict | None, right: dict | None) -> dict:
    """合并两个并行的 expert_thread_ids 更新。

    用于处理并行 assign 调用时的状态更新冲突。
    
    ⭐ 关键：LangGraph 的 reducer 函数必须能够处理 None 值

    Args:
        left: 第一个字典（可能是 None）
        right: 第二个字典（可能是 None），可能包含某个专家的最新 thread_id

    Returns:
        合并后的字典
    """
    logger.debug(f"reducer被调用，处理 expert_thread_ids 状态更新：{left} -> {right}")
    # 处理 None 值
    if left is None:
        left = {}
    if right is None:
        return left

    # 合并两个字典（right 中的值会覆盖 left 中的同名键）
    merged = dict(left)
    merged.update(right)
    return merged


class EnhancedAssignState(AgentState):
    """EnhancedAssignMiddleware 的状态 Schema。
    
    包含一个 expert_thread_ids 字典，用于存储每个专家的 thread_id。
    这样可以在多次 assign 调用之间保持对专家 thread_id 的追踪，
    而专家的完整图状态由专家自己的 checkpointer 根据 thread_id 自主管理。
    """
    expert_thread_ids: NotRequired[Annotated[dict[str, str], merge_expert_thread_ids]]
    """每个专家的 thread_id 字典。键为专家名称，值为 thread_id。使用自定义 reducer 支持并行更新。"""


ASSIGN_TOOL_DESCRIPTION = """Assign a task to a specific expert agent in the development team.

This tool allows you to assign specific development tasks to specialized team members.
The expert agent will execute the task and report the results.
Besides, you can also just use it as a communication tool between you and the other.

Available experts:
{available_experts}

Usage notes:
1. Be clear and specific about what you want the expert to accomplish. 
2. All expert agents maintain their own persistent state across multiple assignments via their dedicated thread_id.
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

Remember: Each expert agent maintains its own persistent state across multiple assignments, allowing them to build on previous work."""  # noqa: E501


class AssignToolSchema(BaseModel):
    """Assign工具的输入参数Schema，简化为专家名称和消息。"""
    expert_name: str = Field(
        description="The name of the expert agent to assign the task to (e.g., 'David', 'Eva', 'Alice')."
    )

    private_message: str = Field(
        description=("A message containing the concise task description that will be sent to the expert agent."
                     "如果是指派专家智能体产出文档交付物，不必明确指明文档的内容应该包含哪些章节，相信你的团队成员的老道经验！")
    )


def _build_assign_tool(*,
                       user_name: str = "Tim Leader",
                       experts: list[_ExpertAgentSpec],
                       ) -> StructuredTool:
    """构建assign工具，支持向专家团队委派任务。
    
    ⭐ 关键改进：
    - 不再维护专家完整状态，只维护 thread_id 映射
    - 调用专家时传入其专属的 thread_id，让专家自主持久化状态
    
    Args:
        user_name: 用户名称，用于注入private message作为send name
        experts: 专家智能体规格列表
        
    Returns:
        结构化的assign工具
    """

    # ⭐ 为每个专家创建一个线程锁，用于防止同一专家的并行调用
    expert_locks: dict[str, threading.Lock] = {spec["name"]: threading.Lock() for spec in experts}
    # ⭐ 为每个专家创建一个 asyncio 锁，用于异步版本
    expert_async_locks: dict[str, asyncio.Lock] = {spec["name"]: asyncio.Lock() for spec in experts}

    # 构建专家图谱字典和描述字符串
    expert_graphs: dict[str, CompiledStateGraph] = {spec["name"]: spec["runnable"] for spec in experts}
    expert_description_str = "\n".join(f"- {s['name']}: {s['description']}" for s in experts)

    # 格式化描述文本
    description = ASSIGN_TOOL_DESCRIPTION.format(available_experts=expert_description_str)

    def _return_command_with_state_update(expert_name: str, expert_thread_id: str, runtime: ToolRuntime,
                                          expert_result: dict) -> Command:
        """处理专家执行结果并返回Command对象。
        
        ⭐ 关键：只更新 expert_thread_ids（如果新生成的话），不维护专家完整状态
        """
        if "messages" not in expert_result:
            error_msg = (
                "Expert agent must return a state containing a 'messages' key. "
                "Custom StateGraphs used with CompiledExpertAgent should include 'messages' "
                "in their state schema to communicate results back to the main agent."
            )
            raise ValueError(error_msg)

        # 提取最后一条消息的文本内容，作为返回给主调智能体
        last_message = expert_result["messages"][-1]
        message_text = getattr(last_message, 'content', '') or getattr(last_message, 'text', '')
        if message_text:
            message_text = message_text.rstrip()

        # ⭐ 只返回当前专家的 thread_id 更新（如果是新生成的）
        return Command(
            update={
                "expert_thread_ids": {expert_name: expert_thread_id},
                "messages": [ToolMessage(message_text, tool_call_id=runtime.tool_call_id)],
            }
        )

    def _validate_and_prepare_call(expert_name: str, private_message: str, runtime: Any) -> tuple[Any, dict, str]:
        """验证专家名称并准备调用配置。
        
        ⭐ 关键改进：从 runtime.state 中读取或生成专家的 thread_id
        
        Returns:
            tuple: (expert runnable, input state, expert_thread_id)
        """
        if expert_name not in expert_graphs:
            allowed_names = ", ".join([f"`{k}`" for k in expert_graphs])
            raise ValueError(
                f"Expert '{expert_name}' does not exist. Available experts: {allowed_names}"
            )

        expert = expert_graphs[expert_name]

        # ⭐ 关键：从 Leader 状态中读取或生成专家的 thread_id
        expert_thread_ids = runtime.state.get("expert_thread_ids", {})
        expert_thread_id = expert_thread_ids.get(expert_name)

        if not expert_thread_id:
            # 首次调用该专家，生成新的 thread_id
            expert_thread_id = str(uuid.uuid4())
            logger.info(f"🆕 当前专家第一次被assign，为专家 '{expert_name}' 生成 thread_id: {expert_thread_id}")
        else:
            logger.debug(f"♻️ 当前专家不是第一次被assign，复用专家 '{expert_name}' 已有的 thread_id: {expert_thread_id}")

        # 构建专家输入状态（因为专家有自己的 checkpointer，只需要构建一条人类消息，不要获取其完整的最新图状态）
        private_message = f"Message from {user_name}:\n {private_message}"
        expert_input = {"messages": [HumanMessage(content=private_message)]}

        return expert, expert_input, expert_thread_id

    def assign(
            private_message: str,
            expert_name: str,
            runtime: ToolRuntime,
    ) -> str | Command:
        """同步版本的assign函数。
        
        ⭐ 使用线程锁防止同一专家的并行调用，如果检测到并发则直接返回错误
        ⭐ 关键改进：传入专家的 thread_id，让专家自主持久化状态
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
            expert, expert_input, expert_thread_id = _validate_and_prepare_call(expert_name, private_message,
                                                                                runtime)
            logger.debug(f"开始执行专家 {expert_name} 的任务 (thread_id: {expert_thread_id})...")

            # ⭐ 关键：构建专家的配置，传入其专属的 thread_id 和 checkpoint_ns
            expert_config = {
                **runtime.config,
                "configurable": {
                    **runtime.config.get("configurable", {}),
                    "thread_id": expert_thread_id,  # 覆盖为专家的 thread_id
                    "checkpoint_ns": f"expert:{expert_name}"  # ⭐ 为每个专家设置独立的 namespace
                }
            }

            # 调用专家，专家会根据 thread_id 自动持久化到自己的 checkpointer
            expert_result = expert.invoke(expert_input, config=expert_config)

            logger.debug(f"专家 {expert_name} 任务执行完成 (thread_id: {expert_thread_id})")
            return _return_command_with_state_update(expert_name, expert_thread_id, runtime, expert_result)
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
        ⭐ 关键改进：传入专家的 thread_id，让专家自主持久化状态
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
            expert, expert_input, expert_thread_id = _validate_and_prepare_call(expert_name, private_message,
                                                                                runtime)
            logger.debug(f"开始异步执行专家 {expert_name} 的任务 (thread_id: {expert_thread_id})...")

            # ⭐ 关键：构建专家的配置，传入其专属的 thread_id 和 checkpoint_ns
            expert_config = {
                **runtime.config,
                "configurable": {
                    **runtime.config.get("configurable", {}),
                    "thread_id": expert_thread_id,  # 覆盖为专家的 thread_id
                    "checkpoint_ns": f"expert:{expert_name}"  # ⭐ 为每个专家设置独立的 namespace
                }
            }

            # 异步调用专家，专家会根据 thread_id 自动持久化到自己的 checkpointer
            expert_result = await expert.ainvoke(expert_input, config=expert_config)

            logger.debug(f"专家 {expert_name} 异步任务执行完成 (thread_id: {expert_thread_id})")
            return _return_command_with_state_update(expert_name, expert_thread_id, runtime, expert_result)
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


class EnhancedAssignMiddleware(AgentMiddleware[EnhancedAssignState, ContextT, ResponseT]):
    """增强版任务委派中间件，提供assign工具用于向专家团队委派任务。
    
    与标准 AssignMiddleware 的核心区别：
    1. 专家智能体编译时传入 checkpointer，实现独立的状态持久化
    2. 只维护 expert_thread_ids 映射，不维护专家完整状态
    3. 调用专家时传入其专属的 thread_id，让专家自主管理状态
    4. 专家状态与 Leader 状态完全解耦
    
    Example:
        ```python
        from src.custom_middleware.enhanced_assign import EnhancedAssignMiddleware
        from src.dev_team.team_experts import team_experts
        
        leader = create_agent(
            model=llm,
            middleware=[
                EnhancedAssignMiddleware(
                    backend=my_backend,
                    experts=team_experts,
                ),
                # ... other middleware
            ],
        )
        ```
    """

    state_schema = EnhancedAssignState  # ⭐ 声明新的状态 Schema

    def __init__(
            self,
            *,
            user_name: str = "Tim Leader",
            experts: Sequence[CompiledExpertAgent] | None = None,
            system_prompt: str | None = ASSIGN_SYSTEM_PROMPT,
            **kwargs: Any,
    ) -> None:
        """初始化EnhancedAssignMiddleware。

        Args:
            user_name: 充当发消息时的sender name
            experts: 专家团队列表，默认为team_experts中定义的所有专家
            system_prompt: 自定义系统提示词，默认为ASSIGN_SYSTEM_PROMPT
            **kwargs: 传递给父类的其他参数
        """
        self.logger = logging.getLogger(__name__)

        # 如果没有提供专家列表，使用默认的team_experts
        if experts is None:
            raise ValueError("Please provide a list of experts for EnhancedAssignMiddleware Instance")

        # 将CompiledExpertAgent转换为内部规格格式
        expert_specs: list[_ExpertAgentSpec] = []
        for expert in experts:
            compiled = expert
            expert_specs.append({
                "name": compiled["name"],
                "description": compiled["description"],
                "runnable": compiled["runnable"]
            })

        self.user_name = user_name

        # 构建assign工具
        assign_tool = _build_assign_tool(user_name=self.user_name, experts=expert_specs)

        self.logger.info(
            f"为用户 {self.user_name} 创建的团队协作中间件 EnhancedAssignMiddleware 初始化完成，已注册了 {len(expert_specs)} 个专家")

        # 构建系统提示词
        if system_prompt and expert_specs:
            experts_desc = "\n".join(f"- {s['name']}: {s['description']}" for s in expert_specs)
            self.system_prompt = system_prompt + "\n\nAvailable experts:\n" + experts_desc
        else:
            self.system_prompt = system_prompt

        # 设置工具列表
        self.tools = [assign_tool]

    def before_agent(self, state: EnhancedAssignState, runtime) -> dict | None:
        """在 Agent 执行前初始化 expert_thread_ids（如果不存在）。
        
        参考 SkillsMiddleware 的实现，在 before_agent 钩子中初始化新的 state key。
        """
        # 如果 expert_thread_ids 已经存在，不重复初始化
        if "expert_thread_ids" in state:
            return None

        # 初始化为空字典
        return {"expert_thread_ids": {}}

    async def abefore_agent(self, state: EnhancedAssignState, runtime) -> dict | None:
        """异步版本的 before_agent。"""
        return self.before_agent(state, runtime)

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
