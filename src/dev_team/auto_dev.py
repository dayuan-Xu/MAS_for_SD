import datetime
import logging
import time
from typing import cast

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import StreamPart

from src.config.config_logging import setup_logging
from src.dev_team.my_backend import LinuxSandboxBackend
from src.dev_team.team import AgentTeam
from src.utils.datasets import Task

logger = logging.getLogger(__name__)

# 自动化软件开发
TASK_DONE_IDENTIFIER = "TASK_DONE"
TASK_REJECTED_IDENTIFIER = "REQUEST_REJECTED"
MAX_REACT_LOOP_COUNT = 5  # dev_team最多运行5次


def target_str_in_AIMessage(target: str, msg: AIMessage):
    """检查消息是否包含 TASK_DONE 标识"""
    content = msg.content
    # 情况1：纯字符串
    if isinstance(content, str):
        return target in content

    # 情况2：列表类型
    if isinstance(content, list):
        for item in content:
            # 子项是字符串
            if isinstance(item, str):
                if target in item:
                    return True
            # 子项是字典（OpenAI 消息格式）
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    text_content = item.get("text", "")
                    if target in text_content:
                        return True
                # 处理其他类型的 content（如 image_url 等）
                elif item.get("type"):
                    logger.warning(f"跳过非文本内容类型: {item.get('type')}")

    return False


def is_task_done(msg: AIMessage):
    """检查消息是否包含 TASK_DONE 标识"""
    return target_str_in_AIMessage(TASK_DONE_IDENTIFIER, msg)


def is_task_rejected(msg: AIMessage):
    """检查消息是否包含 TASK_REJECTED 标识"""
    return target_str_in_AIMessage(TASK_REJECTED_IDENTIFIER, msg)


