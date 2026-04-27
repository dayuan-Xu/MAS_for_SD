import logging
from dataclasses import dataclass

import yaml

from src.paths import DATASETS_PATH

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

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建对象(用于 YAML 反序列化)"""
        tasks = [Task.from_dict(task) for task in data['tasks']]
        return cls(
            name=data['name'],
            description=data['description'],
            tasks=tasks
        )


def load_dataset(file_path) -> SoftwareDevDataset:
    """从yaml文件加载数据集到数据类中"""
    logger.info(f"开始加载数据集: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        loaded_data = yaml.safe_load(f)
    dataset = SoftwareDevDataset.from_dict(loaded_data)

    logger.info(f"数据集名称: {dataset.name})")
    logger.info(f"数据集描述: {dataset.description}")
    logger.info(f"数据集任务数量: {len(dataset.tasks)}")
    return dataset


software_dev_7_path = DATASETS_PATH / "software_dev_7.yaml"
software_dev_7 = load_dataset(software_dev_7_path)
