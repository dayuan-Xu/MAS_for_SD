from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)
# 先安装：pip install rich
from rich import print as rprint
from rich.pretty import pprint

from langgraph.types import interrupt, Command
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.runnables import RunnableConfig
from typing import Annotated
from typing_extensions import TypedDict
from operator import add

class State(TypedDict):
    foo: str
    bar: Annotated[list[str], add]

def node_a(state: State, config: RunnableConfig):
    checkpoint_ns = config["configurable"]["checkpoint_ns"]
    print("checkpoint_ns:", checkpoint_ns)
    response = interrupt("需要继续往node_b接着走吗？")
    if response:
        return {"foo": "a", "bar": ["a"]}

    return Command(update={}, goto=END)

def node_b(state: State, config: RunnableConfig):
    checkpoint_ns = config["configurable"]["checkpoint_ns"]
    print("checkpoint_ns:", checkpoint_ns)

    return {"foo": "b", "bar": ["b"]}


workflow = StateGraph(State)
workflow.add_node(node_a)
workflow.add_node(node_b)
workflow.add_edge(START, "node_a")
workflow.add_edge("node_a", "node_b")
workflow.add_edge("node_b", END)

# 只在本地运行时添加 checkpointer
# LangGraph API 会自动处理持久化，不需要显式设置
checkpointer = InMemorySaver()
graph = workflow.compile(name="delve_into_checkpoint")


# 仅在直接运行此文件时执行测试代码
if __name__ == "__main__":
    graph = workflow.compile(checkpointer=checkpointer, name="delve_into_checkpoint")

    config: RunnableConfig = {"configurable": {"thread_id": "1"}}
    result = graph.invoke({"foo": "", "bar":[]}, config)

    if result["__interrupt__"]:
        print("graph 执行过程中遇到中断")
        rprint(result["__interrupt__"])
        graph.invoke(Command(resume=True), config = config)


    # get the latest state snapshot
    config = {"configurable": {"thread_id": "1"}}
    state_snapshot = graph.get_state(config)

    # 方法 A: 直接打印
    rprint(state_snapshot)

    # # 方法 B: 使用 pprint
    # pprint(state_snapshot, expand_all=True)

    # get a state snapshot list
    sate_snapshot_his_gener = graph.get_state_history(config)
    rprint(list(sate_snapshot_his_gener))
