"""通信中间件 - 基于沙盒后端实现智能体异步通信。

工作原理（通俗解释）：
==================
【发消息】
  - 智能体调用 send_message 工具
  - 中间件直接通过 backend.write() 将消息写入接收者的邮箱文件夹
  - 例如：backend.write("/message_bus/engineer_inbox/msg_123.json", content)

【收消息 - 自动化！】
  - 每次智能体准备调用 LLM 前（wrap_model_call 钩子）
  - 中间件通过 backend.read() 读取收件箱中的所有未读消息
  - 将这些消息转换为 HumanMessage，注入到对话历史中
  - 智能体就会"看到"新消息，就像有人给它发了邮件一样

【并发执行】
  - Leader 和 Engineer 各自独立运行，有自己的 thread_id
  - 但共享同一个 backend（MySandbox 实例）
  - 通过文件系统交换信息，真正的异步通信
"""

import json
import time
import uuid
from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
    ResponseT,
)
from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing import NotRequired

from src.custom_middleware.my_sandbox import MySandbox


class MessageBusState(AgentState):
    """消息总线状态扩展"""

    unread_message_count: NotRequired[int]
    """未读消息数量"""


class SendMessageSchema(BaseModel):
    """发送消息工具的输入 schema"""

    recipient: str = Field(
        description="接收者智能体名称（如 'engineer', 'product_manager', 'architect'）"
    )
    subject: str = Field(
        description="消息主题，简要说明消息目的"
    )
    body: str = Field(
        description="消息正文，包含详细的任务描述或信息"
    )
    priority: str = Field(
        default="normal",
        description="消息优先级：'high'（高）、'normal'（普通）、'low'（低）"
    )


MESSAGE_BUS_ROOT = "temp/persistent/agent_workspace/message_bus"


