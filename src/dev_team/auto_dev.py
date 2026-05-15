import datetime
import logging
import time

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from src.config.config_logging import setup_logging
from src.dev_team.my_backend import LinuxSandboxBackend
from src.dev_team.team import AgentTeam
from src.dev_team.team_config import TASK_DONE_IDENTIFIER, TASK_REJECTED_IDENTIFIER, MAX_REACT_LOOP_COUNT, \
    EXCEPTION_IDENTIFIER
from src.utils.common import is_task_done, is_task_rejected
from src.utils.datasets import Task

logger = logging.getLogger(__name__)


def should_end_multi_loop(_react_loop_count, msg: AIMessage | None) -> tuple[bool, bool]:
    if not isinstance(msg, AIMessage):
        raise Exception(f"一次ainvoke调用后最新的图消息不是AIMessage，而是: {type(msg)}")

    # 检查是否为 TASK_DONE（任务成功完成）
    if is_task_done(msg):
        logger.info(
            "\n" + "=" * 41 + f" ✅ Team Leader 输出 {TASK_DONE_IDENTIFIER}，开发团队认为软件已可交付！" + "=" * 41 + "\n")
        task_success_ = True
        should_break_ = True
        return task_success_, should_break_

    # 检查是否为 TASK_REJECTED（请求被拒绝，与软件开发需求无关）
    if is_task_rejected(msg):
        logger.warning(
            "\n" + "=" * 41 + f" ⚠️  Team Leader 输出 {TASK_REJECTED_IDENTIFIER}，用户输入与软件开发需求无关or输入的软件开发需求被认为太过模糊，请求被拒绝！" + "=" * 41 + "\n")
        task_success_ = False
        should_break_ = True
        return task_success_, should_break_

    # 检查是否为 EXCEPTION（请求被拒绝，与软件开发需求无关）
    if is_task_rejected(msg):
        logger.warning(
            "\n" + "=" * 41 + f" ⚠️  Team Leader 输出 {EXCEPTION_IDENTIFIER}，出现异常情况！" + "=" * 41 + "\n")
        task_success_ = False
        should_break_ = True
        return task_success_, should_break_

    if _react_loop_count > MAX_REACT_LOOP_COUNT:
        logger.error(
            "\n" + "=" * 41 + f" ❌ 开发团队已运行 {MAX_REACT_LOOP_COUNT} 轮 ReAct 循环，失败退出！" + "=" * 41 + "\n")

        task_success_ = False
        should_break_ = True
        return task_success_, should_break_

    return False, False


