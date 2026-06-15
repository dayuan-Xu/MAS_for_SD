"""消息序列完整性检查中间件 - 修复某些异常情况导致某个工具调用缺失相应的ToolMessage。

问题背景：
==========
智能体看不到之前某个工具调用的对应的返回结果消息（ToolMessage），
则会导致BadRequestError: "tool call result does not follow tool call"错误。

解决方案：
==========
在每次模型调用前，执行以下操作：
1. 检测并清理包含BadRequestError的脏消息及其之后的所有消息
2. 遍历所有AssistantMessage中的tool_calls
3. 验证每个tool_call是否有对应的ToolMessage
4. 如果缺少ToolMessage，手术式精准插入到对应AIMessage之后
5. 使用Overwrite包装器替换式更新state中的messages

工作原理：
==========
【before_model 钩子】
  - 在每次模型调用前执行
  - 第一步：检测并清理脏消息（包含BadRequestError的AIMessage及其之后的消息）
  - 第二步：从清理后的消息历史中查找所有AssistantMessage的tool_calls
  - 第三步：检查每个tool_call_id是否有对应的ToolMessage
  - 第四步：如果缺失，手术式精准插入ToolMessage到对应AIMessage之后
  - 第五步：使用Overwrite包装器替换式更新state

注意：
======
此中间件应该放在中间件链的最外层（第一个位置），确保在其他中间件处理之前完成消息序列修复。
"""

import logging
from typing import Any, Dict, Optional

from langchain.agents.middleware.types import AgentMiddleware, AgentState
from langchain_core.messages import ToolMessage, AIMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite
from langgraph.typing import ContextT


