"""系统提示词注入中间件

该中间件用于在模型调用前将自定义提示词文本注入到 system message 中。

核心功能：
1. 在初始化时接收提示词文本
2. 在 wrap_model_call 和 awrap_model_call 时将提示词追加到 system message
3. 支持同步和异步模型调用

使用场景：
- 为特定智能体动态添加系统指令
- 在不同任务阶段注入不同的提示词
- 实现灵活的提示词管理策略
"""

import logging
from typing import Any, Callable

from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware.types import AgentMiddleware, AgentState, ContextT, ModelRequest, ModelResponse, ResponseT

logger = logging.getLogger(__name__)


class SystemPromptInjectMiddleware(AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]):
    """系统提示词注入中间件
    
    该中间件在模型调用前将初始化时传入的提示词文本注入到 system message 中。
    
    工作原理：
    1. 初始化时接收提示词文本
    2. 在 wrap_model_call/awrap_model_call 钩子中，使用 append_to_system_message 将提示词追加到现有 system message
    3. 将更新后的 system message 传递给 handler
    
    Example:
        ```python
        from src.custom_middleware.prompt_inject import SystemPromptInjectMiddleware
        
        # 创建中间件实例，传入要注入的提示词
        prompt_inject = SystemPromptInjectMiddleware(
            prompt="你是一个专业的软件工程师，擅长编写高质量的代码。"
        )
        
        # 在创建智能体时添加到 middleware 列表
        agent = create_agent(
            model=llm,
            tools=tools,
            middleware=[
                prompt_inject,
                # ... other middleware
            ],
        )
        ```
    """

    def __init__(self, prompt: str):
        """初始化系统提示词注入中间件
        
        Args:
            prompt: 要注入到 system message 的提示词文本
        """
        if not prompt or not prompt.strip():
            raise ValueError("prompt 不能为空")
        
        self.prompt = prompt.strip()
        logger.info(f"SystemPromptInjectMiddleware 初始化完成，提示词长度: {len(self.prompt)} 字符")
        logger.debug(f"注入的提示词内容:\n{self.prompt}")

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        """在模型调用前注入提示词到 system message
        
        Args:
            request: 模型调用请求，包含当前的 system message
            handler: 内部处理器
            
        Returns:
            模型调用响应
        """
        logger.debug("📝 [PromptInject] 开始注入系统提示词")
        
        # 将提示词追加到现有的 system message
        new_system_message = append_to_system_message(request.system_message, self.prompt)
        
        # 使用更新后的 system message 调用 handler
        return handler(request.override(system_message=new_system_message))

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Any],
    ) -> ModelResponse[ResponseT]:
        """异步版本的模型调用前提示词注入
        
        Args:
            request: 模型调用请求，包含当前的 system message
            handler: 内部处理器
            
        Returns:
            模型调用响应
        """
        logger.debug("📝 [PromptInject] 开始异步注入系统提示词")
        
        # 将提示词追加到现有的 system message
        new_system_message = append_to_system_message(request.system_message, self.prompt)
        
        # 使用更新后的 system message 调用 handler
        return await handler(request.override(system_message=new_system_message))
