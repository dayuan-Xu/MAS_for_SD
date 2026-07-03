from langchain.agents import create_agent

from src.config.llm import LLMs


def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"It's always sunny in {city}!"


agent = create_agent(
    model=LLMs["gpt-5-nano"],
    tools=[get_weather],
)

# stream = agent.stream_events(
#     {
#         "messages": [
#             {
#                 "role": "user",
#                 "content": "立即仅仅调用一次工具查询乌鲁木齐天气，并告诉我工具返回结果。",
#             }
#         ],
#     },
#     version="v3",
# )


# for i, message in enumerate(stream.messages):
#     print("\n" + "=" * 30 + f" AIMessage{i+1} 推理块 " + "=" * 30)
#     for delta in message.reasoning:
#         print(delta, end="#", flush=True)

#     print("\n" + "=" * 30 + f" AIMessage{i+1} 文本块 " + "=" * 30)
#     for delta in message.text:
#         print(delta, end="|", flush=True)

#     print("\n" + "=" * 30 + f" AIMessage{i+1} 工具调用块 " + "=" * 30)
#     for delta in message.tool_calls:
#         print(delta, end="\n", flush=True)

input = {
    "messages": [
        {
            "role": "user",
            "content": "立即仅仅调用一次工具查询合肥天气，并告诉我工具返回结果。",
        }
    ],
}

stream = agent.stream_events(input, version="v3")

for name, item in stream.interleave("messages", "tool_calls", "values"):
    if name == "messages":
        print("=" * 30 + " 下面的是 stream.messages: " + "=" * 30)
        print(item.text)
    elif name == "tool_calls":
        print("=" * 30 + " 下面的是 stream.tool_calls: " + "=" * 30)
        print(item.tool_name, item.input)
    elif name == "values":
        print("=" * 30 + " 下面的是 stream.values: " + "=" * 30)
        print(item)
#     finalized = message.tool_calls.get()
#     if finalized:
#         print(f"finalized tool calls: {finalized}")

# print("\n" + "=" * 30 + " lifecycle of tool execution " + "=" * 30)
# for call in stream.tool_calls:
#     print(f"{call.tool_name}({call.input})")
#     for delta in call.output_deltas:
#         print(delta, end="", flush=True)
#     print(call.output, call.error)

# final_state = stream.output
# print("\n" + "=" * 30 + " LangGraph最终状态 " + "=" * 30)
# print(final_state)

##########################
# 工具内命名子智能体消息事件
##########################
# weather_agent = create_agent(
#     model=LLMs["gpt-5-nano"],
#     tools=[get_weather],
#     name="weather_agent",
# )


# def call_weather(query: str) -> str:
#     """Query the weather agent."""
#     result = weather_agent.invoke({"messages": [{"role": "user", "content": query}]})
#     return result["messages"][-1].text


# supervisor = create_agent(
#     model=LLMs["gpt-5-nano"],
#     tools=[call_weather],
#     name="supervisor",
# )

# stream = supervisor.stream_events(
#     {"messages": [{"role": "user", "content": "What's the weather in Boston?"}]},
#     version="v3",
# )

# for subagent in stream.subagents:
#     print("="*30+f" {subagent.name} " + "="*30)
#     for message in subagent.messages:
#         for token in message.text:
#             print(token, end="", flush=True)
#     print()