class MessageBusMiddleware(AgentMiddleware[MessageBusState, ContextT, ResponseT]):
    """基于文件系统的消息总线中间件。
    
    这是 FilesystemMiddleware 的扩展，提供智能体之间的异步通信能力。
    
    关键特性：
    1. ✅ 直接访问 backend，无需通过 execute 工具
    2. ✅ 自动检查收件箱并注入消息到对话历史
    3. ✅ 支持真正的并发执行
    4. ✅ 自动从 runtime 获取 agent_name，无需手动传入
    
    Args:
        message_bus_root: 消息总线的根目录路径，默认为 "temp/persistent/agent_workspace/message_bus"
        backend: 文件系统后端实例（必须与 FilesystemMiddleware 共享）
    
    Example:
        ```python
        from src.agentbay_based_dev_team.my_sandbox import my_sandbox_backend
        from src.agentbay_based_dev_team.message_bus_middleware import MessageBusMiddleware
        
        # 创建共享的 backend
        backend = my_sandbox_backend
        
        # 为 Leader 创建消息中间件
        leader_message_bus = MessageBusMiddleware(
            agent_name="leader",
            backend=backend  # ⭐ 共享同一个 backend
        )
        
        # 为 Engineer 创建消息中间件
        engineer_message_bus = MessageBusMiddleware(
            agent_name="engineer",
            backend=backend  # ⭐ 共享同一个 backend
        )
        
        # 在创建智能体时使用
        leader = create_agent(
            model=llm,
            middleware=[
                FilesystemMiddleware(backend=backend),
                leader_message_bus,  # ⭐ 添加消息总线
                # ... 其他中间件
            ],
        )
        ```
    """

    state_schema = MessageBusState

    def __init__(
            self,
            message_bus_root: str = MESSAGE_BUS_ROOT,
            backend: MySandbox | None = None,
    ):
        """初始化消息总线中间件。
        
        Args:
            message_bus_root: 消息总线根目录路径
            backend: 文件系统后端实例（可选，如果为 None 则从 runtime 获取）
            
        Note:
            agent_name 不再需要在初始化时传入，会在运行时从 runtime.config.metadata['lc_agent_name'] 自动获取。
        """
        self.message_bus_root = message_bus_root.rstrip("/")
        self.backend = backend
        self._agent_name: str | None = None  # 延迟初始化，在第一次使用时从 runtime 获取

        # 注册发送消息工具
        self.send_message_tool = self._create_send_message_tool()

    def _get_agent_name(self, runtime_context) -> str:
        """从 runtime 中获取当前智能体名称。
        
        Args:
            runtime_context: 运行时上下文（可能是 ToolRuntime 或 Runtime）
            
        Returns:
            智能体名称
            
        Raises:
            RuntimeError: 如果无法从 runtime 中获取 agent_name
        """
        # 如果已经缓存了 agent_name，直接返回
        if self._agent_name is not None:
            return self._agent_name

        try:
            # 尝试从 runtime.config.metadata 中获取
            if hasattr(runtime_context, 'config') and runtime_context.config:
                metadata = runtime_context.config.get('metadata', {})
                agent_name = metadata.get('lc_agent_name')

                if agent_name:
                    self._agent_name = agent_name
                    return agent_name

            # 如果 runtime_context 是 ToolRuntime，尝试从 state 或其他地方获取
            if hasattr(runtime_context, 'state'):
                # 某些情况下可能在 state 中有相关信息
                pass

            raise RuntimeError(
                "无法从 runtime 中获取 agent_name。"
                "请确保 create_agent 时传入了 name 参数，"
                "或者在创建 MessageBusMiddleware 时显式传入 agent_name。"
            )

        except Exception as e:
            raise RuntimeError(f"获取 agent_name 失败: {str(e)}")

    @property
    def agent_name(self) -> str:
        """获取当前智能体名称（延迟加载）。
        
        注意：这个属性只能在运行时访问（即在中间件钩子函数中），
        因为在初始化时还没有 runtime 上下文。
        """
        if self._agent_name is None:
            raise RuntimeError(
                "agent_name 尚未初始化。请在运行时（如 wrap_model_call 中）访问此属性，"
                "而不是在 __init__ 中访问。"
            )
        return self._agent_name

    @property
    def inbox_path(self) -> str:
        """获取收件箱路径（动态计算）。"""
        return f"{self.message_bus_root}/{self.agent_name}_inbox"

    def _get_backend(self, runtime: ToolRuntime | None = None) -> MySandbox:
        """获取 backend 实例。
        
        Args:
            runtime: 工具运行时上下文（可选）
            
        Returns:
            Backend 实例
            
        Raises:
            RuntimeError: 如果无法获取 backend
        """
        # 优先使用初始化时传入的 backend
        if self.backend is not None:
            return self.backend

        # 尝试从 runtime 中获取（如果提供了 runtime）
        # 注意：这需要调用方正确传递 runtime
        raise RuntimeError(
            "未提供 backend 实例。请在创建 MessageBusMiddleware 时传入 backend 参数，"
            "或者确保 FilesystemMiddleware 已经设置了 backend。"
        )

    def _create_send_message_tool(self) -> StructuredTool:
        """创建发送消息工具。
        
        Returns:
            StructuredTool 实例
        """

        def sync_send_message(
                recipient: str,
                subject: str,
                body: str,
                priority: str = "normal",
                runtime: ToolRuntime = None,
        ) -> str:
            """同步发送消息实现"""
            return self._send_message_impl(recipient, subject, body, priority, runtime)

        async def async_send_message(
                recipient: str,
                subject: str,
                body: str,
                priority: str = "normal",
                runtime: ToolRuntime = None,
        ) -> str:
            """异步发送消息实现"""
            return self._send_message_impl(recipient, subject, body, priority, runtime)

        return StructuredTool.from_function(
            name="send_message",
            description=self._get_send_message_description(),
            func=sync_send_message,
            coroutine=async_send_message,
            args_schema=SendMessageSchema,
        )

    def _get_send_message_description(self) -> str:
        """获取发送消息工具的描述文本。
        
        Returns:
            工具描述字符串
        """
        return """向团队其他成员发送消息。

使用场景：
- 委派任务给其他专家智能体
- 请求协助或咨询意见
- 通知任务完成或进度更新
- 传递重要信息或文档引用

参数说明：
- recipient: 接收者名称（可选值：'engineer', 'product_manager', 'architect', 'QA_engineer', 'project_manager', 'leader'）
- subject: 消息主题，简明扼要地说明目的
- body: 消息正文，包含详细的内容、上下文和期望
- priority: 优先级（'high'/'normal'/'low'），默认为 'normal'

示例：
```python
send_message(
    recipient="engineer",
    subject="实现用户登录功能",
    body="请根据《系统详细设计.md》第3.2节的要求，实现用户登录模块。\\n\\n要求：\\n1. 支持用户名密码登录\\n2. 支持记住登录状态\\n3. 登录失败时给出明确提示\\n\\n交付物：\\n- src/auth/login.py\\n- tests/test_login.py",
    priority="high"
)
```

注意：
- 消息会被立即保存到接收者的收件箱中
- 接收者会在下次调用 LLM 时自动收到这条消息
- 尽量保持消息内容清晰、具体、可执行
"""

    def _send_message_impl(
            self,
            recipient: str,
            subject: str,
            body: str,
            priority: str,
            runtime: ToolRuntime = None,
    ) -> str:
        """发送消息的核心实现。
        
        直接通过 backend 写入消息文件，无需智能体执行 shell 命令。
        
        Args:
            recipient: 接收者名称
            subject: 消息主题
            body: 消息正文
            priority: 优先级
            runtime: 工具运行时上下文
            
        Returns:
            确认消息字符串
        """
        try:
            # 获取 backend
            backend = self._get_backend(runtime)

            # 获取当前智能体名称（首次调用时会从 runtime 中自动获取）
            sender_name = self._get_agent_name(runtime)

            # 生成消息 ID
            message_id = str(uuid.uuid4())

            # 构建消息数据
            message_data = {
                "id": message_id,
                "timestamp": time.time(),
                "sender": sender_name,  # 使用从 runtime 获取的名称
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "priority": priority,
                "read": False,
            }

            # 确定目标收件箱路径
            target_inbox = f"{self.message_bus_root}/{recipient}_inbox"
            message_file = f"{target_inbox}/{message_id}.json"

            # 将消息数据转换为 JSON 字符串
            message_json = json.dumps(message_data, ensure_ascii=False, indent=2)

            # 直接通过 backend 写入文件
            write_result = backend.write(message_file, message_json)

            if write_result.error:
                return f"❌ 发送消息失败：{write_result.error}"

            return f"""✅ 消息已成功发送到 {recipient} 的收件箱

📧 消息ID: {message_id}
📝 主题: {subject}
⚡ 优先级: {priority}
📂 存储位置: {message_file}

接收者会在下次运行时自动收到这条消息。
"""

        except Exception as e:
            return f"❌ 发送消息时发生错误：{str(e)}"

    def _check_and_read_unread_messages(self, runtime_context) -> list[HumanMessage]:
        """检查并读取收件箱中的未读消息。
        
        这是核心的"自动收消息"功能，会在每次模型调用前执行。
        
        Args:
            runtime_context: 运行时上下文（可能是 ToolRuntime 或 Runtime）
            
        Returns:
            未读消息列表，已转换为 HumanMessage 格式
        """
        try:
            # 获取 backend
            backend = self._get_backend(runtime_context if hasattr(runtime_context, 'tool_call_id') else None)

            # 获取当前智能体名称（首次调用时会从 runtime 中自动获取）
            current_agent_name = self._get_agent_name(runtime_context)
            current_inbox_path = f"{self.message_bus_root}/{current_agent_name}_inbox"

            # 列出收件箱中的所有消息文件
            # 注意：backend 可能没有直接的 ls 方法，我们需要通过其他方式
            # 这里我们假设 backend 支持 glob 或者我们可以通过 state 中的 files 来获取

            # 方案1：尝试使用 backend.glob（如果支持）
            if hasattr(backend, 'glob'):
                glob_result = backend.glob(f"{current_inbox_path}/*.json")
                if glob_result.error:
                    return []
                message_files = [entry.get('path', '') for entry in (glob_result.matches or [])]
            else:
                # 方案2：如果没有 glob，返回空列表（依赖智能体主动检查）
                # TODO: 未来可以通过其他方式实现
                return []

            # 读取每个未读消息
            unread_messages = []
            for msg_file in message_files:
                try:
                    # 读取消息文件
                    read_result = backend.read(msg_file)

                    if read_result.error or read_result.file_data is None:
                        continue

                    # 解析 JSON
                    content_str = read_result.file_data.get('content', '')
                    message_data = json.loads(content_str)

                    # 只处理未读消息
                    if not message_data.get('read', True):
                        # 转换为 HumanMessage
                        sender = message_data.get('sender', 'Unknown')
                        subject = message_data.get('subject', 'No Subject')
                        body = message_data.get('body', '')
                        priority = message_data.get('priority', 'normal')

                        # 构建消息内容
                        message_content = f"""📨 来自 {sender} 的新消息

主题: {subject}
优先级: {priority}

内容:
{body}

---
消息ID: {message_data.get('id', 'N/A')}
时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(message_data.get('timestamp', 0)))}
"""

                        # 创建 HumanMessage
                        human_msg = HumanMessage(content=message_content)
                        unread_messages.append(human_msg)

                        # 标记为已读
                        message_data['read'] = True
                        updated_json = json.dumps(message_data, ensure_ascii=False, indent=2)
                        backend.write(msg_file, updated_json)

                except Exception as e:
                    # 单个消息读取失败不影响其他消息
                    continue

            return unread_messages

        except Exception as e:
            # 如果检查失败，返回空列表，不阻断正常流程
            return []

    def wrap_model_call(
            self,
            request: ModelRequest[ContextT],
            handler,
    ) -> ModelResponse[ResponseT] | ExtendedModelResponse:
        """在模型调用前自动检查收件箱，将新消息注入对话历史。
        
        这是实现"自动收消息"的关键钩子。
        
        Args:
            request: 模型请求对象
            handler: 处理器函数
            
        Returns:
            模型响应，可能包含状态更新命令
        """
        # 检查收件箱中的未读消息
        new_messages = self._check_and_read_unread_messages(request.runtime)

        if new_messages:
            # 将新消息添加到请求的消息列表中
            updated_messages = list(request.messages) + new_messages
            request = request.override(messages=updated_messages)

            # 更新状态中的未读消息计数
            state_update = Command(update={
                "unread_message_count": len(new_messages),
                "messages": new_messages  # 将新消息也添加到 state
            })

            # 调用处理器
            response = handler(request)

            # 返回扩展响应，包含状态更新
            return ExtendedModelResponse(
                model_response=response,
                command=state_update
            )

        # 没有新消息，正常处理
        return handler(request)

    async def awrap_model_call(
            self,
            request: ModelRequest[ContextT],
            handler,
    ) -> ModelResponse[ResponseT] | ExtendedModelResponse:
        """异步版本的 wrap_model_call。
        
        Args:
            request: 模型请求对象
            handler: 异步处理器函数
            
        Returns:
            模型响应
        """
        # 检查收件箱
        new_messages = self._check_and_read_unread_messages(request.runtime)

        if new_messages:
            updated_messages = list(request.messages) + new_messages
            request = request.override(messages=updated_messages)

            state_update = Command(update={
                "unread_message_count": len(new_messages),
                "messages": new_messages
            })

            response = await handler(request)

            return ExtendedModelResponse(
                model_response=response,
                command=state_update
            )

        return await handler(request)

    @property
    def tools(self):
        """返回中间件提供的工具列表。
        
        Returns:
            工具列表
        """
        return [self.send_message_tool]
