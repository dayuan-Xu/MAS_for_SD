import uuid
import yaml
from dataclasses import dataclass
from langchain_core.runnables import RunnableConfig

from src.datasets import Task, software_dev_7
from src.paths import USER_SOFTWARE_DEV_TASKS_PATH
from src.utils.graph_running_utils import multi_turn_conversation_with_fixed_human_input


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
    # 将当前对象保存为yaml文件
    task_file_path = USER_SOFTWARE_DEV_TASKS_PATH / f"{traceable_task.task.name}.yaml"
    # ⭐ 确保父目录存在
    task_file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(task_file_path, 'w', encoding='utf-8') as f:
        yaml.dump(traceable_task.to_dict(), f, allow_unicode=True)
        print(f"任务保存成功，保存路径为：{task_file_path}")


# 一次端到端开发
def end_to_end_dev(task: Task):
    print("\n" + "=" * 41 + " ✨开始端到端开发 " + "=" * 41 + "\n")

    # 1 保存负责当前任务的thread_id到文件，方便后续查看具体运行情况
    thread_id = str(uuid.uuid4())
    traceable_task = TraceableTask(thread_id=thread_id, task=task)
    save_traceable_task_to_file(traceable_task)

    # 2 开启完整的端到端开发流程
    task_name = task.name
    task_description = task.description_CN if task.description_CN else task.description
    config_across_runs: RunnableConfig = {
        "tags": [f"{task_name}"],
        "recursion_limit": 30,
        "configurable": {
            "thread_id": thread_id,
        }
    }

    multi_turn_conversation_with_fixed_human_input(config_across_runs, task_description)

    print("\n" + "=" * 41 + " ✨端到端开发完成 " + "=" * 41 + "\n")


if __name__ == "__main__":
    task1 = software_dev_7.tasks[0]
    end_to_end_dev(task1)
