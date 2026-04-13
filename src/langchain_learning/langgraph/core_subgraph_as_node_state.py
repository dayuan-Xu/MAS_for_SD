from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from rich.pretty import pprint
from typing_extensions import TypedDict
from src.config.llm import LLM_1

class State(TypedDict):
    foo: str

# Subgraph
def subgraph_node_1(state: State, config: RunnableConfig):
    checkpoint_ns = config["configurable"]["checkpoint_ns"]
    # "" for the parent graph, "node_name:uuid" for a subgraph
    print("现在在子图的节点内部访问当前检查点命名空间，即当前检查点所属的图是哪个，checkpoint_ns:", checkpoint_ns)
    value = interrupt("请为foo列表再提供一个值:")
    return {"foo": state["foo"] + value}

subgraph_builder = StateGraph(State)

subgraph_builder.add_node(subgraph_node_1)

subgraph_builder.add_edge(START, "subgraph_node_1")

"""
① 默认模式：每次都失忆（最常用）
checkpointer=None
每次调用子图，都重新开始
不记得上一次问过啥
适合：一次性任务（查个价格、算个数）
"""
subgraph = subgraph_builder.compile()  # inherits parent checkpointer 该子图编译时默认checkpointer=None，子图状态也就存在于每次调用

def node_2(state: State, config: RunnableConfig):
    checkpoint_ns = config["configurable"]["checkpoint_ns"]
    # "" for the parent graph, "node_name:uuid" for a subgraph
    print("现在在父图的节点内部访问当前检查点命名空间，即当前检查点所属的图是哪个，checkpoint_ns:", checkpoint_ns)
    return {}


# Parent graph 注意父图和子图共享同一Graph State
builder = StateGraph(State)
builder.add_node("node_1", subgraph)
builder.add_node("node_2", node_2)

builder.add_edge(START, "node_1")
builder.add_edge("node_1", "node_2")

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)  # 仅在父图编译时指定checkpointer

config = {"configurable": {"thread_id": "1"}}

graph.invoke({"foo": ""}, config)

# 可以通过设置subgraphs=True查看”本次调用“中断发生后的子图状态，
# 其实可以查看所有子图的本次调用时的状态，但是这里只有一个子图
# subgraph_state = graph.get_state(config, subgraphs=True).tasks[0].state
subgraph_state = graph.get_state(config, subgraphs=True)

pprint(subgraph_state)

# Resume the subgraph
graph.invoke(Command(resume="bar"), config)

subgraph_state = graph.get_state(config, subgraphs=True)
pprint(subgraph_state)