# 同步版本
def multi_react_loop_with_fixed_human_input(task: Task,
                                            dev_team: AgentTeam,
                                            recursion_limit: int = 300,
                                            ):
    """
    基于agentbay_based_dev_team的自动化软件开发
    
    Args:
        task: 软件开发任务
        dev_team: 开发团队实例
        recursion_limit: 递归限制
    """

    # 1 对于当前任务，判断是绿地开发还是棕地开发
    # 若是棕地开发，但是软件团队之前的开发过程基于的是易失的memory checkpointer，那么此时必须设置force_using_new_thread=True
    thread_id = dev_team.green_or_brown(task, force_using_new_thread=True)

    # 2 设定运行时配置
    task_name = task.name
    task_description = task.description_CN if task.description_CN else task.description

    config_across_runs: RunnableConfig = {
        "tags": [f"{task_name}"],
        "recursion_limit": recursion_limit,  # 顶层图的step上限，默认是25。
        # 根据实验结果，250次的recursion_limit对于Web模态的软件开发任务实现来说已经不够了，刚好够Web贪吃蛇编码阶段结束，尽管的确是有许多中间件的钩子函数占据了许多step。
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "leader"  # ⭐ 可选：为 Leader 设置 namespace
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

                # 检查是否为 TASK_DONE（任务成功完成）
                if latest_AI_message and is_task_done(latest_AI_message):
                    logger.info(
                        "\n" + "=" * 41 + f" ✅ Team Leader 输出 {TASK_DONE_IDENTIFIER}，开发团队认为软件已可交付！" + "=" * 41 + "\n")
                    task_success = True  # 标记成功
                    break

                # 检查是否为 TASK_REJECTED（请求被拒绝，与软件开发需求无关）
                if latest_AI_message and is_task_rejected(latest_AI_message):
                    logger.warning(
                        "\n" + "=" * 41 + f" ⚠️  Team Leader 输出 {TASK_REJECTED_IDENTIFIER}，用户输入与软件开发需求无关or输入的软件开发需求被认为太过模糊，请求被拒绝！" + "=" * 41 + "\n")
                    task_success = False  # 标记失败（因为不是正常的任务完成）
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
        logger.error(f"❌ 多轮 ReAct 循环中发生异常: {e}", exc_info=True)
        task_success = False  # 标记失败
        # 继续上抛
        raise e
    finally:
        # 无论成功还是失败，都会执行这里
        dev_team.download_and_cleanup(success=task_success)


# 异步版本
async def async_multi_react_loop_with_fixed_human_input(task: Task,
                                                        dev_team: AgentTeam,
                                                        recursion_limit: int = 500):
    """
    基于agentbay_based_dev_team的异步自动化软件开发
    
    Args:
        task: 软件开发任务
        dev_team: 开发团队实例（带MCP工具）
        recursion_limit: 递归限制

    :raises: Exception - 任务执行过程中发生的异常
    """

    # 1 对于当前任务，判断是绿地开发还是棕地开发
    # 若是棕地开发，但是软件团队之前的开发过程基于的是易失的memory checkpointer，那么此时必须设置force_using_new_thread=True
    thread_id = dev_team.green_or_brown(task, force_using_new_thread=True)

    # 2 设定运行时配置
    task_name = task.name
    task_description = task.description_CN if task.description_CN else task.description

    config_across_react_loop: RunnableConfig = {
        "tags": [f"{task_name}"],
        "recursion_limit": recursion_limit,  # 顶层图的step上限，默认是25。
        # 根据实验结果，250次的recursion_limit对于Web模态的软件开发任务实现来说已经不够了，刚好够Web贪吃蛇编码阶段结束，尽管的确是有许多中间件的钩子函数占据了许多step。
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "leader"  # ⭐ 可选：为 Leader 设置 namespace
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
            else:
                # 或者上个ReAct循环结束后，等待用户本轮输入
                react_loop_count = react_loop_count + 1

                # 检查是否为 TASK_DONE（任务成功完成）
                if latest_AI_message and is_task_done(latest_AI_message):
                    logger.info(
                        "\n" + "=" * 41 + f" ✅ Team Leader 输出 {TASK_DONE_IDENTIFIER}，开发团队认为软件已可交付！" + "=" * 41 + "\n")
                    task_success = True  # 标记成功
                    break

                # 检查是否为 TASK_REJECTED（请求被拒绝，与软件开发需求无关）
                if latest_AI_message and is_task_rejected(latest_AI_message):
                    logger.warning(
                        "\n" + "=" * 41 + f" ⚠️  Team Leader 输出 {TASK_REJECTED_IDENTIFIER}，用户输入与软件开发需求无关or输入的软件开发需求被认为太过模糊，请求被拒绝！" + "=" * 41 + "\n")
                    task_success = False  # 标记失败（因为不是正常的任务完成）
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
                **config_across_react_loop,
                "run_name": f'{task_name}_{react_loop_count}_{current_timestamp}'
            }

            # ⭐ 使用异步流式调用
            async for stream_part in dev_team.astream(input=dev_input, config=run_config, stream_mode=["values"],
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
        logger.error(f"❌ 多轮 ReAct 循环中发生异常: {e}", exc_info=True)
        task_success = False  # 标记失败
        # 继续上抛
        raise e
    finally:
        # 无论成功还是失败，都会保存成果物
        dev_team.download_and_cleanup(success=task_success)


# 一次自动化开发（同步）
def automatic_dev(task: Task) -> dict:
    """
    执行一次自动化软件开发任务
    
    Args:
        task: 软件开发任务

    Returns:
        dict: 包含任务执行结果的字典
    """
    # 记录开始时间
    start_time = time.time()

    # 为每个任务配置独立的日志系统
    setup_logging(task_name=task.name)

    try:
        # 创建与当前任务关联的沙盒实例
        sandbox = LinuxSandboxBackend(task_name=task.name)

        # 创建dev_team实例
        dev_team = AgentTeam(sandbox)

        # 开启独立开发，传递中断事件
        multi_react_loop_with_fixed_human_input(task, dev_team)

        # ⭐ 计算耗时
        elapsed_time = time.time() - start_time
        return {
            'task_name': task.name,
            'success': True,
            'elapsed_time': elapsed_time
        }

    except Exception as e:
        # ⭐ 计算耗时（即使失败也要统计）
        elapsed_time = time.time() - start_time
        return {
            'task_name': task.name,
            'success': False,
            'elapsed_time': elapsed_time,
            'error': str(e)
        }


# 一次自动化开发（异步）
async def async_automatic_dev(task: Task):
    """
    异步执行一次自动化软件开发任务（使用带MCP工具的DevTeam）

    Args:
        task: 软件开发任务
    """
    # 记录开始时间
    start_time = time.time()

    # 为每个任务配置独立的日志系统
    setup_logging(task_name=task.name)

    # 创建与当前任务关联的沙盒实例
    with LinuxSandboxBackend(task_name=task.name) as sandbox:

        # 创建带 MCP 工具的dev_team实例
        dev_team = await AgentTeam.create_with_agentbay_mcp_tools(sandbox)
        try:

            # 开启独立开发
            await async_multi_react_loop_with_fixed_human_input(task, dev_team,
                                                                recursion_limit=350)  # tank battle刚好是300次顶层节点结束
        except Exception as e:
            # 计算耗时（即使失败也要统计）
            elapsed_time = time.time() - start_time
            logger.error(f"❌ 任务 '{task.name}' 执行失败 ，多轮react loop中出现异常: {e}", exc_info=True)
            return {
                'task_name': task.name,
                'success': False,
                'elapsed_time': elapsed_time,
                'error': str(e)
            }
        else:
            # 计算耗时
            elapsed_time = time.time() - start_time
            return {
                'task_name': task.name,
                'success': True,
                'elapsed_time': elapsed_time
            }
