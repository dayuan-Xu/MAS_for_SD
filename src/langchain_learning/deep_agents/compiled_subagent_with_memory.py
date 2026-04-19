"""
具备以下特性：
1、一个通用目的的deep_agent主智能体 + 多个专用的CompiledSubAgent副智能体(LangGraph的包装)
2、流式图、子图消息输出
3、多轮对话、子图在被父图调用间保持短期记忆

"""
import uuid

from deepagents import create_deep_agent, CompiledSubAgent
from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from src.Tools import internet_search, get_weather_at_location
from src.config.llm import LLMs

# 为了隔离详细工作并避免主智能体的上下文膨胀，可以使用子代理，
# 对于更加复杂的工作流，使用预构建的LangGraph作为子代理，
# 这也是使用副代理的第2种方式：CompiledSubAgent，（充分）自定义的副智能体
# 使用时要为主智能体传入CompiledSubAgent对象

"""
For more complex use cases, you can provide your custom subagents. 
You can create a custom subagent using LangChain’s create_agent or
by making a custom LangGraph graph using the graph API.
对于更复杂的使用场景，你可以提供自定义子代理。
你可以用 LangChain 的 create_agent 创建自定义子代理，
或者用图 API 创建自定义 LangGraph 图。

If you’re creating a custom LangGraph graph, 
make sure that the graph has a state key called "messages":
如果你要创建自定义的 LangGraph 图，确保图中有一个称为 “消息” 的状态键 ：
"""

# 创建研究员副智能体（对应 dict_based_subagent_wo_memory.py 中的 research_subagent）
research_graph = create_agent(
    model=LLMs["gpt-5-mini"],
    tools=[internet_search],
    system_prompt="You are a great researcher.",
    checkpointer=True,
    name="researchGraph"
)

research_subagent = CompiledSubAgent(
    name="research-agent",
    description="Used to research more in depth questions",
    runnable=research_graph,
)

# 创建天气副智能体（对应 dict_based_subagent_wo_memory.py 中的 weather_subagent）
weather_graph = create_agent(
    model=LLMs["gpt-5-mini"],
    tools=[get_weather_at_location],
    system_prompt="You are a great weather agent.",
    checkpointer=True,
    name="weatherGraph"
)

weather_subagent = CompiledSubAgent(
    name="weather-agent",  # 在version=v2时，貌似没在输出子图的AI消息时被用到啊，而是只有在creat_agent传入的name才会生效。
    description="Used to get weather information at some city",
    runnable=weather_graph
)

subagents = [research_subagent, weather_subagent]

checkpointer = InMemorySaver()

# 创建主智能体
main_agent = create_deep_agent(
    model=LLMs["gpt-5-mini"],
    system_prompt="你是一个团队领导，你直面用户的复杂需求。你知人善任，擅长复杂任务的高层规划调度，你并不会事事亲历亲为，而是委派团队成员完成任务。",
    subagents=subagents,
    checkpointer=checkpointer,
    name="Team-Leader",
)

config: RunnableConfig = {"configurable": {
    "thread_id": str(uuid.uuid4())
}}
if __name__ == "__main__":
    from src.utils.graph_running_utils import multi_turn_conversation

    multi_turn_conversation(main_agent, config)

"""
=========================================
请用户输入：我想知道天津天气是阴还是晴。

=========================================
下面开启全新的一轮ReAct循环

================================ Human Message =================================

我想知道天津天气是阴还是晴。
================================== Ai Message ==================================
Name: Team-Leader
Tool Calls:
  task (call_nVrngJtimK2j4vZFHc2HWIOS)
 Call ID: call_nVrngJtimK2j4vZFHc2HWIOS
  Args:
    description: Provide current weather for Tianjin, China. Return a short answer in Chinese specifying current condition (e.g., 晴, 多云, 阴, 小雨, etc.), temperature, and confidence/time of observation. Keep it concise (one sentence).
    subagent_type: weather-agent

================================== 下面这条消息是子图的新消息

================================ Human Message =================================

Provide current weather for Tianjin, China. Return a short answer in Chinese specifying current condition (e.g., 晴, 多云, 阴, 小雨, etc.), temperature, and confidence/time of observation. Keep it concise (one sentence).

================================== 下面这条消息是子图的新消息

================================== Ai Message ==================================
Name: weatherGraph
Tool Calls:
  get_weather_at_location (call_jbGIQfmGcC7GYWo83LEZZ4Un)
 Call ID: call_jbGIQfmGcC7GYWo83LEZZ4Un
  Args:
    city: Tianjin, China

================================== 下面这条消息是子图的新消息

================================= Tool Message =================================
Name: get_weather_at_location

Tianjin, China总是晴天!

================================== 下面这条消息是子图的新消息

================================== Ai Message ==================================
Name: weatherGraph

天津：晴，温度未知；仅有“总是晴天”的描述，未提供观测时间，置信度有限。

"""

#
# def specialized_tools(query):
#     """
#     Use specialized tools for data analysis
#     """
#     return "Specialized tools output"
#
# # Create a custom agent graph
# custom_graph = create_agent(
#     model=LLMs["gpt-5-mini"],
#     tools=[specialized_tools],
#     system_prompt="You are a specialized agent for data analysis..."
# )
#
# # Use it as a custom subagent
# custom_subagent = CompiledSubAgent(
#     name="data-analyzer", # 子代理的唯一标识符。子代理名称成为 AIMessage 和流媒体的元数据，有助于区分代理。
#     description="Specialized agent for complex data analysis tasks",
#     runnable=custom_graph  # 必须传入编译后的LangGraph
# )
#
# subagents = [custom_subagent]
#
# agent = create_deep_agent(
#     model=LLMs["gpt-5-mini"],
#     tools=[internet_search],
#     system_prompt="你可以收集数据，并把数据分析任务交给专业的智能体来做，你在得到数据分析结果后要给用户写出报告",
#     subagents=subagents
# )
