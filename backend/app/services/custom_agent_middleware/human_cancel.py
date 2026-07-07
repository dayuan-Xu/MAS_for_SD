import asyncio
import logging

from langchain.agents.middleware.types import AgentMiddleware


class TaskCancelledException(Exception):
    """任务被用户中止时抛出，由CancelAwareMiddleware在before_model钩子中触发"""

    pass


class CancelAwareMiddleware(AgentMiddleware):
    """感知用户中止操作的智能体中间件

    在每次模型调用前（before_model钩子）检查中止标志：
    - 用户点击中止按钮时，会设置智能体团队执行中止标志（cancel_event.set()）
    - 所有正在运行中的智能体（Alice、Bob、Eva）在下次模型调用前都会检测到此标志
    - 检测到标志后抛出TaskCancelledException，中止当前智能体的执行

    该异常与ToolRetryMiddleware配合工作：
    - 如果异常发生在工具调用中（wrap_tool_call内）：
      ToolRetryMiddleware的should_retry检测到TaskCancelledException时返回False（不重试），
      然后on_failure构造中止ToolMessage返回给LLM，让LLM知道任务被中止从而优雅结束。
    - 如果异常发生在模型调用前（before_model钩子）：
      异常向上传播，由AgentTeam的执行循环捕获处理。
    """

    def __init__(
        self,
        cancel_event: asyncio.Event,
        task_name: str,
        agent_name: str = "unknown",
    ):
        self.cancel_event = cancel_event
        self.task_name = task_name
        self.agent_name = agent_name
        self.logger = logging.getLogger(__name__)

    def before_model(self, state, runtime):
        """模型调用前的同步钩子：检查智能体团队执行中止标志"""
        if self.cancel_event.is_set():
            self.logger.info(
                f"🛑 [{self.agent_name}] 检测到任务中止标志，"
                f"停止智能体模型调用: {self.task_name}"
            )
            raise TaskCancelledException(
                f"任务 {self.task_name} 被用户中止（智能体: {self.agent_name}）"
            )
        return None

    async def abefore_model(self, state, runtime):
        """模型调用前的异步钩子：检查中止标志"""
        return self.before_model(state, runtime)
