from langchain.tools import tool, ToolRuntime
from langchain.messages import HumanMessage

# 1、工具可以通过 runtime.state 访问当前对话状态
# 在工具签名中添加运行时：ToolRuntime 以访问状态。
# 这个参数会自动注入并对LLM隐藏L——它不会出现在工具的模式中。
@tool
def get_last_user_message(runtime: ToolRuntime) -> str:
    """Get the most recent message from the user."""
    messages = runtime.state["messages"]

    # Find the last human message
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return message.content

    return "No user messages found"

# Access custom state fields
# 运行时参数ToolRuntime对模型是隐藏的。以下面这个例子为例，模型只在工具的模式schema中看到 pref_name。
@tool
def get_user_preference(
    pref_name: str,
    runtime: ToolRuntime
) -> str:
    """Get a user preference value."""
    preferences = runtime.state.get("user_preferences", {})
    return preferences.get(pref_name, "Not set")

# 2、用 Command 来更新Agent的状态。这对需要更新自定义状态字段的工具非常有用：
from langgraph.types import Command
from langchain.tools import tool

@tool
def set_user_name(new_name: str) -> Command:
    """Set the user's name in the conversation state."""
    return Command(update={"user_name": new_name})

"""
当工具更新状态变量时，考虑为这些字段定义一个缩减器reducer 。
由于 LLM 可以并行调用多个工具，缩减器决定当同一状态字段被并发工具调用更新时，如何解决冲突。
"""

# 3、在工具中访问 （只读取） 对话过程中的不可变的runtime.context
# Context provides immutable configuration data that is passed at invocation time.
# Use it for user IDs, session details, or application-specific settings that shouldn’t change during a conversation.
# 上下文提供不可变的配置数据，这些配置数据在调用时传递。
# 用它来记录用户 ID、会话细节（每一次session可以认为是langgraph的一次执行）或应用特定设置，这些设置在对话中不应改变！！！！！！！！！！！！！！！！！！

from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime


USER_DATABASE = {
    "user123": {
        "name": "Alice Johnson",
        "account_type": "Premium",
        "balance": 5000,
        "email": "alice@example.com"
    },
    "user456": {
        "name": "Bob Smith",
        "account_type": "Standard",
        "balance": 1200,
        "email": "bob@example.com"
    }
}

@dataclass
class UserContext:
    user_id: str

@tool
def get_account_info(runtime: ToolRuntime[UserContext]) -> str:
    """Get the current user's account information."""
    user_id = runtime.context.user_id

    if user_id in USER_DATABASE:
        user = USER_DATABASE[user_id]
        return f"Account holder: {user['name']}\nType: {user['account_type']}\nBalance: ${user['balance']}"
    return "User not found"

model = ChatOpenAI(model="gpt-4.1")
agent = create_agent(
    model,
    tools=[get_account_info],
    context_schema=UserContext,
    system_prompt="You are a financial assistant."
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "What's my current balance?"}]},
    context=UserContext(user_id="user123")
)



""" 4、在工具访问读写长期记忆runtime.store
The BaseStore provides persistent storage that survives across conversations.
Unlike state (short-term memory), data saved to the store remains available in future sessions.
BaseStore 提供持久存储，能够在对话中存续。与状态（短期记忆）不同，存储中保存的数据在未来的会话中仍然可用。
Access the store through runtime.store. The store uses a namespace/key pattern to organize data:
通过 runtime.store 进入商店。存储使用命名空间/键模式来组织数据：
"""

from typing import Any
from langgraph.store.memory import InMemoryStore
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime


# Access memory
@tool
def get_user_info(user_id: str, runtime: ToolRuntime) -> str:
    """Look up user info."""
    store = runtime.store
    user_info = store.get(("users",), user_id)
    return str(user_info.value) if user_info else "Unknown user"

# Update memory
@tool
def save_user_info(user_id: str, user_info: dict[str, Any], runtime: ToolRuntime) -> str:
    """Save user info."""
    store = runtime.store
    store.put(("users",), user_id, user_info)  # 更新长期记忆
    return "Successfully saved user info."

store = InMemoryStore()
agent = create_agent(
    model,
    tools=[get_user_info, save_user_info],
    store=store
)

# First session: save user info
agent.invoke({
    "messages": [{"role": "user", "content": "Save the following user: userid: abc123, name: Foo, age: 25, email: foo@langchain.dev"}]
})

