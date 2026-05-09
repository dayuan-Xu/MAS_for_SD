"""MCP工具调用拦截器 - 用于处理工具返回结果"""
import json
import logging
import re
from typing import Callable, Awaitable

from langchain_core.messages import ToolMessage
from langchain_mcp_adapters.interceptors import (
    MCPToolCallRequest,
    MCPToolCallResult,
    ToolCallInterceptor,
)
from mcp.types import TextContent, CallToolResult

logger = logging.getLogger(__name__)


class MCPMonitorInterceptor(ToolCallInterceptor):
    """MCP工具执行监控拦截器
    
    记录MCP工具的完整执行流程，包括：
    - 工具调用请求的详细信息（工具名、参数等）
    - 工具执行结果(str)
    
    用于调试和了解MCP工具的执行过程。
    """

    def __init__(self, tool_names: set[str] | None = None, log_level: str = "INFO"):
        """初始化监控拦截器
        
        Args:
            tool_names: 需要监控的工具名称集合。如果为None，则监控所有工具。
            log_level: 日志级别，默认为"INFO"
        """
        self.tool_names = tool_names
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)

    async def __call__(
            self,
            request: MCPToolCallRequest,
            handler: Callable[[MCPToolCallRequest], Awaitable[MCPToolCallResult]],
    ) -> MCPToolCallResult:
        """执行监控逻辑
        
        Args:
            request: 工具调用请求
            handler: 原始工具调用处理器
            
        Returns:
            工具调用结果
        """
        # 如果明确指定了要监控哪些工具，则检查是否需要监控此工具
        if self.tool_names and request.name not in self.tool_names:
            return await handler(request)

        # 记录工具调用请求
        logger.log(
            self.log_level,
            f"\n{'=' * 80}\n"
            f"[MCP工具调用] 开始执行\n"
            f"{'=' * 80}\n"
            f"MCP服务器名称: {request.server_name}，工具名称: {request.name}\n"
            f"调用参数:\n{json.dumps(request.args, ensure_ascii=False, indent=2)}\n"
            f"{'=' * 80}"
        )

        # 执行原始工具调用
        try:
            result = await handler(request)

            # 记录工具执行结果
            result_summary = self._summarize_result(result)
            logger.log(
                self.log_level,
                f"\n{'=' * 80}\n"
                f"[MCP工具完成] 执行完毕\n"
                f"{'=' * 80}\n"
                f"MCP服务器名称: {request.server_name}，工具名称: {request.name}\n"
                f"结果摘要:\n{result_summary}\n"
                f"{'=' * 80}\n"
            )

            return result

        except Exception as e:
            # 记录工具执行异常
            logger.log(
                self.log_level,
                f"\n{'=' * 80}\n"
                f"❌ [MCP工具失败] 执行异常\n"
                f"{'=' * 80}\n"
                f"工具名称: {request.name}\n"
                f"异常类型: {type(e).__name__}\n"
                f"异常信息: {str(e)}\n"
                f"{'=' * 80}\n",
                exc_info=True
            )
            return ToolMessage(
                content=f"MCP工具执行异常，请检查日志。\n"
                        f"工具名称: {request.name}\n"
                        f"异常类型: {type(e).__name__}\n"
                        f"异常信息: {str(e)}",
                tool_call_id=result.tool_call_id
            )

    def _summarize_result(self, result: MCPToolCallResult) -> str:
        """生成结果摘要
            
        Args:
            result: 工具调用结果，可能是 CallToolResult 或 ToolMessage
                
        Returns:
            结果摘要字符串
        """
        # 处理 CallToolResult
        if isinstance(result, CallToolResult):
            logger.log(
                self.log_level,
                f"MCP工具返回结果封装在 CallToolResult:\n"

            )
            if not result.content:
                return "(无内容)"

            summaries = [f"1. isError：{result.isError}", "2. 智能体所见文本内容预览："]
            for i, content_block in enumerate(result.content):
                if isinstance(content_block, TextContent):
                    text = content_block.text
                    text_length = len(text)
                    # 限制显示长度
                    if text_length > 500:
                        preview = text[:250] + "...[已截断]..." + text[-250:]
                    else:
                        preview = text
                    summaries.append(f"  [{i}] TextContent (长度: {text_length}字符):\n{preview}")
                else:
                    summaries.append(f"  [{i}] {type(content_block).__name__}")

            return "\n".join(summaries)

        # 处理 ToolMessage，说明被内层拦截器短路返回（缓存命中）或者内层拦截器遇到异常情况返回，内层可能没有真正成功调用 MCP工具
        elif isinstance(result, ToolMessage):
            logger.log(
                self.log_level,
                f"MCP工具返回结果封装在 ToolMessage:\n"
            )
            content = result.content

            # 如果内容为空
            if not content:
                return "(无内容)"

            # 如果内容是字符串
            if isinstance(content, str):
                if len(content) > 500:
                    preview = content[:250] + "...[已截断]..." + content[-250:]
                else:
                    preview = content
                return f"  Text (长度: {len(content)}字符):\n{preview}"

            # 如果内容是列表
            elif isinstance(content, list):
                summaries = []
                for i, item in enumerate(content):
                    if isinstance(item, str):
                        if len(item) > 500:
                            preview = item[:250] + "...[已截断]..." + item[-250:]
                        else:
                            preview = item
                        summaries.append(f"  [{i}] String (长度: {len(item)}字符):\n{preview}")
                    elif isinstance(item, dict):
                        # 尝试将字典格式化为JSON字符串
                        try:
                            json_str = json.dumps(item, ensure_ascii=False, indent=2)
                            if len(json_str) > 500:
                                preview = json_str[:250] + "...[已截断]..." + json_str[-250:]
                            else:
                                preview = json_str
                            summaries.append(f"  [{i}] Dict:\n{preview}")
                        except Exception:
                            summaries.append(f"  [{i}] Dict: {str(item)[:200]}")
                    else:
                        summaries.append(f"  [{i}] {type(item).__name__}: {str(item)[:200]}")

                return "\n".join(summaries)

            else:
                return f"  {type(content).__name__}: {str(content)[:200]}"

        # 其他未知类型
        else:
            return f"未知的 MCPToolCallResult 类型 {type(result).__name__}: {str(result)[:200]}"


