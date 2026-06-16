"""Unicode编码错误处理中间件

该中间件用于在模型调用前捕获并处理消息中的代理字符（surrogate characters），
防止在模型调用时出现 UnicodeEncodeError。

核心功能：
1. 在 before_model 钩子中检查并清理新出现的 ToolMessage 中的代理字符
2. 维护已处理的 tool_call_id 集合，避免重复处理
3. 精确定位并记录包含代理字符的消息
4. 自动清理代理字符，确保模型调用不会因编码问题失败

设计优势：
- 在 before_model（即 after_tool）阶段处理，此时新消息都是工具返回结果
- 通过追踪已处理的 tool_call_id，每次仅处理未检查过的消息，提高效率
- 代理字符通常来自工具调用返回，在此阶段处理最为合理

使用场景：
- 处理 MCP 工具返回结果中的代理字符
- 处理外部数据源引入的无效 Unicode 字符
- 预防性地清理消息，避免模型调用时的编码错误
"""

import logging
from typing import Any, Annotated

from langchain.agents.middleware.types import AgentMiddleware, AgentState, ContextT, ResponseT, PrivateStateAttr
from langchain_core.messages import ToolMessage
from langgraph.types import Overwrite

logger = logging.getLogger(__name__)


class UnicodeEncodeErrorHandlerState(AgentState):
    """UnicodeEncodeErrorHandlerMiddleware 的状态 Schema。
    
    包含一个 processed_tool_call_ids 集合，用于记录已经检查并处理过的
    ToolMessage 的 tool_call_id，避免重复处理。
    """
    processed_tool_call_ids: Annotated[set[str], PrivateStateAttr]
    """已处理的 ToolMessage 的 tool_call_id 集合。PrivateStateAttr 表明这是内部状态，
    不会暴露在 InputSchema 或输出中，也不会由用户输入注入。"""


