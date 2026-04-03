"""
The simplest way to create a tool is with the @tool decorator. 
By default, the function’s docstring becomes the tool’s description that helps the model understand when to use it:
制作工具最简单的方式是用 @tool 装饰师。默认情况下，函数的文档字符串成为工具的描述，帮助模型了解何时使用：

"""
from langchain.tools import tool
from langchain_core.tools import StructuredTool
from rich.pretty import pprint


@tool
def search_database(query: str, limit: int = 10) -> str:
    """在客户数据库中搜索与查询条件匹配的记录。

    参数：
        query: 用于查找的搜索关键词
        limit: 返回结果的最大数量
    """
    return f"Found {limit} results for '{query}'"
pprint(search_database)
# search_database(query="name", limit=5)直接调用StructuredTool对象（因为加了@tool装饰器）会报错，必须使用invoke方法调用它
res = search_database.invoke("name", limit=5)
pprint(res)
"""
StructuredTool(
│   name='search_database',
│   description='Search the customer database for records matching the query.\n\n    Args:\n        query: Search terms to look for\n        limit: Maximum number of results to return',
│   args_schema=<class 'langchain_core.utils.pydantic.search_database'>,
│   func=<function search_database at 0x000001D9DDC504A0>
)
"""

# 可以通过 @tool(name, description) 自定义工具名称和描述
@tool("calculator", description="Performs arithmetic calculations. Use this for any math problems.")
def calc(expression: str) -> str:
    """Evaluate mathematical expressions."""
    return str(eval(expression))


pprint(calc)
"""
StructuredTool(
│   name='calculator',
│   description='Performs arithmetic calculations. Use this for any math problems.',
│   args_schema=<class 'langchain_core.utils.pydantic.calculator'>,
│   func=<function calc at 0x000001453836EAC0>
)
"""
# 用 Pydantic 模型定义复杂的工具输入：
from pydantic import BaseModel, Field
from typing import Literal

class WeatherInput(BaseModel):
    """Input for weather queries."""
    location: str = Field(description="City name or coordinates")
    units: Literal["celsius", "fahrenheit"] = Field(
        default="celsius",
        description="Temperature unit preference"
    )
    include_forecast: bool = Field(
        default=False,
        description="Include 5-day forecast"
    )

@tool(args_schema=WeatherInput)
def get_weather(location: str, units: str = "celsius", include_forecast: bool = False) -> str:
    """Get current weather and optional forecast."""
    temp = 22 if units == "celsius" else 72
    result = f"Current weather in {location}: {temp} degrees {units[0].upper()}"
    if include_forecast:
        result += "\nNext 5 days: Sunny"
    return result
















