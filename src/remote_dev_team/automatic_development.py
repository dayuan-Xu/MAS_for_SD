import datetime
import logging
import uuid
from typing import cast

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import StreamPart

from src.remote_dev_team.agentbay_based_dev_team import AgentBayBasedDevTeam
from src.utils.datasets import Task

logger = logging.getLogger(__name__)

# 自动化软件开发
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
                    logger.warning(f"跳过非文本内容类型: {item.get('type')}")

    return False


def multi_turn_conversation_with_fixed_human_input(task: Task, dev_team: AgentBayBasedDevTeam):
    """
    基于agentbay_based_dev_team的自动化软件开发
    """
    # 1 保存负责当前任务的thread_id到文件，方便后续查看具体运行情况
    thread_id = str(uuid.uuid4())
    # ⭐ 调用 dev_team 的方法保存任务记录
    dev_team.save_traceable_task_to_file(thread_id=thread_id, task=task)

    # 2 设定运行时配置
    task_name = task.name
    task_description = task.description_CN if task.description_CN else task.description

    config_across_runs: RunnableConfig = {
        "tags": [f"{task_name}"],
        "recursion_limit": 25 * 10,  # 顶层图的step上限，默认是25
        "configurable": {
            "thread_id": thread_id,
        }
    }

    input_text = None
    react_loop_count = 1
    latest_AI_message: AIMessage | None = None
    task_success = False  # 标记任务是否成功

    try:
        while True:
            # 第一次用户输入
            if input_text is None:
                input_text = f"针对一个软件需求完成自动化开发。\n软件需求描述如下：\ntask_name:{task_name}\ntask_description:{task_description}"
                # input_text = f"本次仅做测试，你写入一个新的测试用文本文件到当前项目工作空间./warehouse/snake_game/下，之后输出‘TASK_DONE"
            else:
                # 或者上个ReAct循环结束后，等待用户本轮输入
                react_loop_count = react_loop_count + 1
                if latest_AI_message and is_task_done(latest_AI_message):
                    logger.info(
                        "\n" + "=" * 41 + f" ✅ Team Leader 输出 {TASK_DONE_IDENTIFIER}，开发团队认为软件已可交付！" + "=" * 41 + "\n")
                    task_success = True  # 标记成功
                    break

                if react_loop_count > MAX_REACT_LOOP_COUNT:
                    logger.error(
                        "\n" + "=" * 41 + f" ❌ 开发团队已运行 {MAX_REACT_LOOP_COUNT} 轮 ReAct 循环，失败退出！" + "=" * 41 + "\n")
                    task_success = False  # 标记失败
                    break

                input_text = f"用户无暇亲临指导，请确保软件符合原始需求并可交付，否则继续开发。若当前软件已可交付则仅仅回复'{TASK_DONE_IDENTIFIER}'"

            dev_input = {"messages": [{"role": "user", "content": input_text}]}

            logger.info(
                "\n" + "=" * 41 + f" 💡 开启第 {react_loop_count} 轮 ReAct 循环: {task_name}_{react_loop_count} " + "=" * 41 + "\n")

            current_timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            run_config = {
                **config_across_runs,
                "run_name": f'{task_name}_{react_loop_count}_{current_timestamp}'
            }

            for stream_part in dev_team.stream(input=dev_input, config=run_config, stream_mode=["values"],
                                               subgraphs=True, version="v2"):
                # values流式输出模式下，streamPart对象是ValuesStreamPart类型,包含type、ns、data、interrupts三个key
                stream_part = cast(StreamPart, stream_part)

                data = stream_part["data"]
                messages = data["messages"]

                # 取最新AIMessage
                latest_msg = messages[-1]
                if latest_AI_message is None and isinstance(latest_msg, AIMessage):
                    latest_AI_message = latest_msg
                    continue

                if isinstance(latest_msg, AIMessage) and latest_msg.id != latest_AI_message.id:
                    latest_AI_message = latest_msg

    except Exception as e:
        # 捕获主循环中的异常（如 Session 过期）
        logger.error(f"❌ ReAct 循环中发生异常: {e}", exc_info=True)
        task_success = False  # 标记失败
    finally:
        # ⭐ 关键：无论成功还是失败，都会执行这里
        dev_team.download_and_cleanup(success=task_success)


# 一次自动化开发
def automatic_dev(task: Task):
    from src.utils.my_sandbox import MySandbox

    # 创建与当前任务关联的沙盒实例
    sandbox = MySandbox(task_name=task.name)

    # 创建dev_team实例
    dev_team = AgentBayBasedDevTeam(sandbox)

    multi_turn_conversation_with_fixed_human_input(task, dev_team)
