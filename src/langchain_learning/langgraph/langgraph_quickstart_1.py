# Step 1: Define tools and model

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

from src.config.llm import LLMs

# from langchain.chat_models import init_chat_model
#
#
# model = init_chat_model(
#     "claude-sonnet-4-6",
#     temperature=0
# )

model = LLMs["gpt-5-mini"]


# Define tools
@tool
def multiply(a: int, b: int) -> int:
    """Multiply `a` and `b`.

    Args:
        a: First int
        b: Second int
    """
    return a * b


@tool
def add(a: int, b: int) -> int:
    """Adds `a` and `b`.

    Args:
        a: First int
        b: Second int
    """
    return a + b


@tool
def divide(a: int, b: int) -> float:
    """Divide `a` and `b`.

    Args:
        a: First int
        b: Second int
    """
    return a / b


# Augment the LLM with tools
tools = [add, multiply, divide]
tools_name_to_tool = {tool.name: tool for tool in tools}
model_with_tools = model.bind_tools(tools)

# Step 2: Define state

from langchain.messages import AnyMessage
from typing_extensions import TypedDict, Annotated
import operator


class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]  # 追加式更新
    llm_calls_count: int  # 覆盖式更新


# Step 3: Define model node
from langchain.messages import SystemMessage
from langgraph.types import Command


def llm_call(state: dict, config: RunnableConfig) -> Command:
    """LLM decides whether to call a tool or not"""
    response = model_with_tools.invoke(
        [
            SystemMessage(
                content="You are a helpful assistant tasked with performing arithmetic on a set of inputs."
            )
        ]
        + state["messages"]
    )

    # 根据响应决定路由
    # 其实如果在节点内使用Command对Graph State的更新相同，仅是路由不同
    # 那么完全不必使用Command，如同v2那样使用add_conditional_edge即可
    if response.tool_calls:
        return Command(
            update={"messages": [response], "llm_calls_count": state.get('llm_calls_count', 0) + 1},
            goto="tool_node"
        )
    else:
        return Command(
            update={"messages": [response], "llm_calls_count": state.get('llm_calls_count', 0) + 1},
            goto=END
        )


# Step 4: Define tool node

from langchain.messages import ToolMessage


def tool_node(state: dict):
    """Performs the tool call"""

    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_name_to_tool[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}


# Step 5: Define logic to determine whether to end

from langgraph.graph import StateGraph, START, END

# Step 6: Build agent

# Build workflow
agent_builder = StateGraph(MessagesState)

# Add nodes
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)

# Add edges to connect nodes
agent_builder.add_edge(START, "llm_call")
agent_builder.add_edge("tool_node", "llm_call")

# Compile the agent
agent = agent_builder.compile(name="Arithmetic ReAct Agent v1")

# Show the agent
graph_png = agent.get_graph(xray=True).draw_mermaid_png()
with open(f"{agent.name}.png", "wb") as f:
    f.write(graph_png)
print(f"{agent.name} 架构图已保存为 {agent.name}.png")

# Invoke
from langchain.messages import HumanMessage

messages = [HumanMessage(content="Add 3 and 4.")]

messages = agent.invoke({"messages": messages})
# messages = agent.invoke({"messages": None})  # 传入None值可不行，会在llm_call函数内连接SystemMessage与state["messages"]时报错
# messages = agent.invoke({"messages": []})  # 为messages这个key传入[]可以，不会报错

for m in messages["messages"]:
    m.pretty_print()
