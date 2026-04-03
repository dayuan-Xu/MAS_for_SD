from langgraph.store.memory import InMemoryStore

from src.config.llm import LLMs

store = InMemoryStore()

from dataclasses import dataclass
from langgraph.runtime import Runtime
from langgraph.graph import StateGraph, MessagesState, START
import uuid



@dataclass
class Context:
    user_id: str

async def call_model(state: MessagesState, runtime: Runtime[Context]):
    user_id = runtime.context.user_id  
    namespace = (user_id, "memories")

    # # Search for relevant memories
    # memories = await runtime.store.asearch(
    #     namespace, query=state["messages"][-1].content, limit=3
    # )
    # info = "\n".join([d.value["data"] for d in memories])
    #
    # # ... Use memories in model call
    ai_msp = await LLMs["gpt-3.5-turbo"].ainvoke("Hello，你好啊！假如咱俩是经年好友，你是陆小凤我是花满楼，告诉我一件你对于我的长期记忆")

    long_memory = ai_msp.content

    # Store a new memory
    await runtime.store.aput(
        namespace, str(uuid.uuid4()), {"data": f"{long_memory}"}
    )

builder = StateGraph(MessagesState, context_schema=Context)
builder.add_node(call_model)
builder.add_edge(START, "call_model")
graph = builder.compile(store=store)

import asyncio

async def main():
    # Pass context at invocation time
    await graph.ainvoke(
        {"messages": [{"role": "user", "content": "hi"}]},
        {
            "configurable": {"thread_id": "1"},
            "tags":["Memory Store"],
            "run_name":"Access Memory Store"
        },
        context=Context(user_id="1"),
    )

if __name__ == "__main__":
    asyncio.run(main())