# Second session: get user info
agent.invoke({
    "messages": [{"role": "user", "content": "Get user info for user with id 'abc123'"}]
})
# Here is the user info for user with ID "abc123":
# - Name: Foo
# - Age: 25
# - Email: foo@langchain.dev


"""5、
Stream real-time updates from tools during execution. 
This is useful for providing progress feedback to users during long-running operations.
在执行过程中实时传输工具的更新。这对于在长期运行的作中向用户反馈进展非常有用。
Use runtime.stream_writer to emit custom updates:
使用 runtime.stream_writer 发布自定义更新：
"""
from langchain.tools import tool, ToolRuntime

@tool
def get_weather(city: str, runtime: ToolRuntime) -> str:
    """Get weather for a given city."""
    writer = runtime.stream_writer

    # Stream custom updates as the tool executes
    writer(f"Looking up data for city: {city}")
    writer(f"Acquired data for city: {city}")

    return f"It's always sunny in {city}!"

"""
If you use runtime.stream_writer inside your tool, the tool must be invoked within a LangGraph execution context.
See Streaming for more details.
如果你在工具中使用 runtime.stream_writer，必须在 LangGraph 执行上下文中调用该工具。详情请参见 “流媒体 ”。
"""


"""6、
You can choose different return values for your tools:
你可以为工具选择不同的回报值：
Return a string for human-readable results.
返回字符串以获得人类可读的结果。
Return an object for structured results the model should parse.
返回一个对象 ，用于模型应解析的结构化结果。
Return a Command with optional message when you need to write to state.
需要写入状态时返回一个带可选消息的命令 。
​
Return a string  返回字符串
Return a string when the tool should provide plain text for the model to read and use in its next response.
当工具应提供明文供模型阅读并在下一个响应中使用时，返回字符串。
  收到
from langchain.tools import tool


@tool
def get_weather(city: str) -> str:
    # Get weather for a city.
    return f"It is currently sunny in {city}."
Behavior:  行为：
The return value is converted to a ToolMessage.
返回值被转换为 ToolMessage。
The model sees that text and decides what to do next.
模型看到这些文本后决定下一步该做什么。
No agent state fields are changed unless the model or another tool does so later.
除非模型或其他工具之后更改，否则不会更改代理状态字段。
Use this when the result is naturally human-readable text.
当结果自然可读时，使用这个方法。
Return an object  返回对象
Return an object (for example, a dict) when your tool produces structured data that the model should inspect.
当你的工具产生结构化数据，模型需要检查时，返回一个对象（例如一个字典 ）。
  收到
from langchain.tools import tool


@tool
def get_weather_data(city: str) -> dict:
    # Get structured weather data for a city.
    return {
        "city": city,
        "temperature_c": 22,
        "conditions": "sunny",
    }
Behavior:  行为：
The object is serialized and sent back as tool output.
该对象被序列化并作为工具输出返回。
The model can read specific fields and reason over them.
模型可以读取特定字段并对其进行推理。
Like string returns, this does not directly update graph state.
与字符串返回类似，这不会直接更新图状态。
Use this when downstream reasoning benefits from explicit fields instead of free-form text.
当下游推理受益于显式字段而非自由文本时，可以使用此方法。
​
Return a Command  返回命令
Return a Command when the tool needs to update graph state (for example, setting user preferences or app state). You can return a Command with or without including a ToolMessage. If the model needs to see that the tool succeeded (for example, to confirm a preference change), include a ToolMessage in the update, using runtime.tool_call_id for the tool_call_id parameter.
当工具需要更新图表状态（例如设置用户偏好设置或应用状态）时返回命令 。你可以返回命令， 也可以不包含 ToolMessage。如果模型需要确认工具成功（例如确认偏好变更），则在更新中包含 ToolMessage，runtime.tool_call_id 作为 tool_call_id 参数。
  收到
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command


@tool
def set_language(language: str, runtime: ToolRuntime) -> Command:
    # Set the preferred response language.
    return Command(
        update={
            "preferred_language": language,
            "messages": [
                ToolMessage(
                    content=f"Language set to {language}.",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )
Behavior:  行为：
The command updates state using update.
命令 update 状态是使用 update。
Updated state is available to subsequent steps in the same run.
更新状态可用于同一运行中的后续步骤。
Use reducers for fields that may be updated by parallel tool calls.
对于可能通过并行工具调用更新的字段，使用缩减器。
Use this when the tool is not just returning data, but also mutating agent state.
当工具不仅返回数据，还返回变异的代理状态时，可以使用这个方法。

"""