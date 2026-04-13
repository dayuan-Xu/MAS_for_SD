from operator import add
from typing import TypedDict, Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from langgraph.runtime import Runtime


# 不同智能体应该具备的结构化输出
class SystemDesignDoc(TypedDict):
    """
    System design doc as a part of Solution.
    """
    pass

class RequirementDescriptionDoc(TypedDict):
    """
    Requirement description doc as a part of Solution.
    """
    pass

class DetailedDesignDoc(TypedDict):
    """
    Detailed design doc as a part of Solution.
    """
    pass

class StandardCodeResult(TypedDict):
    """
    Standard code result as a part of Solution.
    """
    code: str
    version: str

class TeamSpace(TypedDict):
    boss_requirement: str
    dev_stages: list[str]                                   # 由团队leader分析原始需求，选择性注入的一些为了满足需求而必不可少的开发阶段。
    messages: Annotated[list[AnyMessage], add_messages]     # 团队空间中的消息，消息内容有结构化要求。
    requirements_description_doc: RequirementDescriptionDoc
    system_design_doc: SystemDesignDoc
    detailed_design_doc: DetailedDesignDoc
    codes: Annotated[list[StandardCodeResult], add]
    manual: str

class ContextSchema(TypedDict):
    """
    Context schema for SD Graph.
    """
    main_model: str     # 完成软件开发主要阶段的base model
    engineer_model: str # 编码人员的base model
    api_key: str
    base_url: str


def requirement_analysis(state: TeamSpace, runtime: Runtime[ContextSchema]):
    # 基于用户输入完成需求澄清、竞品分析、需求列表说明
    pass

def system_design(state: TeamSpace, runtime: Runtime[ContextSchema]):
    # 架构师基于需求分析生成系统设计，包括技术选择、系统模块图
    pass

def task_assignment(state: TeamSpace, runtime: Runtime[ContextSchema]):
    # 基于系统设计生成详细设计：包括数据库定义、后端接口详细定义、前端界面详细定义；同时负责给编码阶段的多位编码人员分配具体任务
    pass

def progress_monitor_and_log(state: TeamSpace, runtime: Runtime[ContextSchema]):
    # 项目经理持续监听团队空间中的消息，捕捉代码进度消息，记录项目进展，并填写报告。
    pass

def code_generation(state: TeamSpace, runtime: Runtime[ContextSchema]):
    # 基于任务详情+代码执行反馈 完成指定的代码生成、调试任务，该节点函数可以多个实例并行运行
    # 该阶段内可以同时调用多个编码人员智能体，并为他们分配不同的任务，每个编码人员智能体具备自己的代码执行工具，从而具备迭代式编码能力。
    # 项目经理持续监听团队空间中的消息，捕捉代码进度消息，记录项目进展，并填写报告。
    pass

def soft_evaluation(state: TeamSpace, runtime: Runtime[ContextSchema]):
    # 从系统测试角度评估生成的软件，并返回评估结果，该阶段可以调用具备代码执行工具的系统测试员智能体
    # 系统测试结果可以反馈给项目经理，由项目经理生成项目总结、项目开发经验报告。
    pass

def manual_generation(state: TeamSpace, runtime: Runtime[ContextSchema]):
    # 项目经理基于现有解决方案生成软件使用手册
    pass

