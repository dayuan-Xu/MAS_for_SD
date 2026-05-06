"""智能体活动监控中间件 - 记录 AI 响应和工具执行情况。

工作原理：
==========
【before_model 钩子】
  - 在每次模型调用前执行
  - 从 state 的消息历史中查找所有连续的 ToolMessage（支持并行工具调用）
  - 通过 tool_call_id 回溯找到对应的工具入参
  - 记录：工具名、工具入参、工具执行结果

【after_model 钩子】
  - 在每次模型调用后执行
  - 从 state 中获取最新的 AIMessage
  - 记录完整的 AI 响应内容（不截断）

执行顺序说明：
==============
假设中间件配置为：[AgentActivityMonitor, middleware2, middleware3]

before_model 执行顺序（正序）：
  1. AgentActivityMonitor.before_model()  ← 最先执行
  2. middleware2.before_model()
  3. middleware3.before_model()

after_model 执行顺序（逆序）：
  1. middleware3.after_model()
  2. middleware2.after_model()
  3. AgentActivityMonitor.after_model()  ← 最后执行

因此，将 AgentActivityMonitor 放在最外层（第一个位置），可以：
  - before_model: 看到原始的工具执行结果（未被其他中间件修改）
  - after_model: 看到所有中间件处理后的最终 AI 响应
"""

import logging
from typing import Any, Dict, Optional

from langchain.agents.middleware.types import AgentMiddleware, AgentState


class AgentActivityMonitor(AgentMiddleware[AgentState]):
    """智能体活动监控中间件。
    
    用于监控和记录智能体的活动，包括：
    1. 工具执行情况（工具名、入参、结果）
    2. AI 响应内容（完整记录，不截断）
    
    所有日志使用 DEBUG 级别记录，便于调试和问题排查。
    
    Example:
        ```python
        from src.custom_middleware.agent_activity_monitor import AgentActivityMonitor
        
        leader = create_agent(
            model=llm,
            middleware=[
                AgentActivityMonitor(),  # ⭐ 放在最外层
                todo_list_middleware,
                skills_middleware,
                # ... 其他中间件
                model_retry_middleware,  # 最内层
            ],
        )
        ```
    """

    def __init__(self):
        """初始化监控中间件。"""
        self.logger = logging.getLogger(__name__)

    def before_model(self, state: AgentState, runtime) -> Optional[Dict[str, Any]]:
        """模型调用前钩子 - 记录工具执行情况。
        
        从 state 的消息历史中查找所有连续的工具执行结果（支持并行工具调用），
        并通过 tool_call_id 回溯找到对应的工具入参。
        
        Args:
            state: 当前智能体状态，包含 messages 列表
            runtime: 运行时上下文
            
        Returns:
            None（不修改 state）
        """
        try:
            messages = state.get("messages", [])

            if not messages:
                return None

            # 从末尾向前查找所有连续的 ToolMessage（支持并行工具调用）
            tool_messages = []
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                if hasattr(msg, 'type') and msg.type == 'tool':
                    tool_messages.insert(0, (i, msg))  # 保持原始顺序
                else:
                    # 遇到非 ToolMessage 就停止（说明已经收集完上一轮的所有工具结果）
                    break

            if not tool_messages:
                # 没有工具执行记录，跳过
                return None

            separator = "=" * 80
            self.logger.info(separator)
            self.logger.info(f"🛠️ [AgentActivityMonitor] 工具执行详情 (共 {len(tool_messages)} 个工具)")
            self.logger.info(separator)

            # 处理每个工具执行结果
            for idx, (msg_index, tool_msg) in enumerate(tool_messages, 1):
                # 提取工具基本信息
                tool_name = getattr(tool_msg, 'name', 'unknown')
                tool_result = tool_msg.content
                tool_call_id = getattr(tool_msg, 'tool_call_id', None)

                # 向前查找对应的 AIMessage 中的 tool_call（获取入参）
                tool_args = {}
                if tool_call_id:
                    for j in range(msg_index - 1, -1, -1):
                        prev_msg = messages[j]
                        if hasattr(prev_msg, 'type') and prev_msg.type == 'ai':
                            # 查找匹配的 tool_call
                            if hasattr(prev_msg, 'tool_calls') and prev_msg.tool_calls:
                                for tc in prev_msg.tool_calls:
                                    if tc.get('id') == tool_call_id:
                                        tool_args = tc.get('args', {})
                                        break
                            break

                # 记录单个工具的详细信息
                self.logger.info(f"\n--- 工具 {idx}/{len(tool_messages)} ---")
                self.logger.info(f"工具名称: {tool_name}")
                self.logger.info(f"工具入参: {tool_args}")
                self.logger.info(f"执行结果:\n{tool_result}")

        except Exception as e:
            # 记录失败不应阻断正常流程
            self.logger.warning(f"⚠️ [AgentActivityMonitor] before_model 记录工具执行失败: {e}", exc_info=True)

        return None

    async def abefore_model(self, state: AgentState, runtime) -> Optional[Dict[str, Any]]:
        """异步版本的 before_model 钩子。"""
        return self.before_model(state, runtime)

    def after_model(self, state: AgentState, runtime) -> Optional[Dict[str, Any]]:
        """模型调用后钩子 - 记录 AI 响应。
        
        从 state 中获取最新的 AIMessage，记录完整的响应内容（不截断）。
        如果 AI 消息中包含工具调用请求，也会记录下来。
        
        Args:
            state: 当前智能体状态，包含 messages 列表
            runtime: 运行时上下文
            
        Returns:
            None（不修改 state）
        """
        try:
            messages = state.get("messages", [])

            if not messages:
                return None

            # 获取最后一条消息
            last_msg = messages[-1]

            # 只记录 AI 消息
            if not (hasattr(last_msg, 'type') and last_msg.type == 'ai'):
                return None

            separator = "=" * 80
            self.logger.info(separator)
            self.logger.info("🤖 [AgentActivityMonitor] AI 响应")
            self.logger.info(separator)

            # 记录 AI 文本内容
            if last_msg.content:
                self.logger.info(f"AI 回复内容:\n{last_msg.content}")

            # 记录工具调用请求（如果有）
            if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                self.logger.info(f"\n🔧 工具调用请求 (共 {len(last_msg.tool_calls)} 个):")
                for idx, tool_call in enumerate(last_msg.tool_calls, 1):
                    tool_name = tool_call.get('name', 'unknown')
                    tool_args = tool_call.get('args', {})
                    tool_id = tool_call.get('id', 'N/A')

                    self.logger.info(f"\n--- 工具调用 {idx}/{len(last_msg.tool_calls)} ---")
                    self.logger.info(f"工具名称: {tool_name}")
                    self.logger.info(f"调用ID: {tool_id}")
                    self.logger.info(f"调用参数: {tool_args}")

        except Exception as e:
            # 记录失败不应阻断正常流程
            self.logger.warning(f"⚠️ [AgentActivityMonitor] after_model 记录 AI 响应失败: {e}", exc_info=True)

        return None

    async def aafter_model(self, state: AgentState, runtime) -> Optional[Dict[str, Any]]:
        """异步版本的 after_model 钩子。"""
        return self.after_model(state, runtime)
