"""MCP 工具错误处理中间件

该中间件用于捕获 MCP 工具执行过程中的异常，防止因工具执行失败导致智能体崩溃。

核心功能：
1. 捕获所有 MCP 工具调用异常
2. 将异常转换为友好的 ToolMessage 返回给智能体
3. 记录详细的错误日志便于调试
4. 允许智能体根据错误信息调整策略
"""

import logging
from typing import Callable, Any

from langchain.agents.middleware import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

logger = logging.getLogger(__name__)


class MCPToolErrorHandler(AgentMiddleware):
    """MCP 工具错误处理中间件
    
    该中间件包装所有工具调用，特别是 MCP 工具，确保执行失败时不会导致智能体崩溃。
    
    工作原理：
    1. 拦截所有工具调用请求
    2. 尝试执行工具
    3. 如果执行失败，捕获异常并返回包含错误信息的 ToolMessage
    4. 记录详细错误日志供后续分析
    
    Example:
        ```python
        from src.custom_middleware.mcp_tool_error_handler import MCPToolErrorHandler
        
        # 创建中间件实例
        mcp_error_handler = MCPToolErrorHandler()
        
        # 在创建智能体时添加到 middleware 列表
        agent = create_agent(
            model=llm,
            tools=mcp_tools,
            middleware=[
                mcp_error_handler,  # 放在重试中间件之前
                model_retry_middleware,
            ],
            checkpointer=checkpointer,
        )
        ```
    """

    def __init__(self, log_level: str = "WARNING"):
        """初始化 MCP 工具错误处理中间件
        
        Args:
            log_level: 错误日志级别，默认为 WARNING
        """
        self.log_level = getattr(logging, log_level.upper(), logging.WARNING)
        logger.info(f"MCPToolErrorHandler 初始化完成，日志级别: {log_level}")

    def wrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        """包装工具调用，添加错误处理
        
        Args:
            request: 工具调用请求
            handler: 内部处理器
            
        Returns:
            工具调用响应（成功结果或包含错误消息的 Command）
        """
        tool_name = request.tool_call.get("name", "unknown")
        tool_args = request.tool_call.get("args", {})
        tool_call_id = request.tool_call.get("id", "unknown")

        try:
            # 尝试执行工具
            logger.debug(f"🔧 [MCPErrorHandler] 开始执行工具: {tool_name}")
            logger.debug(f"   - 参数: {tool_args}")

            response = handler(request)

            logger.debug(f"✅ [MCPErrorHandler] 工具 {tool_name} 执行成功")
            return response

        except Exception as e:
            # 捕获所有异常，防止智能体崩溃
            error_type = type(e).__name__
            error_message = str(e)

            # 记录详细错误日志
            logger.log(
                self.log_level,
                f"❌ [MCPErrorHandler] 工具 {tool_name} 执行失败",
                exc_info=True
            )
            logger.log(self.log_level, f"   - 错误类型: {error_type}")
            logger.log(self.log_level, f"   - 错误信息: {error_message}")
            logger.log(self.log_level, f"   - 工具参数: {tool_args}")

            # 构建友好的错误消息返回给智能体
            friendly_error = (
                f"工具 '{tool_name}' 执行失败。\n"
                f"错误类型: {error_type}\n"
                f"错误详情: {error_message}\n\n"
                f"建议:\n"
                f"1. 检查输入参数是否正确\n"
                f"2. 确认工具使用场景是否合适\n"
                f"3. 尝试其他替代方案\n"
                f"4. 如果持续失败，请报告此问题"
            )

            # 返回包含错误信息的 Command
            return Command(
                update={
                    "messages": [ToolMessage(
                        content=friendly_error,
                        tool_call_id=tool_call_id,
                        name=tool_name,
                    )]
                }
            )

    async def awrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], Any],
    ) -> ToolMessage | Command[Any]:
        """异步版本的工具调用包装器
        
        Args:
            request: 工具调用请求
            handler: 内部处理器
            
        Returns:
            工具调用响应（成功结果或包含错误消息的 Command）
        """
        tool_name = request.tool_call.get("name", "unknown")
        tool_args = request.tool_call.get("args", {})
        tool_call_id = request.tool_call.get("id", "unknown")

        try:
            # 尝试执行工具
            logger.debug(f"🔧 [MCPErrorHandler] 开始异步执行工具: {tool_name}")
            logger.debug(f"   - 参数: {tool_args}")

            response = await handler(request)

            logger.debug(f"✅ [MCPErrorHandler] 工具 {tool_name} 异步执行成功")
            return response

        except Exception as e:
            # 捕获所有异常，防止智能体崩溃
            error_type = type(e).__name__
            error_message = str(e)

            # 记录详细错误日志
            logger.log(
                self.log_level,
                f"❌ [MCPErrorHandler] 工具 {tool_name} 异步执行失败",
                exc_info=True
            )
            logger.log(self.log_level, f"   - 错误类型: {error_type}")
            logger.log(self.log_level, f"   - 错误信息: {error_message}")
            logger.log(self.log_level, f"   - 工具参数: {tool_args}")

            # 构建友好的错误消息返回给智能体
            friendly_error = (
                f"工具 '{tool_name}' 执行失败。\n"
                f"错误类型: {error_type}\n"
                f"错误详情: {error_message}\n\n"
                f"建议:\n"
                f"1. 检查输入参数是否正确\n"
                f"2. 确认工具使用场景是否合适\n"
                f"3. 尝试其他替代方案\n"
                f"4. 如果持续失败，请报告此问题"
            )

            # 返回包含错误信息的 Command
            return Command(
                update={
                    "messages": [ToolMessage(
                        content=friendly_error,
                        tool_call_id=tool_call_id,
                        name=tool_name,
                    )]
                }
            )
