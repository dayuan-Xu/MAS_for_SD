# 技能Skill是一种动态扩展LLM上下文窗口的方式
# 当智能体启动时，自动读取所有md格式的可用技能文件中的yaml前言部分到System Prompt中
# 每个SKILL的yaml前言用一句话说明了该SKILL可以用来做什么、什么时候用它。
# 之后面对用户输入的提示词，智能体会依据每个技能的yaml前言决定加载哪些技能（对应的md文件的正文）到上下文窗口
# 每个SKILL.md文件的正文body text就是简短的指导智能体该如何完成某种特定任务的step-by-step的详细指令、指示。
# 比如查阅开源框架langgraph的文档来回答用户对此的相关理解性疑问、技术性疑问。

# 可以把SKILL看作一个指导智能体干活的工作流参考。

# 代表memory的AGENTS.md和skills的区别？


# When to use skills and tools
# 何时使用技能和工具
# These are a few general guidelines for using tools and skills:
# 以下是使用工具和技能的一些通用指南：

# Use skills when there is a lot of context to reduce the number of tokens in the system prompt.
# 在有大量上下文时使用技能，相较于大量tools，使用skills这种渐进式暴露，可以一定程度上减少系统提示中的Token数量！！！！！

# Use skills to bundle capabilities together into larger actions and provide additional context beyond single tool descriptions.
# 利用技能将能力整合成更大的行动，提供超越单一工具描述的额外背景。

# Use tools if the agent does not have access to the file system.
# 如果代理无法访问文件系统，可以使用工具。
"""
Instructions are task-specific and potentially large
skills会按照任务需要选择性的挑选一个skill的body注入system prompt（只在需要时读取技能body，叫做“渐进式暴露”），
比如指令是针对特定任务的，且可能是大块文字的

Context is always relevant (project conventions, preferences)
memory文件总是会在智能体启动时注入到system prompt，
比如一些始终和任务相关的上下文（项目惯例、偏好）。
"""
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver
from deepagents.backends.filesystem import FilesystemBackend
from langgraph.types import Command
from src.config.llm import LLMs
from src.paths import DEEP_AGENT_WORKSPACE

# Checkpointer is REQUIRED for human-in-the-loop
checkpointer = MemorySaver()

agent = create_deep_agent(
    model=LLMs["gpt-5-nano"],
    backend=FilesystemBackend(root_dir=DEEP_AGENT_WORKSPACE, virtual_mode=True),
    skills=["/skills/"],
    memory=[],
    interrupt_on={
        "write_file": True,  # Default: approve, edit, reject
        "read_file": False,  # No interrupts needed
        "edit_file": True    # Default: approve, edit, reject
    },
    checkpointer=checkpointer,  # Required! for human-in-the-loop
)

# input_text = "What is langgraph?"

config={"configurable": {"thread_id": "12345"}}

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
        for stream_part in agent.stream(input=agent_input, config=config, stream_mode=["values"], version="v2"):
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

            data = stream_part["data"]
            latest_message = data["messages"][-1]
            if last_output_msg is None:
                latest_message.pretty_print()
                last_output_msg = latest_message
            elif latest_message != last_output_msg:
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

