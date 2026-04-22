from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Interrupt, Command, StreamPart
from typing import cast

from src.agentbay_based_dev_team.leader import leader


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


# 运行给定的LangGraph，支持多轮对话（即每次人类输入引发一次ReAct循环，可以有多次人类对话直至人类输入exit）
def multi_turn_conversation(agent: CompiledStateGraph, run_config: RunnableConfig):
    """
    为DeepAgent设计的多轮对话，
    在values模式下流式输出父图、子图消息，流式输出版本version="v2"
    支持父图、子图人在循环发生时收集人类反馈。
    """

    printed_msg_ids = set()  # 用于记录已经输出过的消息id，避免重复输出
    while True:
        # 第一次用户输入；或者上个ReAct循环完整结束后，等待用户新输入令。

        input_text = input("Your input (or type 'exit' to quit): ")

        if input_text == "exit":
            print("\n" + "=" * 41 + " 👟用户输入了exit，结束多轮对话 " + "=" * 41 + "\n")
            break

        agent_input = {"messages": [{"role": "user", "content": input_text}]}

        print("\n" + "=" * 41 + " 💡下面开启全新的一轮ReAct循环 " + "=" * 41 + "\n")
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
                        "\n" + "=" * 41 + " 🕵️‍♀️人在循环：工具触发中断，需要人类干预，之后才能继续进行本轮ReAct循环 " + "=" * 41 + "\n")
                    interrupt = stream_part['interrupts'][0]
                    decisions = get_human_decisions(interrupt)

                    # Resume execution with decisions
                    agent_input = Command(resume={"decisions": decisions})
                    human_in_the_loop = True
                    # 暂停当前ReAct执行，直接继续下一次ReAct
                    break

                namespace = stream_part["ns"]
                data = stream_part["data"]
                messages = data["messages"]

                # 遍历所有消息，而不是只取最后一条
                # 这样可以确保不会漏掉任何新产生的消息（特别是并发工具调用后的多个Tool Message）
                for msg in messages:
                    if msg.id not in printed_msg_ids:
                        # 只打印之前没打印过的新消息
                        if namespace:
                            # 如果namespace不是空元组，而是通往哪个调用子图的节点的路径，则说明是data是子图发射的事件（新消息），
                            # 比如是 'tools:5927c259-58a6-e7bb-c9fe-0c051e90c825'
                            print("\n" + "=" * 33 + "👇 下面这条消息是子图的新消息\n")
                        msg.pretty_print()
                        printed_msg_ids.add(msg.id)
            # 判断本次ReAct循环是否完整地结束了
            if human_in_the_loop:
                # 不是完整地结束
                print("\n" + "=" * 40 + " 👌发生了人在循环，已经收集到人类干预，继续进行本轮ReAct循环\n")
                human_in_the_loop = False  # 继续进行本轮ReAct循环前，恢复默认值
                continue
            else:
                # 说明是完整地结束
                print("\n", "=" * 41, "本轮ReAct循环圆满结束", "=" * 41, "\n")
                current_loop_ends_totally = True

    print("\n", "=" * 41, "✋多轮对话成功结束", "=" * 41, "\n")


# 端到端软件开发
TASK_DONE_IDENTIFIER = "TASK_DONE"
MAX_REACT_LOOP_COUNT = 5  # dev_team最多运行5次


def is_task_done(msg: AIMessage):
    content = msg.content
    # 情况1：纯字符串
    if isinstance(content, str):
        return TASK_DONE_IDENTIFIER in content

    # 情况2：列表类型
    if isinstance(content, list):
        for item in content:
            # 子项是字符串
            if isinstance(item, str):
                if TASK_DONE_IDENTIFIER in item:
                    return True
            # 子项是字典（OpenAI 消息格式）
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    text_content = item.get("text", "")
                    if TASK_DONE_IDENTIFIER in text_content:
                        return True
                # 处理其他类型的 content（如 image_url 等）
                elif item.get("type"):
                    print(f"[yellow]⚠ 跳过非文本内容类型: {item.get('type')}[/yellow]")

    return False


def multi_turn_conversation_with_fixed_human_input(config_across_runs: RunnableConfig, task_description: str):
    """
    基于agentbay_based_dev_team的端到端软件开发
    """
    task_name = config_across_runs["tags"][0]
    agent = leader
    input_text = None
    react_loop_count = 1
    latest_AI_message: AIMessage | None = None

    while True:
        # 第一次用户输入
        if input_text is None:
            input_text = f"针对一个软件需求完成端到端开发，禁止请求任何用户反馈。\n需求描述如下：\n{task_description}"
        else:
            # 或者上个ReAct循环结束后，等待用户本轮输入
            react_loop_count = react_loop_count + 1
            if latest_AI_message and is_task_done(latest_AI_message):
                print("\n" + "=" * 41 + f" ✅ 输出{TASK_DONE_IDENTIFIER}，dev_team认为软件已经可交付!" + "=" * 41 + "\n")
                break

            if react_loop_count > MAX_REACT_LOOP_COUNT:
                print(
                    "\n" + "=" * 41 + f" ❌ dev_team已经运行了{MAX_REACT_LOOP_COUNT}轮ReAct循环，失败退出！" + "=" * 41 + "\n")
                break

            input_text = f"用户无暇亲临指导，请确保软件符合原始需求并可交付，否则继续开发。若当前软件已可交付则仅仅回复'{TASK_DONE_IDENTIFIER}'"

        agent_input = {"messages": [{"role": "user", "content": input_text}]}

        print("\n" + "=" * 41 + f" 💡 下面开启一轮ReAct循环 {task_name}_{react_loop_count} " + "=" * 41 + "\n")

        run_config = {
            **config_across_runs,
            "run_name": f'{task_name}_{react_loop_count}'
        }

        for stream_part in agent.stream(input=agent_input, config=run_config, stream_mode=["values"],
                                        subgraphs=True, version="v2"):
            # values流式输出模式下，streamPart对象是ValuesStreamPart类型,包含type、ns、data、interrupts三个key
            stream_part = cast(StreamPart, stream_part)

            data = stream_part["data"]
            messages = data["messages"]

            # 取最新AIMessage
            latest_msg = messages[-1]
            if latest_AI_message is None:
                latest_AI_message = latest_msg
                continue

            if isinstance(latest_msg, AIMessage) and latest_msg.id != latest_AI_message.id:
                latest_AI_message = latest_AI_message
