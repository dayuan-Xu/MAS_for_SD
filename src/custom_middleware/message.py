# CommunicateMiddleware - 增强版任务委派中间件
# 
# 核心特性：
# 1. 专家智能体编译时传入 checkpointer，实现独立的状态持久化
# 2. 通过 CommunicateMiddleware UserAgent state中的expert_thread_ids 字典（每个thread_id可视为文件名）管理每个专家的 thread_id，
# 同时结合checkpoint_ns（可视为文件夹）完成专家图状态的正确访问----在不同专家应用了不同的thread id后，也有必要在执行专家时配置不同的ns！！！
# 结合ns以表明专家智能体的检查点不属于顶层图""
# 3. communicate 工具调用时自动检测并生成 thread_id（懒加载策略）
# 4. 专家状态与 Leader 状态完全解耦
# 5. 目前只有Leader Agent使用了EnhancedCommunicateMiddleware
#
# 缺陷：
# 1. 被调用的专家智能体的短期记忆，即thread id依旧完全依附于主调智能体状态中的expert_thread_ids 字典
#    这样的话，一个智能体在同一个软件开发任务中的短期记忆，无法被多个不同的智能体提供communicate注入，并且不同智能体发消息必须是同步调用收消息的智能体。
# 2. 缺陷产生原因：CommunicateMiddleware 或者说 想发消息的智能体 ，它们直接拥有智能体对象而不是智能体的InBox
#   同时团队中每个智能体的运行是由communicate工具出发的
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
from typing import Any, Sequence, Callable, TypedDict, Annotated

from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware.types import AgentMiddleware, AgentState, ContextT, ModelRequest, ModelResponse, \
    ResponseT, PrivateStateAttr
from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
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
    """Unique identifier in the main agent's eyes for the expert agent."""

    description: str
    """What this expert agent does."""

    runnable: CompiledStateGraph
    """A custom agent implementation.

    Create a custom agent using either:

    1. LangChain's [`create_agent()`](https://docs.langchain.com/oss/python/langchain/quickstart)
    2. A custom graph using [`langgraph`](https://docs.langchain.com/oss/python/langgraph/quickstart)

    If you're creating a custom graph, make sure the state schema includes a 'messages' key.
    This is required for the expert agent to communicate results back to the leader agent.
    """


def create_compiled_expert_agent(agent: CompiledStateGraph, description: str):
    name = agent.name
    return CompiledExpertAgent(
        name=name,
        runnable=agent,
        description=description
    )


class _ExpertAgentSpec(TypedDict):
    """Internal spec for building the communicate tool."""

    name: str
    description: str
    runnable: CompiledStateGraph


class CommunicateState(AgentState):
    """CommunicateMiddleware 的状态 Schema。
    
    包含一个 expert_thread_ids 字典，用于存储每个专家的 thread_id。
    这样可以在多次 Communicate 调用之间保持对专家 thread_id 的追踪，
    而专家的完整图状态由专家自己的 checkpointer 根据 thread_id 自主管理。
    """
    # expert_thread_ids: NotRequired[dict[str, str]]
    # """每个专家的 thread_id 字典。键为专家名称，值为 thread_id。可以不包含在State中，向后兼容。因为不是个累积的通道，所以不需要自定义 reducer。"""
    expert_thread_ids: Annotated[dict[str, str], PrivateStateAttr]
    """每个专家的 thread_id 字典。键为专家名称，值为 thread_id。PrivateStateAttr 明确表达了"这是内部状态用户不应该关心"。
    显示表明不应该合并到图的InputSchema中，不能由用户输入注入到，也不会暴露在最终输出中"""


MESSAGE_TOOL_DESCRIPTION = """Communicate with a specific expert agent in the development team by sending a message.
The expert agent will do some work and respond to you.
You can also use it as a tool to assign specific tasks to specialized team members.

Available experts:
{available_experts}

Usage notes:
1. Be clear and specific about what you want the expert to accomplish if you are assigning a task. 
2. All expert agents maintain their own memory across multiple communications between you and him/her.
3. Use this tool to leverage the specialized capabiliies of each team member.
4. 目前不支持针对同一专家智能体并行调用该工具，即你不能同时多次给同一个专家智能体发消息，但是你具备同时给不同专家智能体发消息的能力。"""  # noqa: E501

COMMUNICATE_SYSTEM_PROMPT = """## `send_message` (team collaboration tool)

You have access to an `send_message` tool to communicate with specialized expert agents in your development team.

When to use this tool:
- When you want to discuss or debate with one of your team members, use it as a communication tool
- When you need to assign a specific task to a team member because this task requires his/her specialized expertise (coding, testing, product management, etc.)

How to use:
1. Specify the message clearly in the `private_message` parameter
2. Choose the appropriate expert by their `expert_name`"""  # noqa: E501


