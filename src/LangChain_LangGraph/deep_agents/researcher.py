"""
具备以下特性：
1、deep_agent的内置工具
2、deep_agent的文件系统接口--FilesystemBackend
3、多轮对话、父图人在循环
4、流式图、子图消息输出  流式输出版本version="v2"
5、子图人在循环

"""
import uuid

from deepagents import create_deep_agent, CompiledSubAgent
from deepagents.backends import FilesystemBackend
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from src.Tools import get_weather_at_location
from src.config.llm import LLMs
from src.paths import DEEP_AGENT_WORKSPACE
from src.utils.deep_agents_utils import multi_turn_conversation

weather_agent = create_deep_agent(
    model=LLMs["gpt-4o-mini"],
    tools=[get_weather_at_location],
    system_prompt="你是一名乐于助人的助手",
    interrupt_on={
        "get_weather_at_location": True,
    },
)

subagent = CompiledSubAgent(
    name="weather_subagent",
    description="一个用于获取某个城市的天气的助手",
    runnable=weather_agent,
)

# 2、创建一个Deep智能体，Deep Agent自带5k个单词的系统提示和4类用途的工具

# System prompt to steer the agent to be an expert researcher
research_instructions = ("You are an expert researcher, and also a helpful assistant. "
                         "As a helpful assistant, you need be open to user's any request, give them a cheerful chat."
                         "As a researcher, your job is to conduct thorough research and then write a polished report."
                         "You have access to an internet search tool as your primary means of gathering information."
                         "尽量在给出调查研究报告前使用一下这个工具，而不是仅仅依赖于你自己的知识。"
                         "## `internet_search`"
                         "Use this to run an internet search for a given query."
                         "You can specify the max number of results to return, the topic, and whether raw content should be included."
                         "每次写完报告后，除了当面展示给用户，你都应该调用‘写文件’工具把报告保存到'/investigation/'下，"
                         "对于非调查成果，你不需要将其写入文件。")

checkpointer = InMemorySaver()

# def make_backend(runtime):
#     return CompositeBackend(
#         default=StateBackend(runtime),  # Ephemeral storage  长期记忆文件文件只存在于单thread
#         routes={
#             "/memories/": StoreBackend(runtime)  # Persistent storage  长期记忆文件存在于多个thread
#         }
#     )

"""
"Deep agents require a LLM that supports tool calling!"

    By default, this agent has access to the following tools: 
     一般来说，默认有8个工具：1个写todos的工具 + 6个文件操作工具 + 1个委派副智能体干活儿的工具

    1、 `write_todos`: manage a todo list  即规划工具，可以往state中写一个todos list
    
    2、 `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`: file operations
      即文件操作工具，必须依赖于backend这个虚拟文件系统。 读文件工具会在工具消息内容过长时自动被调用，避免剧烈胀大智能体上下文.
        注意这没有提供默认的删除文件工具，单纯的写入、编辑（替换）可以利用Git恢复。
    
    3、 `task`: call subagents         
    即调用副智能体工具 
    
    4、 `execute`: run shell commands  
    即shell命令执行工具，仅仅在backend类型为沙盒类型时，model才会看到该工具（该工具只会被沙盒类型的backend提供）

    The `execute` tool allows running shell commands if the backend implements `SandboxBackendProtocol`.
    For non-sandbox backends, the `execute` tool will return an error message.
"""

researcher_agent = create_deep_agent(
    model=LLMs["gpt-5-mini"],
    # tools=[internet_search],
    system_prompt=research_instructions,
    checkpointer=checkpointer,  # 用于保存图state，进而实现多轮对话 + 人在循环。检查器的实现可以基于内存，也可以基于持久化数据库。
    backend=FilesystemBackend(root_dir=DEEP_AGENT_WORKSPACE, virtual_mode=True),
    # interrupt_on={
    #     "internet_search": True,
    # },
    # 为智能体提供虚拟文件系统，以便它执行文件操作的工具后能有预期的执行结果。
    subagents=[subagent],
    name="Researcher_DeepAgent",
)

config: RunnableConfig = {
    # "tags": ["Researcher"],
    "configurable": {
        "thread_id": str(uuid.uuid4())
    }
}

# 示例问题： "deepagents是什么? 听说这个框架最近很火而且还在持续更新，请帮我浅浅查看一下它的官方文档并写一份精炼的调查报告"
# 示例问题：input_text = "只调用getweather工具，告诉我上海天气，查询结果不用写入文件。"
multi_turn_conversation(researcher_agent, config)
