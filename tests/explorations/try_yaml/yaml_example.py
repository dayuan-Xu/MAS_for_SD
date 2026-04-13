"""
YAML 数据存储和加载示例
演示如何将 Python 对象序列化为 YAML 文件,以及从 YAML 文件加载数据
"""

import yaml
from dataclasses import dataclass, asdict
from typing import List, Optional
from pathlib import Path


# ==================== 示例 1: 基础数据类型 ====================

def basic_yaml_operations():
    """基础的 YAML 读写操作"""
    
    # Python 字典数据
    config_data = {
        "database": {
            "host": "localhost",
            "port": 5432,
            "username": "admin",
            "password": "secret123"
        },
        "server": {
            "host": "0.0.0.0",
            "port": 8080,
            "debug": True
        },
        "features": ["login", "search", "upload"]
    }
    
    # 保存到 YAML 文件
    yaml_file = "config.yaml"
    with open(yaml_file, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
    
    print(f"✓ 数据已保存到 {yaml_file}")
    
    # 从 YAML 文件加载
    with open(yaml_file, 'r', encoding='utf-8') as f:
        loaded_data = yaml.safe_load(f)
    
    print(f"✓ 从 {yaml_file} 加载数据:")
    print(loaded_data)
    return loaded_data


# ==================== 示例 2: 使用数据类(DataClass) ====================

@dataclass
class User:
    """用户数据类"""
    name: str
    age: int
    email: str
    skills: List[str] = None
    
    def __post_init__(self):
        if self.skills is None:
            self.skills = []


@dataclass
class Project:
    """项目数据类"""
    name: str
    owner: User
    members: List[User] = None
    status: str = "active"
    
    def __post_init__(self):
        if self.members is None:
            self.members = []
    
    def to_dict(self):
        """转换为字典(用于 YAML 序列化)"""
        return {
            'name': self.name,
            'owner': asdict(self.owner),
            'members': [asdict(m) for m in self.members],
            'status': self.status
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建对象(用于 YAML 反序列化)"""
        owner = User(**data['owner'])
        members = [User(**m) for m in data.get('members', [])]
        return cls(
            name=data['name'],
            owner=owner,
            members=members,
            status=data.get('status', 'active')
        )


def dataclass_yaml_example():
    """使用数据类的 YAML 操作示例"""
    
    # 创建对象
    owner = User(name="张三", age=30, email="zhangsan@example.com", 
                 skills=["Python", "JavaScript"])
    member1 = User(name="李四", age=25, email="lisi@example.com", 
                   skills=["Java", "Go"])
    member2 = User(name="王五", age=28, email="wangwu@example.com", 
                   skills=["Python", "C++"])
    
    project = Project(
        name="AI助手项目",
        owner=owner,
        members=[member1, member2],
        status="in_progress"
    )
    
    # 保存为 YAML
    yaml_file = "project.yaml"
    with open(yaml_file, 'w', encoding='utf-8') as f:
        yaml.dump(project.to_dict(), f, allow_unicode=True, 
                  default_flow_style=False, sort_keys=False)
    
    print(f"\n✓ 项目数据已保存到 {yaml_file}")
    
    # 从 YAML 加载并重建对象
    with open(yaml_file, 'r', encoding='utf-8') as f:
        loaded_data = yaml.safe_load(f)
    
    loaded_project = Project.from_dict(loaded_data)
    
    print(f"\n✓ 加载的项目信息:")
    print(f"  项目名称: {loaded_project.name}")
    print(f"  负责人: {loaded_project.owner.name}")
    print(f"  成员数量: {len(loaded_project.members)}")
    print(f"  状态: {loaded_project.status}")
    
    return loaded_project


# ==================== 示例 3: 自定义 YAML 表示 ====================

class CustomYAMLRepr:
    """支持自定义 YAML 表示的类"""
    
    def __init__(self, title: str, content: str, tags: List[str] = None):
        self.title = title
        self.content = content
        self.tags = tags or []
    
    def to_yaml_dict(self):
        """转换为 YAML 友好的字典"""
        return {
            'title': self.title,
            'content': self.content,
            'tags': self.tags
        }
    
    @classmethod
    def from_yaml_dict(cls, data: dict):
        """从 YAML 字典创建对象"""
        return cls(
            title=data['title'],
            content=data['content'],
            tags=data.get('tags', [])
        )
    
    def __repr__(self):
        return f"CustomYAMLRepr(title='{self.title}', tags={self.tags})"


def custom_yaml_representation():
    """自定义 YAML 表示示例"""
    
    articles = [
        CustomYAMLRepr("Python入门", "Python是一种...", ["编程", "教程"]),
        CustomYAMLRepr("YAML详解", "YAML是...", ["配置", "数据格式"]),
    ]
    
    # 保存
    yaml_file = "articles.yaml"
    articles_data = [a.to_yaml_dict() for a in articles]
    
    with open(yaml_file, 'w', encoding='utf-8') as f:
        yaml.dump(articles_data, f, allow_unicode=True, 
                  default_flow_style=False)
    
    print(f"\n✓ 文章数据已保存到 {yaml_file}")
    
    # 加载
    with open(yaml_file, 'r', encoding='utf-8') as f:
        loaded_articles = yaml.safe_load(f)
    
    restored_articles = [CustomYAMLRepr.from_yaml_dict(a) for a in loaded_articles]
    
    print(f"\n✓ 加载了 {len(restored_articles)} 篇文章:")
    for article in restored_articles:
        print(f"  - {article.title}: {article.tags}")
    
    return restored_articles


# ==================== 示例 4: 安全注意事项 ====================

def security_considerations():
    """YAML 安全加载的注意事项"""
    
    # ⚠️ 不安全的方式 - 可能执行任意 Python 代码
    # yaml.load(data, Loader=yaml.FullLoader)  # 不推荐用于不可信数据
    
    # ✓ 安全的方式 - 只加载基本数据类型
    safe_yaml = """
name: test
value: 123
items:
  - item1
  - item2
"""
    
    # 推荐使用 safe_load
    data = yaml.safe_load(safe_yaml)
    print(f"\n✓ 安全加载结果: {data}")
    
    # safe_load 只能处理:
    # - 字典(dict)
    # - 列表(list)
    # - 字符串(str)
    # - 数字(int, float)
    # - 布尔值(bool)
    # - None


# ==================== 主函数 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("YAML 数据存储和加载完整示例")
    print("=" * 60)
    
    # 示例 1: 基础操作
    print("\n【示例 1】基础 YAML 操作")
    print("-" * 60)
    basic_yaml_operations()
    
    # 示例 2: 数据类
    print("\n【示例 2】使用数据类(DataClass)")
    print("-" * 60)
    dataclass_yaml_example()
    
    # 示例 3: 自定义表示
    print("\n【示例 3】自定义 YAML 表示")
    print("-" * 60)
    custom_yaml_representation()
    
    # 示例 4: 安全考虑
    print("\n【示例 4】安全注意事项")
    print("-" * 60)
    security_considerations()
    
    print("\n" + "=" * 60)
    print("所有示例完成!查看生成的 YAML 文件了解格式。")
    print("=" * 60)