# 异步版本
async def multi_react_loop(task: Task,
                           dev_team: AgentTeam,
                           recursion_limit: int = 10_000):
    """
    基于agentbay_based_dev_team的异步自动化软件开发
    
    Args:
        task: 软件开发任务
        dev_team: 开发团队实例（带MCP工具）
        recursion_limit: 递归限制
        enable_brown: 是否复用已有thread_id，启用棕地开发，

    :raises: Exception - 任务执行过程中发生的异常
    """
    # 2 设定运行时配置
    task_name = task.name
    task_description = task.description_CN if task.description_CN else task.description
    task_working_dir = dev_team.task_working_dir

    thread_id = dev_team.get_thread_id()
    is_brown = dev_team.get_is_brown()

    config_across_react_loop: RunnableConfig = {
        "tags": [f"{task_name}"],
        "recursion_limit": recursion_limit,
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": dev_team.team_type  # ⭐ 可选：为 Leader/Planner 设置 namespace
        }
    }

    input_text = None
    react_loop_count = 1
    latest_AI_message = None
    task_success = False  # 标记任务是否成功

    try:
        while True:
            # 第一次用户输入
            if input_text is None:
                if is_brown:
                    # 真正进行棕地开发
                    input_text = (f"棕地开发！继续完成未完成的‘基础版’软件功能点\n"
                                  f"软件需求描述如下：\n"
                                  f"task_name:{task_name}\n"
                                  f"task_description:{task_description}\n"
                                  f"项目工作空间为：{task_working_dir}\n")
                else:
                    # 绿地开发
                    input_text = (f"针对一个软件需求完成开发。\n"
                                  f"软件需求描述如下：\n"
                                  f"task_name:{task_name}\n"
                                  f"task_description:{task_description}\n"
                                  f"项目工作空间为：{task_working_dir}")


            else:
                # 或者上个ReAct循环结束后，等待用户本轮输入
                react_loop_count = react_loop_count + 1
                task_success, should_break = should_end_multi_loop(react_loop_count, latest_AI_message)
                if should_break:
                    break

                # input_text = f"用户无暇亲临指导，请确保软件符合原始需求并可交付，否则继续开发。若当前软件已可交付则仅仅回复'{TASK_DONE_IDENTIFIER}'"
                input_text = f"若当前软件已经完成“基础版”下所有软件功能点的开发，则仅回复'{TASK_DONE_IDENTIFIER}'"

            dev_input = {"messages": [{"role": "user", "content": input_text}]}

            current_timestamp = datetime.datetime.now().strftime("%H:%M")
            run_config = {
                **config_across_react_loop,
                "run_name": f'{task_name}_{react_loop_count}_{current_timestamp}'
            }

            logger.info("=" * 41)
            logger.info(f" 开启第 {react_loop_count} 轮 ReAct 循环: {task_name}_{react_loop_count} ")
            logger.info("=" * 41)

            # 使用异步调用（一次ainvoke就是一个完整的ReAct loop）
            result = await dev_team.ainvoke(input=dev_input, config=run_config)

            # 从返回结果中获取messages, 取最新AIMessage
            if result["messages"]:
                latest_msg = result['messages'][-1]
                if isinstance(latest_msg, AIMessage):
                    latest_AI_message = latest_msg
                else:
                    raise Exception(f"一次ainvoke调用后最新的图消息不是AIMessage，而是: {type(latest_msg)}")

    except Exception as e:
        # 捕获主循环中的异常（如 Session 过期）
        logger.error(f"❌ 多轮 ReAct 循环中发生异常: {e}", exc_info=True)
        task_success = False  # 标记失败
        # 继续上抛
        raise e
    finally:
        # 无论成功还是失败，都会保存成果物
        dev_team.download_and_cleanup(success=task_success)


# 一次自动化开发
async def auto_dev(task: Task, enable_brown=False):
    """
    异步执行一次自动化软件开发任务（使用带MCP工具的DevTeam）

    Args:
        task: 软件开发任务
        enable_brown: 是否复用旧thread_id
    """
    # 记录开始时间
    start_time = time.time()

    # 为每个任务配置独立的日志系统
    setup_logging(task_name=task.name, log_level=logging.INFO)
    logger.info(f"任务开始: {task.name}，对于该任务，当前是否启用棕地开发检测：{enable_brown}")

    try:

        # 创建与当前任务关联的沙盒实例，是否复用task box由enable_brown控制
        with LinuxSandboxBackend(task_name=task.name) as sandbox:

            # 创建带 MCP 工具的dev_team实例
            dev_team = await AgentTeam.create_with_agentbay_mcp(sandbox)
            try:
                # 开启多轮react loop
                await multi_react_loop(
                    task,
                    dev_team,
                    recursion_limit=10_000,  # 为每个智能体设定的顶层节点步数
                )
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
    except RuntimeError as e:
        if "沙盒会话即将达到最大运行时间限制" in str(e):
            # 捕获并打印异常
            logger.error(f"❌ 本次软件开发任务运行时间过长，沙盒自动释放了，任务 '{task.name}' 执行失败: {e}",
                         exc_info=True)
            return {'task_name': task.name, 'success': False, 'elapsed_time': time.time() - start_time}
