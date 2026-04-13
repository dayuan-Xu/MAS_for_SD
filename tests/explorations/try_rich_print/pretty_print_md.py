from rich.console import Console
from rich.markdown import Markdown

console = Console()

# 渲染 Markdown 内容
md_content = """
# 一级标题

这是一段**粗体**和*斜体*文本。

## 代码示例（二级标题）

```python
 def hello(): print("Hello, World!")
```

- 列表项 1
- 列表项 2

## PyCharm 终端/运行面板 渲染对比（二级标题）
| 场景 | 效果 | 解决方案 |
|------|------|----------|
| PyCharm「终端」标签页 | ✅ 完美渲染，开箱即用 | 直接运行脚本 |
| PyCharm「运行」标签页 | ❌ 纯文本，无样式 | 加 `force_terminal=True`也没有用 |

"""
markdown = Markdown(md_content)
console.print(markdown)


# 写一个美化打印md内容的str到终端的函数
def print_md(str_with_md_content):
    console.print(Markdown(str_with_md_content))
