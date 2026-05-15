import logging
from dataclasses import dataclass

import yaml

from src.config.config_logging import experiment_logger

logger = logging.getLogger(__name__)


@dataclass
class Task:
    "通用软件开发任务数据类"
    number: int = -1  # 在数据集中的编号
    name: str = ""  # 任务名称
    name_CN: str = ""  # 任务名称（中文）
    description: str = ""  # 任务描述
    description_CN: str = ""  # 任务描述（中文）

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建对象(用于 YAML 反序列化)"""
        return cls(
            number=data['number'],
            name=data['name'],
            name_CN=data['name_CN'],
            description=data['description'],
            description_CN=data['description_CN']
        )

    def to_dict(self):
        """将对象转换为字典(用于 YAML 序列化)"""
        return {
            'number': self.number,
            'name': self.name,
            'name_CN': self.name_CN,
            'description': self.description,
            'description_CN': self.description_CN
        }


@dataclass
class SoftwareDevDataset:
    """通用软件开发任务数据集"""
    name: str = ""  # 数据集名称
    description: str = ""  # 数据集描述
    tasks: list[Task] = None  # 软件开发任务列表
    task_name_to_task: dict[str, Task] = None

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建对象(用于 YAML 反序列化)"""
        tasks = [Task.from_dict(task) for task in data['tasks']]
        return cls(
            name=data['name'],
            description=data['description'],
            tasks=tasks,
            task_name_to_task={task.name: task for task in tasks}
        )


def load_dataset(file_path) -> SoftwareDevDataset:
    """从yaml文件加载数据集到数据类中"""
    experiment_logger.info(f"开始加载数据集: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        loaded_data = yaml.safe_load(f)
    dataset = SoftwareDevDataset.from_dict(loaded_data)

    experiment_logger.info(f"数据集名称: {dataset.name}")
    experiment_logger.info(f"数据集描述: {dataset.description}")
    experiment_logger.info(f"数据集任务数量: {len(dataset.tasks)}")
    return dataset


# ========== TraceableTask 数据类 ==========

@dataclass
class TraceableTask:
    """可追踪的任务对象，用于保存任务启动记录。"""
    thread_ids: list[str]  # dev team为完成该任务而创建的线程ID
    task_context_box_names: list[str]
    task_context_box_ids: list[str]
    task: Task

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建对象(用于 YAML 反序列化)"""
        return cls(
            thread_ids=data['thread_ids'],
            task_context_box_names=data['task_context_box_names'],
            task_context_box_ids=data['task_context_box_ids'],
            task=Task.from_dict(data['task'])
        )

    def to_dict(self):
        """将对象转换为字典(用于 YAML 序列化)"""
        return {
            'thread_ids': self.thread_ids,
            'task_context_box_names': self.task_context_box_names,
            'task_context_box_ids': self.task_context_box_ids,
            'task': self.task.to_dict()
        }

    def update(self, new_thread_id, new_box_name, new_box_id):
        self.thread_ids.append(new_thread_id)
        self.task_context_box_names.append(new_box_name)
        self.task_context_box_ids.append(new_box_id)