class UnicodeEncodeErrorHandlerMiddleware(AgentMiddleware[UnicodeEncodeErrorHandlerState, ContextT, ResponseT]):
    """Unicode编码错误处理中间件
    
    该中间件在 before_model 钩子中检查并清理新出现的 ToolMessage 中的代理字符，
    防止模型调用时出现 UnicodeEncodeError。
    
    工作原理：
    1. 在 before_model 钩子中，获取当前状态中的所有 ToolMessage
    2. 对比已处理的 tool_call_id 集合，找出未处理的新消息
    3. 检查这些新消息是否包含代理字符
    4. 如果发现代理字符，记录详细日志并清理
    5. 更新已处理的 tool_call_id 集合
    
    Example:
        ```python
        from src.custom_middleware.unicode_encode_error_handler import UnicodeEncodeErrorHandlerMiddleware
        
        # 创建中间件实例
        unicode_handler = UnicodeEncodeErrorHandlerMiddleware()
        
        # 在创建智能体时添加到 middleware 列表
        agent = create_agent(
            model=llm,
            tools=tools,
            middleware=[
                unicode_handler,
                # ... other middleware
            ],
        )
        ```
    """

    state_schema = UnicodeEncodeErrorHandlerState  # ⭐ 声明新的状态 Schema

    def before_model(self, state: UnicodeEncodeErrorHandlerState, runtime) -> dict | None:
        """在模型调用前检查并清理新出现的 ToolMessage 中的代理字符
        
        Args:
            state: 当前图状态
            runtime: 运行时上下文
            
        Returns:
            如果需要更新状态，返回包含 updates 的字典；否则返回 None
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        # 获取已处理的 tool_call_id 集合
        processed_ids = state.get("processed_tool_call_ids", set())

        # 如果 processed_tool_call_ids 不存在或为空，初始化为空集合
        if not isinstance(processed_ids, set):
            processed_ids = set()

        # 找出所有未处理的 ToolMessage
        new_tool_messages = []
        for idx, message in enumerate(messages):
            if isinstance(message, ToolMessage) and message.tool_call_id:
                if message.tool_call_id not in processed_ids:
                    new_tool_messages.append((idx, message))

        if not new_tool_messages:
            logger.debug("没有新的 ToolMessage 需要检查")
            return None

        logger.debug(f"发现 {len(new_tool_messages)} 条新的 ToolMessage 需要检查")

        # 检查并清理每条新消息
        cleaned_messages = []
        newly_processed_ids = set()

        for idx, message in new_tool_messages:
            has_surrogates, cleaned_content = self._check_and_clean_message(message)

            if has_surrogates:
                # 创建清理后的消息
                cleaned_message = message.model_copy(update={"content": cleaned_content})
                cleaned_messages.append((idx, cleaned_message))

                logger.warning(
                    f"检测到 ToolMessage 包含代理字符并已清理:\n"
                    f"  消息索引: {idx}\n"
                    f"  tool_call_id: {message.tool_call_id}\n"
                    f"  原始内容预览: {self._create_content_preview(self._extract_text_content(message.content))}\n"
                    f"  清理后预览: {self._create_content_preview(self._extract_text_content(cleaned_content))}"
                )
            else:
                logger.debug(
                    f"ToolMessage 不包含代理字符 (tool_call_id: {message.tool_call_id})"
                )

            # 标记为已处理
            newly_processed_ids.add(message.tool_call_id)

        # 如果没有需要清理的消息，只更新 processed_tool_call_ids
        if not cleaned_messages:
            updated_processed_ids = processed_ids | newly_processed_ids
            return {
                "processed_tool_call_ids": updated_processed_ids
            }

        # 构建更新后的消息列表
        updated_messages = list(messages)
        for idx, cleaned_message in cleaned_messages:
            updated_messages[idx] = cleaned_message

        # 更新 processed_tool_call_ids
        updated_processed_ids = processed_ids | newly_processed_ids

        logger.info(
            f"完成代理字符检查和清理:\n"
            f"  检查了 {len(new_tool_messages)} 条新消息\n"
            f"  清理了 {len(cleaned_messages)} 条包含代理字符的消息\n"
            f"  已处理的 tool_call_id 总数: {len(updated_processed_ids)}"
        )

        # 使用Overwrite包装器进行替换式更新（绕过reducer的追加行为）
        return {
            "messages": Overwrite(updated_messages),
            "processed_tool_call_ids": updated_processed_ids
        }

    async def abefore_model(self, state: UnicodeEncodeErrorHandlerState, runtime) -> dict | None:
        """异步版本的 before_model。
        
        Args:
            state: 当前图状态
            runtime: 运行时上下文
            
        Returns:
            如果需要更新状态，返回包含 updates 的字典；否则返回 None
        """
        return self.before_model(state, runtime)

    def _check_and_clean_message(self, message: ToolMessage) -> tuple[bool, Any]:
        """检查并清理消息中的代理字符
        
        Args:
            message: ToolMessage 对象
            
        Returns:
            (是否包含代理字符, 清理后的内容)
        """
        content = message.content

        if content is None:
            return False, content

        # 检查是否包含代理字符
        has_surrogates = self._content_has_surrogate_characters(content)

        if not has_surrogates:
            return False, content

        # 清理代理字符
        cleaned_content = self._clean_message_content(content)

        return True, cleaned_content

    def _content_has_surrogate_characters(self, content: Any) -> bool:
        """检查消息内容是否包含代理字符
        
        Args:
            content: 消息内容（可以是字符串或列表）
            
        Returns:
            True 如果包含代理字符，否则 False
        """
        if content is None:
            return False

        # 如果内容是字符串
        if isinstance(content, str):
            return self._text_has_surrogate_characters(content)

        # 如果内容是列表（多模态消息）
        if isinstance(content, list):
            for item in content:
                if isinstance(item, str):
                    if self._text_has_surrogate_characters(item):
                        return True
                elif isinstance(item, dict):
                    if self._dict_has_surrogate_characters(item):
                        return True

        return False

    def _text_has_surrogate_characters(self, text: str) -> bool:
        """检查文本是否包含代理字符
        
        Args:
            text: 要检查的文本
            
        Returns:
            True 如果包含代理字符，否则 False
        """
        if not text or not isinstance(text, str):
            return False

        try:
            # 尝试使用 UTF-8 编码，如果遇到代理字符会抛出 UnicodeEncodeError
            text.encode('utf-8')
            return False
        except UnicodeEncodeError:
            return True

    def _dict_has_surrogate_characters(self, item: dict) -> bool:
        """检查字典类型内容块是否包含代理字符
        
        Args:
            item: 内容块字典
            
        Returns:
            True 如果包含代理字符，否则 False
        """
        # 检查常见的文本字段
        for key in ['text', 'content']:
            if key in item and isinstance(item[key], str):
                if self._text_has_surrogate_characters(item[key]):
                    return True

        return False

    def _clean_message_content(self, content: Any) -> Any:
        """清理消息内容中的代理字符
        
        Args:
            content: 消息内容（可以是字符串或列表）
            
        Returns:
            清理后的内容
        """
        if content is None:
            return content

        # 如果内容是字符串
        if isinstance(content, str):
            return self._clean_text_content(content)

        # 如果内容是列表（多模态消息）
        if isinstance(content, list):
            cleaned_list = []
            for item in content:
                if isinstance(item, str):
                    cleaned_list.append(self._clean_text_content(item))
                elif isinstance(item, dict):
                    # 处理字典类型的内容块（如多模态内容）
                    cleaned_item = self._clean_dict_content(item)
                    cleaned_list.append(cleaned_item)
                else:
                    cleaned_list.append(item)
            return cleaned_list

        # 其他类型直接返回
        return content

    def _clean_text_content(self, text: str) -> str:
        """清理文本中的代理字符
        
        使用 surrogatepass 错误处理策略：
        - 先尝试用 surrogatepass 编码（保留代理字符）
        - 再用 replace 解码（将代理字符替换为 ）
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        if not text or not isinstance(text, str):
            return text

        try:
            # 检查是否包含代理字符
            if not self._text_has_surrogate_characters(text):
                return text

            # 使用 surrogatepass 编码，然后用 replace 解码
            # 这会将代理字符替换为 U+FFFD (REPLACEMENT CHARACTER)
            cleaned = text.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')

            logger.debug(f"已清理代理字符: {text[:50]}... -> {cleaned[:50]}...")
            return cleaned

        except Exception as e:
            logger.warning(f"清理代理字符时出错: {str(e)}，返回原始文本")
            return text

    def _clean_dict_content(self, item: dict) -> dict:
        """清理字典类型内容块中的代理字符
        
        Args:
            item: 内容块字典
            
        Returns:
            清理后的字典
        """
        cleaned_item = item.copy()

        # 处理常见的文本字段
        for key in ['text', 'content']:
            if key in cleaned_item and isinstance(cleaned_item[key], str):
                cleaned_item[key] = self._clean_text_content(cleaned_item[key])

        return cleaned_item

    def _extract_text_content(self, content: Any) -> str:
        """从消息内容中提取纯文本（用于日志）
        
        Args:
            content: 消息内容
            
        Returns:
            提取的文本
        """
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, dict) and 'text' in item:
                    texts.append(str(item['text']))
            return " ".join(texts)

        return str(content)

    def _create_content_preview(self, text: str, max_length: int = 100) -> str:
        """创建内容预览（用于日志）
        
        Args:
            text: 文本内容
            max_length: 最大长度
            
        Returns:
            预览字符串
        """
        if not text:
            return "(空内容)"

        # 截取前 max_length 个字符
        preview = text[:max_length]

        # 如果文本被截断，添加省略号
        if len(text) > max_length:
            preview += "..."

        # 转义换行符，使日志更易读
        preview = preview.replace('\n', '\\n').replace('\r', '\\r')

        return preview
