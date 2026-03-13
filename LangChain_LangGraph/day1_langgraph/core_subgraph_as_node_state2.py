from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, StateGraph, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from LangChain_LangGraph.day0_langchain.my_langchain_utils import LLM_1

# 子图节点
def subgraph_node_1(state: MessagesState, config: RunnableConfig):
    response = LLM_1.invoke(state["messages"])
    return {"messages":[response]}

# 具备自己持久化状态的子图
subgraph_builder = StateGraph(MessagesState)

subgraph_builder.add_node(subgraph_node_1)

subgraph_builder.add_edge(START, "subgraph_node_1")

subgraph = subgraph_builder.compile(checkpointer=True)  # 此时子图在父图的多次执行invoke间具备状态

#  注意：父图和子图共享状态
builder = StateGraph(MessagesState)
builder.add_node("agent", subgraph)
builder.add_edge(START, "agent")

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "1"}}

graph.invoke({"messages": [{"role": "user", "content": "hi"}]}, config)
graph.invoke({"messages": [{"role": "user", "content": "what did I say?"}]}, config)

# 子图状态中包含两次父图调用积累的消息，因为子图也有状态
subgraph_state = graph.get_state(config, subgraphs=True)

from rich import print as rprint
rprint(subgraph_state)