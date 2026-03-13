from typing_extensions import TypedDict
from langgraph.graph.state import StateGraph, START

# Define subgraph
class SubgraphState(TypedDict):
    # note that none of these keys are shared with the parent graph state
    bar: str
    baz: str

def subgraph_node_1(state: SubgraphState):
    return {"baz": "baz"}

def subgraph_node_2(state: SubgraphState):
    return {"bar": state["bar"] + state["baz"]}

subgraph_builder = StateGraph(SubgraphState)
subgraph_builder.add_node(subgraph_node_1)
subgraph_builder.add_node(subgraph_node_2)

subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph_builder.add_edge("subgraph_node_1", "subgraph_node_2")
subgraph = subgraph_builder.compile()

# Define parent graph
class ParentState(TypedDict):
    foo: str

def node_1(state: ParentState):
    return {"foo": "hi! " + state["foo"]}

def node_2(state: ParentState):
    # 需要转换为子图可接受的状态
    response = subgraph.invoke({"bar": state["foo"]})
    # Transform response back to the parent state
    return {"foo": response["bar"]}


builder = StateGraph(ParentState)
builder.add_node("node_1", node_1)
builder.add_node("node_2", node_2)
builder.add_edge(START, "node_1")
builder.add_edge("node_1", "node_2")
graph = builder.compile()

# 在节点函数内调用子图，此时流式输出中想要看见子图内的每步事件，
# 必须设置subgraphs=True，此时返回值会作为元组发射：（namespace，data）
# 命名空间就是从父图到(子图被调用的)节点的路径
# subgraphs – Whether to stream events from inside subgraphs, defaults to False.
# If True, the events will be emitted as tuples (namespace, data), or (namespace, mode, data) if stream_mode is a list,
# where namespace is a tuple with the path to the node where a subgraph is invoked,
# e.g. ("parent_node:<task_id>", "child_node:<task_id>").
for namespace, data in graph.stream({"foo": "foo"}, subgraphs=True):
    print("=======================================================")
    print("namespace==", namespace, sep=" ")
    print("data==", data, sep=" ")


"""
总结：
当父图和子图的状态模式State Schema不同 （没有任何共享键）时，就需要在函数中调用子图，然后再把该函数作为父图的一个节点。

节点函数在调用子图前需要从父状态中转换出子图可接受的状态，然后返回前将子图调用结果转换回父图可接受的状态。

这种情况就像是一个智能体在它的选择调用另外一个智能体（这个调用可视作一个工具ask_another_do_sth_for_me），
至于工具内被调用的智能体是否应该记住主调智能体过往对它的（多次）调用，参考LangChain Agents可知：
节点函数内被调用的智能体
case1：只执行一次性任务而无需记住过去主调智能体对它的调用，该被调智能体在compile时不需要指定checkpointer的值，默认为None
case2：也可以记住主调智能体对它的多次调用，那么该被调用智能体需要在compile时指定checkpointer=True
"""