# 1.1 静态模型选择
from langchain.agents import create_agent
from LangChain_LangGraph.day0_langchain.my_langchain_utils import LLM_1


def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"{city}总是晴天!"

tools = [get_weather]

agent = create_agent("openai:gpt-5", tools=tools)

# 1.2 基于当前state和context，实现动态模型选择
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse


basic_model = ChatOpenAI(model="gpt-4.1-mini")
advanced_model = ChatOpenAI(model="gpt-4.1")

@wrap_model_call
def dynamic_model_selection(request: ModelRequest, handler) -> ModelResponse:
    """基于对话复杂度选择模型"""
    message_count = len(request.state["messages"])

    if message_count > 10:
        # Use an advanced model for longer conversations
        model = advanced_model
    else:
        model = basic_model
    return handler(request.override(model=model))

agent = create_agent(
    model=basic_model,  # Default model
    tools=tools,
    middleware=[dynamic_model_selection]
)

# 2.1 静态工具
from langchain.tools import tool
from langchain.agents import create_agent


@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

@tool
def get_weather(location: str) -> str:
    """Get weather information for a location."""
    return f"Weather in {location}: Sunny, 72°F"

agent = create_agent(LLM_1, tools=[search, get_weather])

# 2.2 动态工具（智能体运行时可访问的工具列表是可变的，可基于认证状态、用户权限、功能标志或对话阶段调整可用工具集）
from langchain.agents import create_agent
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse
from typing import Callable
def public_search(query: str):
    pass
def private_search(query: str):
    pass
def advanced_search(query: str):
    pass

# 比如一开始允许所有已有工具，但是会根据认证状态、对话阶段调整（减少）可使用的工具
@wrap_model_call
def state_based_tools(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    """Filter tools based on conversation State."""
    # Read from State: check if user has authenticated
    state = request.state
    is_authenticated = state.get("authenticated", False)
    message_count = len(state["messages"])

    # Only enable sensitive tools after authentication
    if not is_authenticated:
        tools = [t for t in request.tools if t.name.startswith("public_")]
        request = request.override(tools=tools)
    elif message_count < 5:
        # Limit tools early in conversation
        tools = [t for t in request.tools if t.name != "advanced_search"]
        request = request.override(tools=tools)

    return handler(request)

agent = create_agent(
    model="gpt-4.1",
    tools=[public_search, private_search, advanced_search],
    middleware=[state_based_tools]
)

# 此外，动态工具还可以在运行时被发现并创建（比如来自MCP server的工具），需要额外处理。

# 2.3 通过 @wrap_tool_call 装饰符创建中间件，可自定义工具错误处理方式（自定义工具执行出错时模型会看到什么内容的ToolMessage）
from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage


@wrap_tool_call
def handle_tool_errors(request, handler):
    """Handle tool execution errors with custom messages."""
    try:
        return handler(request)
    except Exception as e:
        # Return a custom error message to the model
        return ToolMessage(
            content=f"Tool error: Please check your input and try again. ({str(e)})",
            tool_call_id=request.tool_call["id"]
        )

agent = create_agent(
    model="gpt-4.1",
    tools=[search, get_weather],
    middleware=[handle_tool_errors]
)

# 3.1 字符串系统提示词
agent = create_agent(
    LLM_1,
    tools,
    system_prompt="You are a helpful assistant. Be concise and accurate."
)

# 3.2 使用SystemMessage作为系统提示词，可以更好的控制提示词的结构, 或者利用提供商的某些特定功能
from langchain.agents import create_agent
from langchain.messages import SystemMessage, HumanMessage

literary_agent = create_agent(
    model="anthropic:claude-sonnet-4-5",
    system_prompt=SystemMessage(
        content=[
            {
                "type": "text",
                "text": "You are an AI assistant tasked with analyzing literary works.",
            },
            {
                "type": "text",
                "text": "<the entire contents of 'Pride and Prejudice'>",
                "cache_control": {"type": "ephemeral"}
            }
        ]
    )
)

"""
cache_control 字段中带有 {“type”： “ephemeral”} 的字段指示 Anthropic 缓存该内容块，从而降低使用同一系统提示符重复请求时的延迟和成本。
"""

result = literary_agent.invoke(
    {"messages": [HumanMessage("Analyze the major themes in 'Pride and Prejudice'.")]}
)

# 3.3 对于需要根据runtime context或agent state修改系统提示符的高级用例，可以使用中间件
# 比如根据用户在对话中的角色（专家or初学者）修改智能体的系统提示词
from typing import TypedDict

from langchain.agents import create_agent
from langchain.agents.middleware import dynamic_prompt, ModelRequest

def web_search(query: str) -> str:
    """Search the web for information."""
    return f"Results for: {query}"

class Context(TypedDict):
    user_role: str

@dynamic_prompt
def user_role_prompt(request: ModelRequest) -> str:
    """Generate system prompt based on user role."""
    user_role = request.runtime.context.get("user_role", "user")
    base_prompt = "You are a helpful assistant."

    if user_role == "expert":
        return f"{base_prompt} Provide detailed technical responses."
    elif user_role == "beginner":
        return f"{base_prompt} Explain concepts simply and avoid jargon."

    return base_prompt

agent = create_agent(
    model="gpt-4.1",
    tools=[web_search],
    middleware=[user_role_prompt],
    context_schema=Context
)

# The system prompt will be set dynamically based on context
result = agent.invoke(
    {"messages": [{"role": "user", "content": "Explain machine learning"}]},
    context={"user_role": "expert"}
)

# 4、为智能体命名，以便在多代理系统中将代理作为子图添加时，该名称可作为节点标识符使用
# 代理名称优先使用 snake_case（例如，用 research_assistant 代替 Research Assistant）
agent = create_agent(
    LLM_1,
    tools,
    name="research_assistant"
)

# 5、可通过传递对代理状态的更新来调用代理。因为所有代理在其状态中包含一系列消息;要调用代理，只需传递一条新消息。
result = agent.invoke(
    {"messages": [{"role": "user", "content": "What's my last question?"}]}
)






