"""
具备以下特性：
1、一个通用目的的deep_agent主智能体 + 多个专用的deep_agent副智能体
2、deep_agent的文件系统接口--FilesystemBackend
3、流式图、子图消息输出

"""

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from rich.pretty import pprint

from src.Tools import internet_search, get_weather_at_location
from src.config.llm import LLMs
from src.paths import DEEP_AGENT_WORKSPACE

# 为了隔离详细工作并避免主智能体的上下文膨胀，可以使用子代理
# 第一种方式是 基于字典的自定义副智能体dict-based SubAgent，类型是DeepAgent
# 为每个副智能体创建一个副智能体的字典， 该字典定义了主DeepAgent可以使用的副智能体
research_subagent = {
    "name": "research-agent",                                    # 子代理的唯一标识符。子代理名称会成为 AIMessage 和流媒体的元数据，有助于区分代理。
    "description": "Used to research more in depth questions",   # 用于让主智能体了解副智能体并判断要不要委托它
    "system_prompt": "You are a great researcher",
    "tools": [internet_search],
    # "model": LLMs["gpt-4o-mini"],  # Optional override, defaults to main agent model
}

weather_subagent = {
    "name": "weather-agent",
    "description": "Used to get weather information at some city",
    "system_prompt": "You are a great weather agent",
    "tools": [get_weather_at_location],
    # "model": LLMs["gpt-4o-mini"],  # Optional override, defaults to main agent model
}

# 注意，这里添加的每个副智能体，在主智能体的多次调用间不会保持记忆，因为无法为其注入checkpointer
subagents = [research_subagent, weather_subagent]

# 创建主Deep智能体的时候，告诉它可以委派的副智能体有谁
main_agent = create_deep_agent(
    model=LLMs["gpt-5-mini"],
    system_prompt="你是一个团队领导，你直面用户的复杂需求。你知人善任，擅长复杂任务的高层规划调度，你并不会事事亲历亲为，而是委派团队成员完成任务。",
    backend=FilesystemBackend(root_dir=DEEP_AGENT_WORKSPACE, virtual_mode=True),
    subagents=subagents,
    name="团队领导",
)

# input_state = {
#         "messages": [
#             {
#                 "role": "user",
#                 "content": "现在AI智能体对于软件公司程序员的真实影响到底是什么样的？真的杀死了前端程序员的价值了吗？它的深度广度烈度如何？调查写一份精炼的调查报告并保存到文件"
#             }
#         ]
# }

input_state = {
        "messages": [
            {
                "role": "user",
                "content": "大连天气如何，只用回答我阴天或者晴天。"
            }
        ]
}

last_output_msg = None
for step_state in main_agent.stream(
    input_state,
    stream_mode="values",
    subgraphs=True,       # 因为我们希望看到副智能体的执行过程
    # version="v1",       #  这里没有显式指定，所以默认用的是version="v1"，subgraphs=True的情况下，step_state是一个元组，包含namespace和data两部分
):
    namespace, data = step_state
    latest_message = data["messages"][-1]   # 这里的data可能是父图的values（state-snapshot），也可能是子图的values

    if last_output_msg is None:
        # 只会执行一次，用于打印第一个消息
        latest_message.pretty_print()
        last_output_msg = latest_message
    elif latest_message.id != last_output_msg.id:
        # 只用于打印图的或子图的新产出消息
        if namespace:
            # 如果namespace不是空元组，而是通往哪个调用子图的节点的路径，则说明是data是子图发射的事件（新消息），
            # 比如是 'tools:5927c259-58a6-e7bb-c9fe-0c051e90c825'
            print("\n================================== 下面这条消息是子图的新消息\n")
        latest_message.pretty_print()
        last_output_msg = latest_message


"""
"D:\Python\VS Code WorkSpace\MAS_for_SD\.venv\Scripts\python.exe" "D:\Python\VS Code WorkSpace\MAS_for_SD\src\LangChain_LangGraph\deep_agents\deep_subagent_wo_memory.py" 
================================ Human Message =================================

大连天气如何，只用回答我阴天或者晴天。
================================== Ai Message ==================================
Name: 团队领导
Tool Calls:
  task (call_pBle7cqnVjwh0wZpkezuV0bI)
 Call ID: call_pBle7cqnVjwh0wZpkezuV0bI
  Args:
    description: 你是一个weather-agent。请查询当前（实时）中国辽宁省大连市的天气状况（不要使用模拟或假设数据，尽可能取真实气象数据源）。根据当前天气状况，判断并在输出中只返回以下两个词中的一个："阴天" 或 "晴天"。判断规则：如果天空主要被云覆盖、阴沉、多云或有降水迹象，应返回"阴天"；如果天空主要为晴朗、少云，应返回"晴天"。输出必须严格只有一个词，不能有其他说明、标点或注释。
    subagent_type: weather-agent

================================== 下面这条消息是子图的新消息

================================ Human Message =================================

你是一个weather-agent。请查询当前（实时）中国辽宁省大连市的天气状况（不要使用模拟或假设数据，尽可能取真实气象数据源）。根据当前天气状况，判断并在输出中只返回以下两个词中的一个："阴天" 或 "晴天"。判断规则：如果天空主要被云覆盖、阴沉、多云或有降水迹象，应返回"阴天"；如果天空主要为晴朗、少云，应返回"晴天"。输出必须严格只有一个词，不能有其他说明、标点或注释。

================================== 下面这条消息是子图的新消息

================================== Ai Message ==================================
Name: weather-agent
Tool Calls:
  get_weather_at_location (call_FTfIogHjshETBcPZZCQZ4i3p)
 Call ID: call_FTfIogHjshETBcPZZCQZ4i3p
  Args:
    city: 大连

================================== 下面这条消息是子图的新消息

================================= Tool Message =================================
Name: get_weather_at_location

大连总是晴天!

================================== 下面这条消息是子图的新消息

================================== Ai Message ==================================
Name: weather-agent

晴天
================================= Tool Message =================================
Name: task

晴天
================================== Ai Message ==================================
Name: 团队领导

晴天

进程已结束，退出代码为 0

"""