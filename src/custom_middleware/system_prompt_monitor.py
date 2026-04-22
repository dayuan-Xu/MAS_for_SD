from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from rich.console import Console
from rich.markdown import Markdown
from typing import Callable


class MyMonitorMiddleware(AgentMiddleware):
    def __init__(self, enabled: bool = True):
        """初始化监控中间件

        Args:
            enabled: 是否启用监控功能。默认为 True。
                    如果设为 False，wrap_model_call 将直接调用 handler，不打印任何内容。
        """
        self.enabled = enabled
        self.console = Console()

    def _render_markdown_content(self, content):
        """
        递归渲染 Markdown 内容，支持多种格式

        Args:
            content: 可能是 str、list[str]、list[dict] 或其他类型
        """
        if content is None:
            return

        # 情况1：纯字符串
        if isinstance(content, str):
            if content.strip():  # 只渲染非空字符串
                self.console.print(Markdown(content))
            return

        # 情况2：列表类型
        if isinstance(content, list):
            for item in content:
                # 子项是字符串
                if isinstance(item, str):
                    if item.strip():
                        self.console.print(Markdown(item))
                # 子项是字典（OpenAI 消息格式）
                elif isinstance(item, dict):
                    if item.get("type") == "text":
                        text_content = item.get("text", "")
                        if text_content:
                            self.console.print(Markdown(text_content))
                    # 处理其他类型的 content（如 image_url 等）
                    elif item.get("type"):
                        self.console.print(f"[yellow]⚠ 跳过非文本内容类型: {item.get('type')}[/yellow]")
                else:
                    # 其他未知类型，尝试转换为字符串
                    try:
                        self.console.print(Markdown(str(item)))
                    except Exception as e:
                        self.console.print(f"[red]⚠ 无法渲染内容: {e}[/red]")
            return

        # 情况3：其他类型，尝试转换
        try:
            self.console.print(Markdown(str(content)))
        except Exception as e:
            self.console.print(f"[red]⚠ 无法渲染内容类型 {type(content)}: {e}[/red]")

    def wrap_model_call(
            self,
            request: ModelRequest,
            handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """包装模型调用，美化打印系统提示词

        如果 enabled=False，则直接调用 handler，不执行任何监控逻辑。
        """
        # 如果未启用监控，直接调用 handler
        if not self.enabled:
            return handler(request)

        # 启用监控时，打印系统提示词
        if request.system_message:
            self.console.print("=" * 41, " MyMonitorMiddleware ", "=" * 41, sep=" ")
            self.console.print("\n[bold cyan]📋 System Prompt:[/bold cyan]")
            self.console.print("[cyan]" + "─" * 60 + "[/cyan]")
            self._render_markdown_content(request.system_message.content)
            self.console.print("[cyan]" + "─" * 60 + "[/cyan]\n")

        return handler(request)