class CommunicateToolSchema(BaseModel):
    """Assign工具的输入参数Schema，简化为专家名称和消息。"""
    expert_name: str = Field(
        description="The name of the expert agent to send the message to."
    )

    private_message: str = Field(
        description="A message containing the information that will be sent to the expert agent."
    )


def _build_send_message_tool(*,
                             user_name: str = "Message Sender Name",
                             expert_specs: list[_ExpertAgentSpec],
                             ) -> StructuredTool:
    """构建assign工具，支持向专家团队委派任务。
    
    - 不再维护专家完整状态，只维护 thread_id 映射
    - 调用专家时传入其专属的 thread_id，让专家自主持久化状态
    
    Args:
        user_name: 用户名称，用于注入private message作为send name
        expert_specs: 专家智能体规格列表
        
    Returns:
        结构化的assign工具
    """

    # 为每个专家创建一个线程锁，用于防止同一专家的并行调用
    expert_locks: dict[str, threading.Lock] = {spec["name"]: threading.Lock() for spec in expert_specs}
    # 为每个专家创建一个 asyncio 锁，用于异步版本
    expert_async_locks: dict[str, asyncio.Lock] = {spec["name"]: asyncio.Lock() for spec in expert_specs}

    # 构建专家图谱字典和描述字符串
    expert_name_to_graphs: dict[str, CompiledStateGraph] = {spec["name"]: spec["runnable"] for spec in expert_specs}
    expert_name_to_description_str = "\n".join(f"- {s['name']}: {s['description']}" for s in expert_specs)

    # 工具名称
    send_message_tool_name = "send_message"

    # 格式化工具描述文本
    description = MESSAGE_TOOL_DESCRIPTION.format(
        available_experts=expert_name_to_description_str if expert_specs else "None")

    def _return_command_with_state_update(expert_name: str, runtime: ToolRuntime, expert_result: dict) -> Command:
        """处理专家执行结果并返回Command对象。
        :rtype: Command
        """
        if "messages" not in expert_result:
            error_msg = ("专家智能体必须返回包含“messages”这个key的状态字典。"
                         "传入 CompiledExpertAgent 中的自定义状态图应在其状态模式中包含'messages'，以便将结果传回主智能体。")
            raise ValueError(error_msg)

        # 提取最后一条消息的文本内容，作为返回给主调智能体
        last_message = expert_result["messages"][-1]
        message_content = getattr(last_message, 'content', '') or getattr(last_message, 'text', '')
        if isinstance(message_content, str):
            message_content = f"Response from {expert_name}:\n" + message_content

        # 只返回当前专家本次ReAct循环的最后一条AIMessage
        return Command(
            update={
                "messages": [ToolMessage(message_content, tool_call_id=runtime.tool_call_id)],
            }
        )

    def _validate_and_prepare_call(expert_name: str, private_message: str, runtime: ToolRuntime) -> tuple:
        """验证专家名称并准备调用配置。
        
        关键改进：从 runtime.state 中读取或生成专家的 thread_id
        
        Returns:
            tuple: (expert runnable, input state, expert_thread_id)
        """
        if expert_name not in expert_name_to_graphs:
            allowed_names = ", ".join([f"`{k}`" for k in expert_name_to_graphs])
            raise ValueError(
                f"Expert '{expert_name}' does not exist. Available experts: {allowed_names}"
            )

        expert = expert_name_to_graphs[expert_name]

        # 从 Leader/Planner 状态中读取已经生成的专家的 thread_id
        expert_thread_ids = runtime.state.get("expert_thread_ids", {})
        expert_thread_id = expert_thread_ids.get(expert_name)

        if expert_thread_id is None:
            # 上抛
            raise ValueError(
                f"'{expert_name}'还没有被分配一个thread id。 "
                f"请在当前MessageMiddleware.(a)before_agent中为当前MessageMiddleware实例所拥有的每位专家智能体分配一个thread id。"
            )

        # 构建专家输入状态（因为专家有自己的 checkpointer，只需要构建一条人类消息，不要获取其完整的最新图状态）
        # 设置消息发送者名称
        sender_name = user_name
        private_message = (f"1. Here comes a new message from {sender_name}:\n"
                           f"{private_message}\n"
                           f"2. Give me your response to this new message like I were {sender_name}."
                           f"Don't call {send_message_tool_name} with the expert_name equal to {sender_name},"
                           f"because I will relay your response to {sender_name}.")
        expert_input = {"messages": [HumanMessage(content=private_message)]}

        return expert, expert_input, expert_thread_id

    def send_message(
            private_message: str,
            expert_name: str,
            runtime: ToolRuntime,
    ) -> str | Command:
        """同步版本的send_message函数。
        
        使用线程锁防止同一专家的并行调用，如果检测到并发则直接返回错误
        关键改进：传入专家的 thread_id，让专家自主持久化状态
        """
        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for expert assignment")

        # 获取该专家的锁
        lock = expert_locks.get(expert_name)
        if not lock:
            raise ValueError(f"Expert '{expert_name}' not found in your contacts list")

        # 尝试非阻塞获取锁，如果失败说明有并发调用，直接返回错误
        acquired = lock.acquire(blocking=False)
        if not acquired:
            logger.warning(
                f"⚠️ 检测到并发调用：专家 '{expert_name}' 正在执行另一个任务。"
                f"不支持对同一专家智能体并行调用 send_message，请顺序调用。"
            )
            # 直接返回错误消息，不阻塞等待
            return Command(
                update={
                    "messages": [ToolMessage(
                        content=f"❌ 错误：专家智能体 '{expert_name}' 正在执行另一个任务。"
                                f"不支持对同一专家智能体并行调用 send_message。"
                                f"请等待当前任务完成后再调用，或指派其他专家。",
                        tool_call_id=runtime.tool_call_id
                    )]
                }
            )

        try:
            expert, expert_input, expert_thread_id = _validate_and_prepare_call(expert_name, private_message,
                                                                                runtime)

            logger.debug(f"开始执行专家 {expert_name} (thread_id: {expert_thread_id})")

            # 关键：构建专家的配置，传入其专属的 thread_id 和 checkpoint_ns
            expert_config = {
                **runtime.config,
                "tags": runtime.config["tags"] + [f"{expert_name}"],
                "configurable": {
                    **runtime.config.get("configurable", {}),
                    "thread_id": expert_thread_id,  # 覆盖为专家智能体自己的 thread_id
                    "checkpoint_ns": f"expert_{expert_name}"  # 必要，为每个专家设置独立的 namespace
                },
            }

            # 调用专家，专家会根据 thread_id 自动持久化到自己的 checkpointer
            expert_result = expert.invoke(expert_input, config=expert_config)

            logger.debug(
                f"专家智能体 {expert_name} 执行完成，将提取其最后一条不包含工具调用的AIMessage返回给主调智能体")

            return _return_command_with_state_update(expert_name, runtime, expert_result)
        except Exception as e:
            logger.error(f"专家智能体 {expert_name} 执行过程中出现异常: {e}", exc_info=True)
            return Command(
                update={
                    "messages": [ToolMessage(
                        f"专家智能体 {expert_name} 执行过程中出现异常: {str(e)}",
                        tool_call_id=runtime.tool_call_id
                    )]
                }
            )
        finally:
            # 释放锁
            lock.release()

    async def asend_message(
            private_message: str,
            expert_name: str,
            runtime: ToolRuntime,
    ) -> str | Command:
        """异步版本的assign函数。
        
        使用 asyncio 锁防止同一专家的并行调用
        关键改进：传入专家的 thread_id，让专家自主持久化状态
        """
        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for expert assignment")

        # 获取该专家的 asyncio 锁
        lock = expert_async_locks.get(expert_name)
        if not lock:
            raise ValueError(f"Expert '{expert_name}' not found in your contacts list")

        # 尝试获取锁，如果锁已被占用，说明有并发调用
        try:
            acquired = lock.acquire(False)  # 非阻塞尝试
            if not acquired:
                logger.warning(
                    f"⚠️ 检测到并发调用：专家 '{expert_name}' 正在执行另一个任务。"
                    f"当前调用将被阻塞，直到前一个任务完成。建议避免同时多次 send_message 同一个专家。"
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
            logger.debug(f"开始异步执行专家 {expert_name} (thread_id: {expert_thread_id})...")

            # 构建专家的配置，传入其专属的 thread_id 和 checkpoint_ns
            expert_config = {
                **runtime.config,
                "tags": runtime.config["tags"] + [f"{expert_name}"],
                "configurable": {
                    **runtime.config.get("configurable", {}),
                    "thread_id": expert_thread_id,  # 覆盖为专家智能体自己的 thread_id
                    "checkpoint_ns": f"expert_{expert_name}"  # 必要，为每个专家设置独立的 namespace
                },
            }

            # 异步调用专家，专家会根据 thread_id 自动持久化到自己的 checkpointer
            expert_result: dict = await expert.ainvoke(expert_input, config=expert_config)

            logger.debug(f"专家 {expert_name} 执行完成 (thread_id: {expert_thread_id})")

            # 缺陷是：
            # 若程序在 expert.ainvoke() 执行过程中被强行终止，而且本次执行该专家之前是新建了expert_thread_id而不是复用已有的expert thread id，
            # 那么本次新建的expert_thread_id将不会被持久化到Alice的图状态中，
            # 下次接着Alice的thread id运行Alice，在Alice的MessageMiddlware.abefore_agent钩子函数的输入中会检测到expert_thread_ids这个key不在图状态中！
            # 修复方法：
            # 每次send message调用应该仅仅返回ToolMessage到主调智能体的状态中
            return _return_command_with_state_update(expert_name, runtime, expert_result)
        except Exception as e:
            logger.error(f"专家智能体 {expert_name} 执行过程中出现异常: {e}", exc_info=True)
            return Command(
                update={
                    "messages": [ToolMessage(
                        f"专家智能体 {expert_name} 执行过程中出现异常: {str(e)}",
                        tool_call_id=runtime.tool_call_id
                    )]
                }
            )
        finally:
            # ⭐ 释放锁
            lock.release()

    return StructuredTool.from_function(
        name=send_message_tool_name,
        func=send_message,
        coroutine=asend_message,
        description=description,
        infer_schema=False,
        args_schema=CommunicateToolSchema,
    )


class CommunicateMiddleware(AgentMiddleware[CommunicateState, ContextT, ResponseT]):
    """增强版任务委派中间件，提供send_message工具用于向专家团队委派任务。
    
    与标准 CommunicateMiddleware 的核心区别：
    1. 专家智能体编译时传入 checkpointer，实现独立的状态持久化
    2. 只维护 expert_thread_ids 映射，不维护专家完整状态
    3. 调用专家时传入其专属的 thread_id，让专家自主管理状态
    4. 专家状态与 Leader 状态完全解耦
    """

    state_schema = CommunicateState  # ⭐ 声明新的状态 Schema

    def __init__(
            self,
            *,
            user_name: str = "Message Sender Name",
            experts: Sequence[CompiledExpertAgent] | None = None,
            system_prompt: str | None = COMMUNICATE_SYSTEM_PROMPT,
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

        self.user_name = user_name

        # 如果没有提供专家列表，使用默认的team_experts
        if experts is None:
            raise ValueError("Please provide a list of experts for CommunicateMiddleware Instance")

        # 将CompiledExpertAgent转换为内部规格格式
        self.expert_specs: list[_ExpertAgentSpec] = []
        for expert in experts:
            compiled = expert
            dict_: _ExpertAgentSpec = {
                "name": compiled["name"],
                "description": compiled["description"],
                "runnable": compiled["runnable"],
            }
            self.expert_specs.append(dict_)

        # 构建send message工具
        message_tool = _build_send_message_tool(user_name=self.user_name, expert_specs=self.expert_specs)

        self.logger.debug(
            f"为用户 {self.user_name} 创建的团队协作中间件 CommunicateMiddleware 初始化完成，已注册了 {len(self.expert_specs)} 个专家")

        # 构建系统提示词
        if system_prompt and self.expert_specs:
            experts_desc = "\n".join(f"- {s['name']}: {s['description']}" for s in self.expert_specs)
            self.system_prompt = system_prompt + "\n\nAvailable contacts:\n" + experts_desc
        else:
            self.system_prompt = system_prompt

        # 设置工具列表
        self.tools = [message_tool]

    def before_agent(self, state: CommunicateState, runtime) -> dict | None:
        """在 Agent 执行前初始化 expert_thread_ids（如果不存在）。
        
        参考 SkillsMiddleware 的实现，在 before_agent 钩子中初始化新的 state key。
        """
        if "expert_thread_ids" in state and state["expert_thread_ids"]:
            logger.debug(
                f"为用户 {self.user_name} 创建的团队协作中间件 CommunicateMiddleware"
                f" 检测到 专家线程ID映射 已存在于图状态之中并且不为空: {state['expert_thread_ids']}")
            return None
        else:
            logger.debug(
                f"为用户 {self.user_name} 创建的团队协作中间件 CommunicateMiddleware 正在初始化 专家线程ID映射")

            logger.warning(
                f"为用户 {self.user_name} 创建的团队协作中间件 CommunicateMiddleware "
                f"检测到 专家线程ID映射 目前不存在！")

            # 初始化为非空字典
            expert_name_to_thread_id = {expert_spec["name"]: str(uuid.uuid4()) for expert_spec in self.expert_specs}

            logger.info(
                f"智能体{self.user_name}的 CommunicateMiddleware 实例"
                f"成功为该智能体初始化了 专家名到其线程ID 的映射: {expert_name_to_thread_id}")

            return {
                "expert_thread_ids": expert_name_to_thread_id
            }

    async def abefore_agent(self, state: CommunicateState, runtime) -> dict | None:
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
