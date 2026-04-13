# 1、Read long-term memory in tools
# 在添加给智能体的预定义工具中，实现长期记忆的读取，前提是创建智能体create_agent时传入了一个store对象
# 这样框架底层才能有store对象注入到工具的运行时ToolRuntime对象中
from dataclasses import dataclass

from langchain_core.runnables import RunnableConfig
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langgraph.store.memory import InMemoryStore


@dataclass
class Context:
    user_id: str

# InMemoryStore saves data to an in-memory dictionary. Use a DB-backed store in production.
store = InMemoryStore()

# Write sample data to the store using the put method
store.put(
    ("users",),  # Namespace to group related data together (users namespace for user data)
    "user_123",  # Key within the namespace (user ID as key)
    {
        "name": "John Smith",
        "language": "English",
    }  # Data to store for the given user
)

@tool
def get_user_info(runtime: ToolRuntime[Context]) -> str:
    """Look up user info."""
    # Access the store - same as that provided to `create_agent`   这里访问到的runtime.store就会是传递给create_agent的store!!!!
    store_1 = runtime.store
    user_id = runtime.context.user_id
    # Retrieve data from store - returns StoreValue object with value and metadata
    user_info = store_1.get(("users",), user_id)
    return str(user_info.value) if user_info else "Unknown user"


# 创建智能体的时候传入store，就像编译一个Graph时传入一个store一样。
agent = create_agent(
    model="claude-sonnet-4-6",
    tools=[get_user_info],
    # Pass store to agent - enables agent to access store when running tools
    store=store,
    context_schema=Context
)

# Run the agent
agent.invoke(
    {"messages": [{"role": "user", "content": "look up user information"}]},
    context=Context(user_id="user_123")
)






# 2、下面介绍如何在添加到智能体的工具中，实现“写入长期记忆”
from dataclasses import dataclass
from typing_extensions import TypedDict
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langgraph.store.memory import InMemoryStore


# InMemoryStore saves data to an in-memory dictionary. Use a DB-backed store in production.
store = InMemoryStore()

@dataclass
class Context:
    user_id: str

# TypedDict defines the structure of user information for the LLM
class UserInfo(TypedDict):
    name: str

# Tool that allows agent to update user information (useful for chat applications)
@tool
def save_user_info(user_info: UserInfo, runtime: ToolRuntime[Context]) -> str:
    """Save user info."""
    # Access the store - same as that provided to `create_agent`
    store_2 = runtime.store
    user_id = runtime.context.user_id
    # Store data in the store (namespace, key, data)
    store_2.put(("users",), user_id, user_info)
    return "Successfully saved user info."

agent = create_agent(
    model="claude-sonnet-4-6",
    tools=[save_user_info],
    store=store,
    context_schema=Context
)

# Run the agent
agent.invoke(
    {"messages": [{"role": "user", "content": "My name is John Smith"}]},
    # user_id passed in context to identify whose information is being updated
    context=Context(user_id="user_123")
)

# You can access the store directly to get the value
store.get(("users",), "user_123").value