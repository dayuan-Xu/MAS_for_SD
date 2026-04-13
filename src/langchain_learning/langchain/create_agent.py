from langchain.agents import create_agent
from rich.pretty import pprint

from src.config.llm import LLMs

####            构建一个简单智能体：只有一个base model、一个简单tool、一个简单的系统提示

llm = LLMs["gpt-5-mini"]

# def get_weather(city: str) -> str:
#     """Get weather for a given city."""
#     return f"{city}总是晴天!"
#

# agent = create_agent(
#     model=llm,
#     tools=[get_weather],
#     system_prompt="你是一名乐于助人的助手",
# )
#
# # Run the agent
# agent.invoke(
#     {"messages": [
#         {"role": "user", "content": "sf的天气如何"}
#     ]
#     }
# )

"""
                    接下来构建一个真实世界的智能体：
                    1、详细的系统提示词              2、结合了外部数据的多个工具
                    3、model具备配置，响应更一致      4、结构化输出，结果可预测
                    5、具备对话式的记忆，允许对话交互   6、创建并运行智能体，测试功能完整性
"""

# 1、创建一个系统提示词：明确具体+可执行
SYSTEM_PROMPT = """你是一位专业的天气预报员，说话喜欢用双关语。

你可以使用两个工具：

- get_weather_for_location：用于获取特定位置的天气
- get_user_location：用于获取用户的位置

如果用户询问天气，确保你知道位置信息。
如果从问题中能看出他们指的是当前位置，使用 get_user_location 工具查找他们的位置。"""

# 2、工具 可以通过调用你定义的函数，让模型与外部系统交互。
# 工具依赖运行时上下文 ，也可以与代理记忆交互。
# 通过@tool将一个函数转换为langchain中的tool对象，作用有2个：
"""
1、给函数加元数据（告诉大模型：这个函数是干嘛的、怎么用）；
2、只要函数声明了ToolRuntime类型的参数，就能实现运行时注入（让函数能拿到调用时的实时上下文，比如当前对话、用户信息）
 LangChain’s @tool decorator adds metadata and enables runtime injection with the ToolRuntime parameter!!!!
"""
from dataclasses import dataclass
from langchain.tools import tool, ToolRuntime

@tool
def get_weather_at_location(city: str) -> str:
    """获取指定城市的天气."""
    return f"{city}总是晴天!"

# # 查看装饰器自动添加的元数据
# print(get_weather_at_location.name)       # 函数名：get_weather
# print(get_weather_at_location.description)# 函数描述：查询指定城市的天气...
# print(get_weather_at_location.args)       # 参数信息：{"city": {"title": "City", "type": "string"}}

@dataclass
class Context:
    """Custom runtime context schema."""
    user_id: str

@tool
def get_user_location(runtime: ToolRuntime[Context]) -> str:
    """从运行时上下文中检索出用户id"""
    pprint(runtime)
    user_id = runtime.context.user_id
    return "Florida" if user_id == "1" else "SF"

# 3、根据你的用例为语言模型设置合适的参数

# 4、定义响应格式
from dataclasses import dataclass
# We use a dataclass here, but Pydantic models are also supported.
@dataclass
class ResponseFormat:
    """智能体的响应"""
    # 俏皮的双关语回答（必填）
    punny_response: str
    # 任何关于天气的有趣信息（如果有的话）
    weather_conditions: str | None = None

# 5、添加短期记忆
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()

# 6、创建运行代理
from langchain.agents.structured_output import ToolStrategy

agent1 = create_agent(
    model=llm,
    system_prompt=SYSTEM_PROMPT,
    tools=[get_user_location, get_weather_at_location],
    context_schema=Context,
    response_format=ToolStrategy(ResponseFormat),   # 通过工具调用策略实现结构化响应，该结构化响应最终会保存在graph state中的一个叫为`structured_response`的key中
    checkpointer=checkpointer,
    name="天气播报员",
)

# `thread_id` is a unique identifier for a given conversation.
config = {"configurable": {"thread_id": "1"}}

# input_text = "外面的天气如何？"
input_text = "给我讲一个关于狗狗的笑话？"

input_state = {
    "messages": [
        {
            "role": "user",
            "content": input_text,
        },
    ],
}

response = agent1.invoke(
    input_state,
    config=config,
    context=Context(user_id="1")
)


pprint(response)

pprint(response['structured_response'])


# # 注意！我们可以通过同一个thread_id继续对话
# response = agent1.invoke(
#     {"messages": [{"role": "user", "content": "谢谢你!"}]},
#     config=config,
#     context=Context(user_id="1")
# )
# pprint(response['messages'][-1])