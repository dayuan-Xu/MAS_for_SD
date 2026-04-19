import uuid
from dataclasses import dataclass

import yaml
from langchain_core.runnables import RunnableConfig

from src.paths import USER_SOFTWARE_DEV_TASKS_PATH


def deep_agent_based_team():
    from src.deep_agent_based_dev_team.deep_agent_based_team import leader, run_config
    from src.utils.graph_running_utils import multi_turn_conversation

    # toy_game = """使用Python GUI开发一个简单的五子棋游戏。"""

    multi_turn_conversation(leader, run_config)
    # 主派副智能体模式的缺点：
    # 只有主智能体具备用户接口，用户无法干预副智能体。
    # 虽然副智能体单独进行任务可以避免填充主智能体的上下文，但是主智能体也无法获知副智能体的真实发展状况，因而无法给予有效指导，尤其是当副智能体遇到复杂问题时。


@dataclass
class SoftwareDevTask:
    thread_id: str
    original_input: str

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建对象(用于 YAML 反序列化)"""
        return cls(
            thread_id=data['thread_id'],
            original_input=data['original_input']
        )

    def to_dict(self):
        """将对象转换为字典(用于 YAML 序列化)"""
        return {
            'thread_id': self.thread_id,
            'original_input': self.original_input
        }


def save_task_to_file(thread_id, original_input):
    # 将当前任务保存为yaml文件
    task = SoftwareDevTask(thread_id=thread_id, original_input=original_input)
    task_file_path = USER_SOFTWARE_DEV_TASKS_PATH / f"{thread_id}.yaml"
    # ⭐ 确保父目录存在
    task_file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(task_file_path, 'w', encoding='utf-8') as f:
        yaml.dump(task.to_dict(), f, allow_unicode=True)
        print(f"任务保存成功，保存路径为：{task_file_path}")


def agent_based_team():
    print("\n" + "=" * 41 + " ✨欢迎使用虚拟开发团队 " + "=" * 41 + "\n")
    original_software_requirement = input("请用一句话描述你的软件开发任务需求（or type 'exit' to quit）：")
    if original_software_requirement == "exit":
        print("\n" + "=" * 41 + " 退出程序 " + "=" * 41 + "\n")
        return

    thread_id = str(uuid.uuid4())
    save_task_to_file(thread_id, original_software_requirement)

    run_config: RunnableConfig = {
        "tags": ["agent_based_dev_team"],
        "run_name": "软件开发任务-1",
        "configurable": {"thread_id": thread_id}
    }

    from src.utils.graph_running_utils import end_to_end_dev

    end_to_end_dev(run_config, original_software_requirement)


if __name__ == "__main__":
    agent_based_team()