class MessageSequenceValidator(AgentMiddleware[AgentState]):
    """消息序列完整性检查中间件。
    
    用于检测和修复棕地开发时缺失的ToolMessage，避免BadRequestError错误。
    
    Example:
        ```python
        from src.custom_middleware.message_sequence_validator import MessageSequenceValidator
        
        planner = create_agent(
            model=llm,
            middleware=[
                MessageSequenceValidator(),  # ⭐ 放在最外层
                todo_list_middleware,
                filesystem_middleware,
                # ... 其他中间件
                model_retry_middleware,  # 最内层
            ],
        )
        ```
    """

    def __init__(self):
        """初始化消息序列验证中间件。"""
        self.logger = logging.getLogger(__name__)

    def before_model(self, state: AgentState, runtime: Runtime[ContextT]) -> Optional[Dict[str, Any]]:
        """模型调用前钩子 - 检查并修复消息序列完整性。
        
        从 state 的消息历史中查找所有未完成的工具调用，并为缺失的ToolMessage生成占位符。
        同时清理包含BadRequestError的脏消息。
        
        Args:
            state: 当前智能体状态，包含 messages 列表
            runtime: 运行时上下文
            
        Returns:
            如果检测到缺失的ToolMessage或脏消息，返回使用Overwrite包装的更新state；否则返回None
        """
        try:
            messages = state.get("messages", [])

            if not messages:
                return None

            # ========== 第一步：检测并清理脏消息 ==========
            # 查找包含BadRequestError的AIMessage
            bad_request_error_marker = "tool call result does not follow tool call"
            dirty_message_index = None

            for idx, msg in enumerate(messages):
                if isinstance(msg, AIMessage):
                    # 检查content中是否包含BadRequestError
                    content_str = str(msg.content) if msg.content else ""
                    if bad_request_error_marker in content_str:
                        dirty_message_index = idx
                        self.logger.warning(f"⚠️ 检测到脏消息（索引{idx}），包含BadRequestError")
                        break

            # 如果找到脏消息，截断消息列表（保留脏消息之前的所有消息）
            if dirty_message_index is not None:
                original_count = len(messages)
                messages = messages[:dirty_message_index]
                removed_count = original_count - dirty_message_index
                self.logger.info(f"✅ 已清理脏消息及其之后的 {removed_count} 条消息")

                # 清理后重新检查消息列表
                if not messages:
                    return None

            # ========== 第二步：检测缺失的ToolMessage ==========
            # 收集所有AssistantMessage中的tool_calls（记录消息索引）
            pending_tool_calls = []  # List of (msg_index, tool_call_id, tool_name)

            for msg_idx, msg in enumerate(messages):
                if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        tool_call_id = tool_call.get('id')
                        tool_name = tool_call.get('name', 'unknown')
                        if tool_call_id:
                            pending_tool_calls.append((msg_idx, tool_call_id, tool_name))

            if not pending_tool_calls:
                # 没有待处理的工具调用，无需检查
                return None

            # 收集所有已有的ToolMessage的tool_call_id
            existing_tool_message_ids = set()
            for msg in messages:
                if isinstance(msg, ToolMessage):
                    tool_call_id = getattr(msg, 'tool_call_id', None)
                    if tool_call_id:
                        existing_tool_message_ids.add(tool_call_id)

            # 找出缺失ToolMessage的工具调用
            missing_tool_calls = [
                (msg_idx, tc_id, tc_name)
                for msg_idx, tc_id, tc_name in pending_tool_calls
                if tc_id not in existing_tool_message_ids
            ]

            if not missing_tool_calls:
                # 所有工具调用都有对应的ToolMessage，序列完整
                return None

            # ========== 第三步：手术式精准插入缺失的ToolMessage ==========
            # 记录发现的问题
            separator = "=" * 80
            self.logger.warning(separator)
            self.logger.warning(f"⚠️ [MessageSequenceValidator] 检测到 {len(missing_tool_calls)} 个缺失的ToolMessage")
            self.logger.warning(separator)

            for idx, (msg_idx, tc_id, tc_name) in enumerate(missing_tool_calls, 1):
                self.logger.warning(f"  [{idx}] 工具名称: {tc_name}, 调用ID: {tc_id}, 所属AIMessage索引: {msg_idx}")

            # 构建新的消息列表，手术式插入缺失的ToolMessage
            new_messages = []
            inserted_count = 0

            # 创建一个映射：AIMessage索引 -> 需要在其后插入的ToolMessage列表
            insertions_map = {}
            for msg_idx, tc_id, tc_name in missing_tool_calls:
                if msg_idx not in insertions_map:
                    insertions_map[msg_idx] = []
                insertions_map[msg_idx].append((tc_id, tc_name))

            # 遍历原消息列表，在适当位置插入ToolMessage
            for current_idx, msg in enumerate(messages):
                new_messages.append(msg)

                # 如果当前消息是AIMessage且有需要插入的ToolMessage
                if current_idx in insertions_map:
                    for tc_id, tc_name in insertions_map[current_idx]:
                        # 生成占位符内容
                        placeholder_content = (
                            f"该工具调用未能成功返回。"
                            f"可能原因：本次软件开发持续时间过长触发超时沙盒自动释放或网络中断导致沙盒连接断开。"
                            f"请重新执行该操作或采取其他策略。"
                        )

                        # 创建ToolMessage
                        placeholder_tool_message = ToolMessage(
                            content=placeholder_content,
                            tool_call_id=tc_id,
                            name=tc_name
                        )

                        # 紧跟在AIMessage之后插入
                        new_messages.append(placeholder_tool_message)
                        inserted_count += 1

                        self.logger.info(f"✅ 已在AIMessage[{current_idx}]后插入ToolMessage: '{tc_name}' (ID: {tc_id})")

            # ========== 第四步：使用Overwrite替换式更新state ==========
            self.logger.info(f"✅ 消息序列修复完成，共插入 {inserted_count} 个ToolMessage")
            self.logger.warning(separator)

            # 使用Overwrite包装器进行替换式更新（绕过reducer的追加行为）
            return {"messages": Overwrite(new_messages)}

        except Exception as e:
            # 记录失败不应阻断正常流程
            self.logger.error(f"❌ [MessageSequenceValidator] before_model 修复消息序列失败: {e}", exc_info=True)
            return None

    async def abefore_model(self, state: AgentState, runtime) -> Optional[Dict[str, Any]]:
        """异步版本的 before_model 钩子。"""
        return self.before_model(state, runtime)
