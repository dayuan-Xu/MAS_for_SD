import logging
import uuid
import yaml
from dataclasses import dataclass
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import StreamPart
from typing import cast

from src.paths import USER_SOFTWARE_DEV_TASKS_PATH
from src.remote_dev_team.agentbay_based_dev_team import AgentBayBasedDevTeam
from src.utils.datasets import Task
from src.utils.my_sandbox import MySandbox

logger = logging.getLogger(__name__)


@dataclass
class TraceableTask:
    thread_id: str
    task: Task

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建对象(用于 YAML 反序列化)"""
        return cls(
            thread_id=data['thread_id'],
            task=Task.from_dict(data['task'])
        )

    def to_dict(self):
        """将对象转换为字典(用于 YAML 序列化)"""
        return {
            'thread_id': self.thread_id,
            'task': self.task.to_dict()
        }


def save_traceable_task_to_file(traceable_task: TraceableTask):
    """保存任务启动记录到 YAML 文件。
    
    ⭐ 优化：如果文件已存在，则跳过写入，避免重复保存
    
    Args:
        traceable_task: 可追踪的任务对象
    """
    task_file_path = USER_SOFTWARE_DEV_TASKS_PATH / f"{traceable_task.task.name}.yaml"

    # ⭐ 关键优化：检查文件是否已存在
    if task_file_path.exists():
        logger.info(f"⏭️ 任务启动记录已存在，跳过保存: {task_file_path}")
        return

    # 确保父目录存在
    task_file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(task_file_path, 'w', encoding='utf-8') as f:
        yaml.dump(traceable_task.to_dict(), f, allow_unicode=True)
        logger.info(f"✅ 任务启动记录已保存: {task_file_path}")


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
    traceable_task = TraceableTask(thread_id=thread_id, task=task)
    save_traceable_task_to_file(traceable_task)

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
                input_text = f"针对一个软件需求完成自动化开发，禁止请求任何用户反馈。\n需求描述如下：\n{task_description}"
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

            run_config = {
                **config_across_runs,
                "run_name": f'{task_name}_{react_loop_count}'
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
        logger.info("🧹 进入清理阶段，开始清理资源和下载成果物...")
        dev_team.cleanup_and_download(success=task_success)
        logger.info("✅ 清理阶段完成")


# 一次自动化开发
def automatic_dev(task: Task):
    # 创建与当前任务关联的沙盒实例
    sandbox = MySandbox(task_name=task.name)

    # 创建dev_team实例
    dev_team = AgentBayBasedDevTeam(sandbox)

    multi_turn_conversation_with_fixed_human_input(task, dev_team)
