import logging
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from typing import Callable


class MyMonitorMiddleware(AgentMiddleware):
    def __init__(self, enabled: bool = True):
        """初始化监控中间件

        Args:
            enabled: 是否启用监控功能。默认为 True。
                    如果设为 False，wrap_model_call 将直接调用 handler，不打印任何内容。
        """
        self.enabled = enabled
        self.logger = logging.getLogger(__name__)

    def wrap_model_call(
            self,
            request: ModelRequest,
            handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """包装模型调用，记录系统提示词到日志

        如果 enabled=False，则直接调用 handler，不执行任何监控逻辑。
        """
        # 如果未启用监控，直接调用 handler
        if not self.enabled:
            return handler(request)

        # 启用监控时，记录系统提示词到日志
        if request.system_message:
            separator = "=" * 80
            self.logger.info(separator)
            self.logger.info("📋 MyMonitorMiddleware - System Prompt:")
            self.logger.info(separator)
            
            # 提取并记录系统提示词内容
            content = request.system_message.content
            if isinstance(content, str):
                # 只记录前500个字符，避免日志过长
                preview = content[:500] if len(content) > 500 else content
                self.logger.info(f"System prompt (preview):\n{preview}")
                if len(content) > 500:
                    self.logger.info(f"... (总长度: {len(content)} 字符，已截断)")
            else:
                self.logger.info(f"System prompt type: {type(content)}")
            
            self.logger.info(separator)

        return handler(request)
