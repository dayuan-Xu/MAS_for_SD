from typing import cast

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Interrupt, Command, StreamPart


def get_human_decisions(input_interrupt: Interrupt) -> list[dict]:
    interrupt_value = input_interrupt.value
    action_requests = interrupt_value["action_requests"]
    review_configs = interrupt_value["review_configs"]

    # Create a lookup map from tool name to review config
    config_map = {cfg["action_name"]: cfg for cfg in review_configs}

    # Display the pending actions to the user
    # 并发工具调用下，可能会有多个工具调用被中断，这些中断需要人类顺序逐个处理
    user_decisions = []
    for action in action_requests:
        review_config = config_map[action["name"]]
        print(f"Tool: {action['name']}")
        print(f"Arguments: {action['args']}")
        print(f"Allowed decisions: {review_config['allowed_decisions']}")
        decision_type = input("\nEnter your decision('a'-approve/'r'-reject/'e'-edit) for this tool_call: ")
        # 提高容错性，允许用户输入时大小写不敏感，并且去掉首尾空格
        decision_type = decision_type.strip().lower()

        if decision_type == "approve" or decision_type == "a":
            user_decisions.append({"type": "approve"})
        elif decision_type == "reject" or decision_type == "r":
            user_decisions.append({"type": "reject"})
        elif decision_type == "edit" or decision_type == "e":
            new_args = {}
            for k in action["args"]:
                new_arg_value = input(f"请为{k} = {action['args'][k]}提供一个新值:")
                new_args[k] = new_arg_value
            user_decisions.append({"type": "edit", "edited_action": {"name": action["name"], "args": new_args}})
        else:
            print("无效的决策输入，默认做出的决定为reject")
            user_decisions.append({"type": "reject"})

    # 验证decisions数量与action_requests数量是否匹配
    if len(user_decisions) != len(action_requests):
        raise ValueError(
            f"决策数量({len(user_decisions)})与待处理工具调用数量({len(action_requests)})不匹配！"
        )
    return user_decisions


def multi_turn_conversation(agent: CompiledStateGraph, run_config: RunnableConfig):
    """
    为DeepAgent设计的多轮对话，
    在values模式下流式输出父图、子图消息，流式输出版本version="v2"
    支持父图、子图人在循环发生时收集人类反馈。
    """

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
            """
            问：如何控制一轮完整的ReAct循环中模型调用与工具调用的最大循环次数？难道任务完不成就一直让model-tool loop没有上限地一直持续下去吗？
            答：
            Deep Agents 是基于 LangGraph 构建的，create_deep_agent 返回一个编译后的 LangGraph 可运行图。
            LangGraph 的 ReAct 代理默认有 max_iterations 参数来控制一轮完整循环（model → tool → model）的最大次数。
            默认 max_iterations=25，超过此次数会抛出 MaxIterationsExceededError 异常，而不是无限循环。
            可以人为在invoke智能体时通过config指定：
            result = agent.invoke(
                {"messages": [{"role": "user", "content": "query"}]},
                config={
                    "recursion_limit": 10  # 最大 10 次 model-tool 循环
                }
            )

            recursion_limit: int
            "Maximum number of times a call can recurse.

            If not provided, defaults to `25`."
            """
            for stream_part in agent.stream(input=agent_input, config=run_config, stream_mode=["values"],
                                            subgraphs=True, version="v2"):
                # values流式输出模式下，streamPart对象是ValuesStreamPart类型,包含type、ns、data、interrupts三个key
                stream_part = cast(StreamPart, stream_part)
                # 先判断本次ReAct循环是否需要人类参与
                if stream_part['interrupts']:
                    # 如果真需要人类参与
                    print(
                        "\n=========================================\n工具中断触发，需要人类干预，之后才能继续进行本轮ReAct循环\n")
                    interrupt = stream_part['interrupts'][0]
                    decisions = get_human_decisions(interrupt)

                    # Resume execution with decisions
                    agent_input = Command(resume={"decisions": decisions})
                    human_in_the_loop = True
                    # 暂停当前ReAct执行，直接继续下一次ReAct
                    break

                namespace = stream_part["ns"]
                data = stream_part["data"]
                latest_message = data["messages"][-1]

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

            # 判断本次ReAct循环是否完整地结束了
            if human_in_the_loop:
                # 不是完整地结束
                print(
                    "\n=========================================\n发生了人在循环，已经收集到人类干预，继续进行本轮ReAct循环\n")
                human_in_the_loop = False  # 继续进行本轮ReAct循环前，恢复默认值
                continue
            else:
                # 说明是完整地结束
                print("\n=========================================\n本轮ReAct循环圆满结束\n")
                current_loop_ends_totally = True

    print("多轮对话成功结束。")
