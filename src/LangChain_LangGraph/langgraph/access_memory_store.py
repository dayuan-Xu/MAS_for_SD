# """
# 本文件介绍LangGraph基础设施之一的Store，用于存储跨越单个多轮对话的长期记忆。
#
# Store对象一般在图编译时与检查器对象一起传入给compile方法，比如：
#
# from dataclasses import dataclass
# from langgraph.checkpoint.memory import InMemorySaver
#
# @dataclass
# class Context:
#     user_id: str
#
# # We need this because we want to enable threads (conversations)
# checkpointer = InMemorySaver()
#
# # ... Define the graph ...
#
# # Compile the graph with the checkpointer and store
# builder = StateGraph(MessagesState, context_schema=Context)
# # ... add nodes and edges ...
# graph = builder.compile(checkpointer=checkpointer, store=store) # 编译时传入检查器和仓库
#
#
#
# Each memory is organized under a custom namespace (similar to a folder) and a distinct key (like a file name).
# Namespaces often include user or org IDs or other labels that makes it easier to organize information.
# 每个内存都组织在自定义命名空间 （类似文件夹）和独立键 （类似文件名）下。
# 命名空间通常包含用户或组织 ID 或其他标签，以便于信息组织。
# """



import uuid
from langgraph.store.memory import InMemoryStore
from rich.pretty import pprint

store = InMemoryStore()
user_id = "1"
namespace_for_memory = (user_id, "memories")  # 注意关于该用户的长期记忆的命名空间（相当于文件夹）的命名方式！！！一般包括了user_id

memory_id = str(uuid.uuid4())
memory = {"food_preference" : "I like pizza"}

store.put(namespace_for_memory, memory_id, memory)

memories = store.search(namespace_for_memory)
pprint(memories)
pprint(memories[-1].dict())

# {'value': {'food_preference': 'I like pizza'},
#  'key': '07e0caf4-1631-47b7-b15f-65515d4c1843',
#  'namespace': ['1', 'memories'],
#  'created_at': '2024-10-02T17:22:31.590602+00:00',
#  'updated_at': '2024-10-02T17:22:31.590605+00:00'}


"""
除了简单的检索，商店还支持语义搜索，让你根据意义而非精确匹配来查找记忆。
为实现此功能，请配置存储器材中的嵌入模型
"""
from langchain.embeddings import init_embeddings

searchable_store = InMemoryStore(
    index={
        "embed": init_embeddings("openai:text-embedding-3-small"),  # Embedding provider
        "dims": 1536,                              # Embedding dimensions
        "fields": ["food_preference", "$"]              # Fields to embed
    }
)


# Store with specific fields to embed
searchable_store.put(
    namespace_for_memory,
    str(uuid.uuid4()),
    {
        "food_preference": "I love Italian cuisine",
        "context": "Discussing dinner plans"
    },
    index=["food_preference"]  # Only embed "food_preferences" field
)

# Store without embedding (still retrievable, but not searchable)
searchable_store.put(
    namespace_for_memory,
    str(uuid.uuid4()),
    {"system_info": "Last updated: 2024-01-01"},
    index=False  # index的默认值为None，此处明确指定不进行语义索引化
)

# 如何在LangGraph中使用Store？？？

"""
You can access the store and the user_id in any node by using the Runtime object.
The Runtime is automatically injected by LangGraph when you add it as a parameter to your node function. 
Here’s how you might use it to save memories:
你可以通过运行时对象runtime object在任何节点访问存储Store 和 context中的user_id。

当你把运行时作为参数添加到节点函数时，LangGraph 会自动注入运行时间runtime object。

以下是你可能如何用它来保存记忆的方法：
from langgraph.runtime import Runtime
from dataclasses import dataclass

@dataclass
class Context:
    user_id: str

async def save_memory(state: MessagesState, runtime: Runtime[Context]):

    # Get the user id from the runtime context
    user_id = runtime.context.user_id

    # Namespace the memory
    namespace = (user_id, "memories")

    # ... Analyze conversation and create a new memory

    # Create a new memory ID
    memory_id = str(uuid.uuid4())

    # We create a new memory
    await runtime.store.aput(namespace, memory_id, {"memory": memory})
    
    
    
We can access the memories and use them in our model call.
我们可以访问这些记忆，并在模型调用中使用它们。
from dataclasses import dataclass
from langgraph.runtime import Runtime

@dataclass
class Context:
    user_id: str

# 比如在每轮对话开始的一次model_call时（可以通过state中的model_call_count字段是否为0判断），
# 默认读取当前用户的长期记忆命名空间中的所有长期记忆，
# 从而避免智能体每开新的一轮对话时就失忆了一样
async def call_model(state: MessagesState, runtime: Runtime[Context]):
    # Get the user id from the runtime context
    user_id = runtime.context.user_id

    # Namespace the memory
    namespace = (user_id, "memories")

    # Search based on the most recent message
    memories = await runtime.store.asearch(
        namespace,
        query=state["messages"][-1].content,
        limit=3
    )
    info = "\n".join([d.value["memory"] for d in memories])

    # ... Use memories in the model call
    
    
If we create a new thread, we can still access the same memories so long as the user_id is the same.
如果我们新建一个线程，只要 user_id 相同，我们仍然可以访问相同的记忆。

# Invoke the graph on a new thread
config = {"configurable": {"thread_id": "2"}}

# Let's say hi again
for update in graph.stream(
    {"messages": [{"role": "user", "content": "hi, tell me about my memories"}]},  # 你好，请告诉我你关于我的（长期）记忆有哪些？
    config,
    stream_mode="updates",
    context=Context(user_id="1"),  # 不同thread_id，同一user_id
):
    print(update)
"""