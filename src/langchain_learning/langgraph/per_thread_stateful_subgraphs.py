# 必须实现per-thread subgraphs in tool以实现查看子图的状态！
import uuid

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from rich.pretty import pprint

from src.config.llm import LLMs
from src.utils.graph_running import multi_turn_conversation


@tool
def fruit_info(fruit_name: str) -> str:
    """Look up fruit info."""
    return f"Info about {fruit_name}"


@tool
def veggie_info(veggie_name: str) -> str:
    """Look up veggie info."""
    return f"Info about {veggie_name}"


from langgraph.graph import MessagesState, StateGraph


def create_sub_agent(model, *, name, **kwargs):
    """Wrap an agent with a unique node name for namespace isolation."""
    agent = create_agent(model=model, name=name, **kwargs)
    #  when parent graph and subgraph share state keys, you can pass a compiled subgraph directly to add_node.
    #  the subgraph reads from and writes to the parent’s state channels automatically
    return (
        StateGraph(MessagesState)
        .add_node(f"ns_for_{name}", agent)  # unique name → stable namespace  #
        .add_edge("__start__", f"ns_for_{name}")
        .compile()  # 若传入的kwargs中已经有checkpointer=True，则此处不必checkpointer=True
    )


fruit_agent = create_sub_agent(
    LLMs["minimax-m2.7"],
    name="fruit_agent",
    tools=[fruit_info],
    system_prompt="You are a fruit expert. Use the fruit_info tool. Respond in one short sentence every time.",
    checkpointer=True,  # 开启per-thread的子图状态，确保副智能体支持多轮对话的记忆
)
veggie_agent = create_sub_agent(
    LLMs["minimax-m2.7"],
    name="veggie_agent",
    tools=[veggie_info],
    system_prompt="You are a veggie expert. Use the veggie_info tool. Respond in one short sentence every time.",
    checkpointer=True,  # 开启per-thread的子图状态，确保副智能体支持多轮对话的记忆
)


# Wrap subagents as tools for the outer agent
@tool
def ask_fruit_expert(question: str) -> str:
    """Ask the fruit expert. Use for ALL fruit questions."""
    response = fruit_agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
    )
    return response["messages"][-1].content


@tool
def ask_veggie_expert(question: str) -> str:
    """Ask the veggie expert. Use for ALL veggie questions."""
    response = veggie_agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
    )
    return response["messages"][-1].content


# Outer agent with checkpointer
agent = create_agent(
    model=LLMs["minimax-m2.7"],
    tools=[ask_fruit_expert, ask_veggie_expert],
    system_prompt=(
        "You have two experts: ask_fruit_expert and ask_veggie_expert. "
        "ALWAYS delegate questions to the appropriate expert."
    ),
    middleware=[
        ToolCallLimitMiddleware(tool_name="ask_fruit_expert", run_limit=1),  # 不允许同时多次调用同一个per-thread类型的子图
        ToolCallLimitMiddleware(tool_name="ask_veggie_expert", run_limit=1),  # 不允许同时多次调用同一个per-thread类型的子图
    ],
    checkpointer=MemorySaver(),
)

config: RunnableConfig = {
    "configurable":
        {"thread_id": str(uuid.uuid4())}
}

# # First call - LLM calls both fruit and veggie experts
# response_1 = agent.invoke(
#     {"messages": [{"role": "user", "content": "跟我简单讲一讲樱桃和西兰花"}]},
#     config=config,
# )
# # Fruit subagent message count: 4
# # Veggie subagent message count: 4
#
# # Second call - both agents accumulate independently
# response_2 = agent.invoke(
#     {"messages": [{"role": "user", "content": "现在跟我简单讲一讲橙子和胡萝卜"}]},
#     config=config,
# )
# # Fruit subagent message count: 8 (remembers cherries!)
# # Veggie subagent message count: 8 (remembers broccoli!)

multi_turn_conversation(agent, config)

agent_state = agent.get_state(config, subgraphs=True)
pprint(agent_state)

##### 无法获取per-thread stateful子图的状态
# subagent_state = fruit_agent.get_state(config, subgraphs=True)
# pprint(subagent_state)
#
# Traceback (most recent call last):
#   File "D:\Python\VS Code WorkSpace\MAS_for_SD\src\dev_team\per_thread_stateful_subgraphs.py", line 119, in <module>
#     subagent_state = fruit_agent.get_state(config, subgraphs=True)
#                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "D:\Python\VS Code WorkSpace\MAS_for_SD\.venv\Lib\site-packages\langgraph\pregel\main.py", line 1271, in get_state
#     raise ValueError("No checkpointer set")
# ValueError: No checkpointer set
