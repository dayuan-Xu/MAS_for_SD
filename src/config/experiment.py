from dataclasses import dataclass

import yaml

from src.paths import DATASETS_PATH


@dataclass
class Task:
    "任务数据类"
    number: int
    name: str
    description: str
    description_CN: str

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建对象(用于 YAML 反序列化)"""
        return cls(
            number=data['number'],
            name=data['name'],
            description=data['description'],
            description_CN=data['description_CN']
        )


@dataclass
class SoftwareDevDataset:
    """软件开发数据集"""
    name: str = "SoftwareDev"
    description: str = "SoftwareDev是由MetaGPT提出的一个用于测试多智能体软件软件开发能力的数据集。"
    tasks: list[Task] = None

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建对象(用于 YAML 反序列化)"""
        tasks = [Task.from_dict(task) for task in data['tasks']]
        return cls(
            name=data['name'],
            description=data['description'],
            tasks=tasks
        )


def load_dataset(file_path):
    """从yaml文件加载数据集到数据类中"""
    with open(file_path, 'r', encoding='utf-8') as f:
        loaded_data = yaml.safe_load(f)
    dataset = SoftwareDevDataset.from_dict(loaded_data)

    print(f"数据集名称: {dataset.name}", f"数据集描述: {dataset.description}", sep="\n")
    print(f"数据集任务数量: {len(dataset.tasks)}")
    return dataset


software_dev_7_path = DATASETS_PATH / "software_dev_7.yaml"
software_dev_7 = load_dataset(software_dev_7_path)