class UnicodeDecodeInterceptor(ToolCallInterceptor):
    """解码Unicode转义格式的文本为可读文本
    
    将MCP工具返回结果中的"\\u6d4f\\u9633\\u70df\\u82b1\\u5382"
    解码为可读的中文文本"浏阳烟花厂"
    
    处理范围：
    - CallToolResult.content 中的 TextContent.text
    - ToolMessage.content 中的字符串内容
    

    """

    async def __call__(
            self,
            request: MCPToolCallRequest,
            handler: Callable[[MCPToolCallRequest], Awaitable[MCPToolCallResult]],
    ) -> MCPToolCallResult:
        """执行解码逻辑
        
        Args:
            request: 工具调用请求
            handler: 原始工具调用处理器
            
        Returns:
            解码后的工具调用结果
        """
        # 执行原始工具调用
        result = await handler(request)

        # 对结果进行解码
        logger.info(f"开始解码MCP工具返回结果中unicode转义格式的文本")
        decoded_result = self._decode_unicode(result)
        logger.info(f"MCP工具返回结果解码完成")

        return decoded_result

    def _decode_unicode(self, result: MCPToolCallResult) -> MCPToolCallResult:
        """对MCP工具返回结果进行解码
        
        Args:
            result: 原始工具调用结果
            
        Returns:
            解码后的结果
        """
        # 处理 CallToolResult
        if isinstance(result, CallToolResult):
            return self._decode_call_tool_result(result)

        # 处理 ToolMessage
        elif isinstance(result, ToolMessage):
            return self._decode_tool_message(result)

        # 其他类型直接返回
        else:
            logger.warning(f"未知的 MCPToolCallResult 类型: {type(result).__name__}")
            return result

    def _decode_call_tool_result(self, result: CallToolResult) -> CallToolResult:
        """解码 CallToolResult 中的 Unicode转义格式的文本
        
        Args:
            result: 原始的 CallToolResult
            
        Returns:
            解码后的 CallToolResult
        """
        if not result.content:
            return result

        # 遍历所有 content blocks，解码 TextContent
        decoded_content = []
        for content_block in result.content:
            if isinstance(content_block, TextContent):
                # 解码 TextContent 中的文本
                decoded_text = self._decode_unicode_string(content_block.text)
                # 创建新的 TextContent 对象（保持其他属性不变）
                decoded_content.append(
                    TextContent(
                        type=content_block.type,
                        text=decoded_text,
                        annotations=content_block.annotations if hasattr(content_block, 'annotations') else None
                    )
                )
            else:
                # 非 TextContent 类型保持不变
                decoded_content.append(content_block)

        # 创建新的 CallToolResult
        return CallToolResult(
            content=decoded_content,
            structuredContent=result.structuredContent,
            isError=result.isError
        )

    def _decode_tool_message(self, result: ToolMessage) -> ToolMessage:
        """解码 ToolMessage 中的 Unicode转义格式的文本
        
        Args:
            result: 原始的 ToolMessage
            
        Returns:
            解码后的 ToolMessage
        """
        content = result.content

        # 如果内容为空，直接返回
        if not content:
            return result

        # 如果内容是字符串，直接解码
        if isinstance(content, str):
            decoded_content = self._decode_unicode_string(content)
            return ToolMessage(
                content=decoded_content,
                tool_call_id=result.tool_call_id,
                name=result.name if hasattr(result, 'name') else None,
                status=result.status if hasattr(result, 'status') else None,
                additional_kwargs=result.additional_kwargs if hasattr(result, 'additional_kwargs') else {}
            )

        # 如果内容是列表，遍历解码每个字符串元素
        elif isinstance(content, list):
            decoded_content = []
            for item in content:
                if isinstance(item, str):
                    decoded_content.append(self._decode_unicode_string(item))
                else:
                    # 非字符串元素保持不变
                    decoded_content.append(item)

            return ToolMessage(
                content=decoded_content,
                tool_call_id=result.tool_call_id,
                name=result.name if hasattr(result, 'name') else None,
                status=result.status if hasattr(result, 'status') else None,
                additional_kwargs=result.additional_kwargs if hasattr(result, 'additional_kwargs') else {}
            )

        # 其他类型直接返回
        else:
            return result

    def _decode_unicode_string(self, text: str) -> str:
        """解码字符串中的 Unicode 转义格式的文本
        
        使用正则表达式精确匹配并解码 \\uXXXX 格式的字符，
        避免影响字符串中的其他内容（如已存在的中文字符）。
        
        Args:
            text: 包含 Unicode 转义字符的字符串
            
        Returns:
            解码后的字符串

        示例：
            转换前的打印输出: "button with text '\u767e\u5ea6\u4e00\u4e0b' at index [436]"
            转换后的打印输出: "button with text '百度一下' at index [436]"
        """
        if not text or not isinstance(text, str):
            return text

        try:
            # 检查转换前打印出来的文本中是否包含 Unicode转义格式的文本
            if r'\u' not in text:
                logger.info(f"字符串 {text} 中不存在 Unicode转义格式的文本，直接返回")
                return text

            # 使用正则表达式匹配 \uXXXX 模式并逐个解码
            def replace_unicode_escape(match):
                """将匹配的 \\uXXXX文本 转换为对应的 Unicode 字符"""
                unicode_hex = match.group(1)
                try:
                    # 将十六进制字符串转换为整数，再转换为 Unicode 字符
                    return chr(int(unicode_hex, 16))
                except (ValueError, OverflowError):
                    # 如果转换失败，保留原始文本
                    return match.group(0)

            # 匹配 \uXXXX 模式的文本（4个十六进制数字）
            decoded = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode_escape, text)
            logger.debug(f"Unicode转义格式的文本转换成功: {text} -> {decoded}")
            return decoded

        except Exception as e:
            # 捕获其他异常，确保不会中断执行
            logger.warning(f"Unicode转义格式的文本解码过程中发生未知错误: {str(e)[:100]}, 保留原始文本")
            return text
