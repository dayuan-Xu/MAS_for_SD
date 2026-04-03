"""
具备以下特性：
1、一个通用目的的deep_agent主智能体 + 多个专用的CompiledSubAgent副智能体(LangGraph的包装)
2、流式图、子图消息输出
3、多轮对话、子图在被父图调用间保持短期记忆

"""
from typing import cast
from langchain.agents import create_agent
from deepagents import create_deep_agent, CompiledSubAgent
from langgraph.types import StreamPart, Command
from src.config.llm import LLMs
from src.Tools import internet_search, get_weather_at_location
import uuid
from langgraph.checkpoint.memory import InMemorySaver
from rich.pretty import pprint

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
    name="weather-agent",           # 在version=v2时，貌似没在输出子图的AI消息时被用到啊，而是只有在creat_agent传入的name才会生效。
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

config = {"configurable": {
    "thread_id": str(uuid.uuid4())
}}

last_output_msg = None
while True:
    # 第一次用户输入；或者上个ReAct循环完整结束后，等待用户新输入令。
    input_text = input("\n=========================================\n请用户输入：")
    if input_text == "exit":
        print("\n用户输入了exit，结束多轮对话。")
        break
    agent_input = {"messages": [{"role": "user", "content": input_text}]}

    print("\n=========================================\n下面开启全新的一轮ReAct循环\n")
    human_in_the_loop = False  # 每次开始前默认没发生人在循环
    current_loop_ends_totally = False  # 每次开始前默认本次ReAct没有完整结束

    while not current_loop_ends_totally:
        # 开启新一轮的 或 继续未完整结束的 ReAct循环
        for stream_part in main_agent.stream(input=agent_input, config=config, stream_mode="values",
                subgraphs=True,
                version="v2"):  # 这里用的是version=v2，所以stream_part是一个字典，包含"type" "ns" "data" "interrupts"四个键

            # 先判断本次ReAct循环是否需要人类参与
            if stream_part['interrupts']:
                # 如果真需要人类参与
                print("\n=========================================\n工具中断触发，需要人类干预，之后才能继续进行本轮ReAct循环\n")
                interrupt_value = stream_part['interrupts'][0].value
                action_requests = interrupt_value["action_requests"]
                review_configs = interrupt_value["review_configs"]

                # Create a lookup map from tool name to review config
                config_map = {cfg["action_name"]: cfg for cfg in review_configs}

                # Display the pending actions to the user
                # 并发工具调用下，可能会有多个工具调用被中断，这些中断需要人类顺序逐个处理
                decisions = []
                for action in action_requests:
                    review_config = config_map[action["name"]]
                    print(f"Tool: {action['name']}")
                    print(f"Arguments: {action['args']}")
                    print(f"Allowed decisions: {review_config['allowed_decisions']}")
                    decision_type = input("\nEnter your decision(approve/reject/edit) for this tool_call: ")

                    if decision_type == "approve":
                        decisions.append({"type": "approve"})
                    elif decision_type == "reject":
                        decisions.append({"type": "reject"})
                    elif decision_type == "edit":
                        new_args = {}
                        for k in action["args"]:
                            new_arg_value = input(f"请为{k} = {action['args'][k]}提供一个新值:")
                            new_args[k] = new_arg_value
                        decisions.append({"type": "edit", "edited_action": {"name": action["name"], "args": new_args}})

                # Resume execution with decisions
                agent_input = Command(resume={"decisions": decisions})
                human_in_the_loop = True
                # 暂停当前ReAct执行，直接继续下一次ReAct
                break

            namespace = stream_part["ns"]
            data = stream_part["data"]

            latest_message = data["messages"][-1]
            if last_output_msg is None:
                latest_message.pretty_print()
                last_output_msg = latest_message
            elif latest_message.id != last_output_msg.id:
                # 只用于打印图的或子图的新产出消息
                if namespace:
                    # 如果namespace不是空元组，而是那个调用子图的节点名，则说明是data是子图发射的事件（新消息），
                    # 比如是 'tools'
                    print("\n================================== 下面这条消息是子图的新消息\n")
                latest_message.pretty_print()
                last_output_msg = latest_message

        # 判断本次ReAct循环是否完整地结束了
        if human_in_the_loop:
            # 不是完整地结束
            print("\n=========================================\n发生了人在循环，已经收集到人类干预，继续进行本轮ReAct循环\n")
            human_in_the_loop = False  # 继续进行本轮ReAct循环前，恢复默认值
            continue
        else:
            # 说明是完整地结束
            print("\n=========================================\n本轮ReAct循环圆满结束\n")
            current_loop_ends_totally = True

print("多轮对话成功结束。")

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