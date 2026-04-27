import logging
from pathlib import Path

import yaml
from deepagents import CompiledSubAgent, SubAgentMiddleware, create_deep_agent
from deepagents.backends import CompositeBackend
from deepagents.middleware import FilesystemMiddleware, SkillsMiddleware
from deepagents.middleware.subagents import SubAgent
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

from src.Tools import get_current_time, internet_search
from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.assign import AssignMiddleware
from src.paths import AGENTBAY_SYSTEM_PROMPTS_FILES, LOCAL_PROJECTS_WAREHOUSE_FOR_REMOTE_TASK_RESULT, USER_SOFTWARE_DEV_TASKS_PATH
from src.remote_dev_team.agent_config import LEADER_SKILL_PATH, ENGINEER_SKILL_PATH, QA_ENGINEER_SKILL_PATH, \
    my_composite_backend_routes, MY_WRITE_FILE_TOOL_DESCRIPTION
from src.remote_dev_team.shared_middleware import todo_list_middleware, summarization_middleware, retry_middleware
from src.utils.my_sandbox import MySandbox
from src.utils.roles_prompt_manager import get_system_prompt

logger = logging.getLogger(__name__)


# ========== TraceableTask 数据类 ==========

from dataclasses import dataclass
from src.utils.datasets import Task


@dataclass
class TraceableTask:
    """可追踪的任务对象，用于保存任务启动记录。"""
    thread_id: str
    task_context_box_id: str
    task: Task

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建对象(用于 YAML 反序列化)"""
        return cls(
            thread_id=data['thread_id'],
            task_context_box_id=data['task_context_box_id'],
            task=Task.from_dict(data['task'])
        )

    def to_dict(self):
        """将对象转换为字典(用于 YAML 序列化)"""
        return {
            'thread_id': self.thread_id,
            'task_context_box_id': self.task_context_box_id,
            'task': self.task.to_dict()
        }


class AgentBayBasedDevTeam:
    """基于 AgentBay 的自动化软件开发团队。
    
    该类负责：
    1. 基于传入的 sandbox 创建composite backend，之后创建统一的文件系统中间件
    2. 使用这些中间件创建所有团队专家（Product Manager、Architect、Project Manager、Engineer、QA Engineer）
    3. 创建 Team Leader，并将所有专家注册到 AssignMiddleware
    4. 暴露 leader 的所有调用方法（invoke、stream 等）
    
    所有团队成员共享同一个 composite backend，智能体只能感知到一个文件系统，
    但实际上，不同的文件操作会被路由到不同后端（项目操作路由到沙盒后端，技能读取、记忆存取操作路由到本地文件系统后端）。
    """

    def __init__(self, sandbox: MySandbox,
                 projects_warehouse_for_remote_task_result: Path = LOCAL_PROJECTS_WAREHOUSE_FOR_REMOTE_TASK_RESULT):
        """初始化开发团队。
        
        Args:
            sandbox: 沙盒实例，充当每次任务的项目空间
            projects_warehouse_for_remote_task_result: 本地项目仓库根目录，用于保存任务成果物。默认为 PROJECTS_WAREHOUSE_BY_AGENTS
        """
        logger.info(f"初始化 AgentBayBasedDevTeam")
        logger.debug(f"获得的沙盒实例: {sandbox}")
        if not sandbox.task_name:
            raise ValueError("AgentBayBasedDevTeam 实例所用的sandbox必须有一个软件开发任务")

        logger.debug(f"本地用于保存任务成果物的项目仓库路径: {projects_warehouse_for_remote_task_result}")

        self.sandbox = sandbox
        self.composite_backend = CompositeBackend(
            default=self.sandbox,
            routes=my_composite_backend_routes,
        )
        self._local_projects_warehouse = projects_warehouse_for_remote_task_result
        self._llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]
        logger.info(f"使用模型: {'minimax-m2.7' if settings.USE_PAID_LLM_API else 'gpt-5-mini'}")

        # 创建团队
        logger.info("开始创建团队专家...")
        self._filesystem_middleware = None
        self.experts = self._create_experts()
        logger.info(f"已创建 {len(self.experts)} 个专家: {[expert['name'] for expert in self.experts]}")

        logger.info("开始创建 Team Leader...")
        self.leader = self._create_leader()
        logger.info("✅ AgentBayBasedDevTeam 初始化完成")

    def _get_filesystem_middleware(self):
        """创建基于 composite backend 的文件系统中间件，可共享"""
        if self._filesystem_middleware is not None:
            return self._filesystem_middleware

        logger.debug("创建文件系统中间件")
        logger.debug("此处基于一个组合式后端CompositeBackend来创建文件系统中间件")
        self._filesystem_middleware = FilesystemMiddleware(
            backend=self.composite_backend,
            custom_tool_descriptions={
                "write_file": MY_WRITE_FILE_TOOL_DESCRIPTION
            })
        return self._filesystem_middleware

    def _create_skills_middleware(self, sources: list[str]):
        """创建基于 composite backend 的技能中间件，不可共享
        
        Args:
            sources: 技能路径列表，如 [LEADER_SKILL_PATH] 或 [ENGINEER_SKILL_PATH]
        """
        logger.debug(f"创建技能中间件，来源: {sources}")
        return SkillsMiddleware(backend=self.composite_backend, sources=sources)

    def _create_subagent_middleware(self, skills_middleware):
        """创建基于 composite backend 的子智能体中间件，用于作为主智能体的分身，不可共享"""
        # 通用子智能体描述
        general_purpose_description = (
            "General-purpose agent for researching complex questions, "
            "searching for files and content, and executing multi-step tasks. "
            "When you are searching for a keyword or file and are not confident "
            "that you will find the right match in the first few tries, "
            "use this agent to perform the search for you. "
            "This agent has access to all tools as the main agent."
        )

        general_purpose_subagent: SubAgent = {
            "model": self._llm,
            "tools": [],
            "name": "general-purpose",
            "description": general_purpose_description,
            "system_prompt": "In order to complete the objective that the user asks of you, you have access to a number of standard tools.",
            "middleware": [
                self._get_filesystem_middleware(),
                skills_middleware,
                summarization_middleware,
                retry_middleware,
            ],
        }

        return SubAgentMiddleware(backend=self.composite_backend, subagents=[general_purpose_subagent])

    def _create_deep_agent_expert(
            self,
            role_name: str,
            expert_name: str,
            expert_description: str,
    ) -> CompiledSubAgent:
        """创建基于deep agent的专家智能体。
        
        Args:
            role_name: 角色名称（用于获取系统提示词，如 "product_manager", "architect", "project_manager"）
            expert_name: assign主调智能体可见的专家名称（如 "Alice", "Bob", "Cindy"）
            expert_description: 专家描述
        
        Returns:
            team_expert
        """
        logger.debug(f"创建专家 {expert_name} ({role_name})")
        sys_prompt = get_system_prompt(role_name, prompts_dir=AGENTBAY_SYSTEM_PROMPTS_FILES)

        graph = create_deep_agent(
            model=self._llm,
            tools=[get_current_time, internet_search],
            system_prompt=sys_prompt,
            middleware=[retry_middleware],
            checkpointer=True,
            backend=self.composite_backend,
            name=f"{expert_name}_{role_name.title().replace('_', '')}"  # langchain在给AIMessage添加name属性时使用
        )

        logger.debug(f"专家 {expert_name} 创建完成")
        return CompiledSubAgent(
            name=expert_name,
            description=expert_description,
            runnable=graph,
        )

    def _create_product_manager(self):
        """创建产品经理专家"""
        return self._create_deep_agent_expert(
            role_name="product_manager",
            expert_name="Alice",
            expert_description="一名产品经理，擅长根据需求描述，交付产品需求文档。",
        )

    def _create_architect(self):
        """创建架构师专家"""
        return self._create_deep_agent_expert(
            role_name="architect",
            expert_name="Bob",
            expert_description="一名架构师，擅长根据产品需求文档，交付软件架构设计文档。",
        )

    def _create_project_manager(self):
        """创建项目经理专家"""
        return self._create_deep_agent_expert(
            role_name="project_manager",
            expert_name="Cindy",
            expert_description="一名项目经理，擅长根据软件架构设计文档，交付软件详细设计文档。",
        )

    def _create_engineer(self):
        """创建工程师专家（需要记忆保持）"""
        logger.debug("创建工程师 David")
        skills_middleware = self._create_skills_middleware([ENGINEER_SKILL_PATH])
        fs_middleware = self._get_filesystem_middleware()
        subagent_middleware = self._create_subagent_middleware(skills_middleware)

        sys_prompt = get_system_prompt("engineer", prompts_dir=AGENTBAY_SYSTEM_PROMPTS_FILES)

        agent = create_agent(
            model=self._llm,
            tools=[get_current_time],
            system_prompt=sys_prompt,
            middleware=[
                todo_list_middleware,
                skills_middleware,
                fs_middleware,
                subagent_middleware,
                summarization_middleware,
                retry_middleware,
            ],
            checkpointer=True,
            name="David_Engineer",
        )

        logger.debug("工程师 David 创建完成")
        return CompiledSubAgent(
            name="David",
            description="一名软件工程师，可根据明确的编码任务需求，交付功能性代码文件和测试代码文件，同时完成代码调试、单元测试、集成测试。",
            runnable=agent,
        )

    def _create_QA_engineer(self):
        """创建QA工程师专家（需要记忆保持）"""
        logger.debug("创建QA工程师 Eva")
        skills_middleware = self._create_skills_middleware([QA_ENGINEER_SKILL_PATH])
        fs_middleware = self._get_filesystem_middleware()
        subagent_middleware = self._create_subagent_middleware(skills_middleware)

        sys_prompt = get_system_prompt("QA_engineer", prompts_dir=AGENTBAY_SYSTEM_PROMPTS_FILES)

        agent = create_agent(
            model=self._llm,
            tools=[get_current_time],
            system_prompt=sys_prompt,
            middleware=[
                todo_list_middleware,
                skills_middleware,
                fs_middleware,
                subagent_middleware,
                summarization_middleware,
                retry_middleware,
            ],
            checkpointer=True,
            name="Eva_QA_Engineer",
        )

        logger.debug("QA工程师 Eva 创建完成")
        return CompiledSubAgent(
            name="Eva",
            description="一名软件测试员，可对指定的软件项目进行系统测试，交付一份系统测试报告。",
            runnable=agent,
        )

    def _create_experts(self):
        """创建所有团队专家"""
        logger.info("开始逐个创建专家...")
        experts = [
            self._create_product_manager(),
            self._create_architect(),
            self._create_project_manager(),
            self._create_engineer(),
            self._create_QA_engineer(),
        ]
        logger.info(f"所有专家创建完成，共 {len(experts)} 个")
        return experts

    def _create_leader(self):
        """创建团队 Leader"""
        logger.info("开始创建 Team Leader...")

        # 创建 Leader 专属的 middleware
        logger.debug("创建 Leader 的文件系统中间件")
        fs_middleware = self._get_filesystem_middleware()

        logger.debug("创建 Leader 的技能中间件")
        skills_middleware = self._create_skills_middleware([LEADER_SKILL_PATH])

        logger.debug("创建 Leader 的子智能体中间件")
        subagent_middleware = self._create_subagent_middleware(skills_middleware)

        logger.debug(f"创建 AssignMiddleware，注册 {len(self.experts)} 个专家")
        assign_middleware = AssignMiddleware(experts=self.experts)

        # 获取系统提示词
        logger.debug("加载 Team Leader 系统提示词")
        leader_sys_prompt = get_system_prompt("team_leader", prompts_dir=AGENTBAY_SYSTEM_PROMPTS_FILES)

        # 创建 Leader agent
        logger.info("创建 Leader Agent (包含多个中间件)...")
        leader = create_agent(
            model=self._llm,
            tools=[get_current_time],
            system_prompt=leader_sys_prompt,
            middleware=[
                todo_list_middleware,  # 共享
                skills_middleware,  # 专属
                fs_middleware,  # 专属
                subagent_middleware,  # 专属
                assign_middleware,  # 专属（包含专属 experts）
                summarization_middleware,  # 共享
                retry_middleware,  # 共享
            ],
            checkpointer=MemorySaver(),
            name="Tim_Leader",
        )

        logger.info("✅ Team Leader 创建完成")
        return leader

    # ========== 代理 Leader 的所有调用方法 ==========

    def invoke(self, input, config=None, **kwargs):
        """同步调用 leader"""
        return self.leader.invoke(input, config, **kwargs)

    def stream(self, input, config=None, stream_mode=None, subgraphs=False, version=None, **kwargs):
        """流式调用 leader"""
        return self.leader.stream(input, config=config, stream_mode=stream_mode, subgraphs=subgraphs, version=version,
                                  **kwargs)

    async def ainvoke(self, input, config=None, **kwargs):
        """异步调用 leader"""
        return await self.leader.ainvoke(input, config, **kwargs)

    async def astream(self, input, config=None, stream_mode=None, subgraphs=False, version=None, **kwargs):
        """异步流式调用 leader"""
        return self.leader.astream(input, config=config, stream_mode=stream_mode, subgraphs=subgraphs, version=version,
                                   **kwargs)

    def download_and_cleanup(self, success: bool = True):
        """先下载成果物到本地，后清理会话资源。
            
        Args:
            success: 任务是否成功完成，用于日志记录
        """
        logger.info(f"开始清理和下载 (success={success})")

        # 1. 下载成果物
        if self.sandbox.task_name:
            task_name = self.sandbox.task_name
            local_dir = self._local_projects_warehouse / task_name  # ⭐ 使用配置的仓库路径
            logger.info(f"下载任务成果物到: {local_dir}")
            try:
                self.sandbox.download_task_artifacts(local_dir)
                logger.info(f"成果物下载完成")
            except Exception as e:
                logger.error(f"成果物下载失败: {e}", exc_info=True)
                logger.warning("跳过下载，继续清理会话")
        else:
            logger.warning("sandbox.task_name 为空，跳过下载")

        # 2. 清理云端会话（无论下载是否成功都要执行）
        logger.info("清理云端会话...")
        try:
            self.sandbox.cleanup()
            logger.info("清理完成")
        except Exception as e:
            logger.error(f"清理会话失败: {e}", exc_info=True)
            logger.warning("会话可能已过期，跳过清理")

    def save_traceable_task_to_file(self, thread_id: str, task: Task):
        """保存任务启动记录到 YAML 文件。
        
        ⭐ 优化：如果文件已存在，则跳过写入，避免重复保存
        
        Args:
            thread_id: 线程ID
            task: 任务对象
        """
        # 从 sandbox 获取 task_context_box_id
        task_context_box_id = self.sandbox.task_context_box_id
        if not task_context_box_id:
            logger.warning("⚠️ sandbox.task_context_box_id 为空，无法保存任务记录")
            return
        
        # 创建 TraceableTask 实例
        traceable_task = TraceableTask(
            thread_id=thread_id,
            task_context_box_id=task_context_box_id,
            task=task
        )
        
        # 构造文件路径
        task_file_path = USER_SOFTWARE_DEV_TASKS_PATH / f"{traceable_task.task.name}.yaml"

        # ⭐ 关键优化：检查文件是否已存在
        if task_file_path.exists():
            logger.info(f"⏭️ 任务启动记录已存在，跳过保存: {task_file_path}")
            return

        # 确保父目录存在
        task_file_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存到 YAML 文件
        with open(task_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(traceable_task.to_dict(), f, allow_unicode=True)
            logger.info(f"✅ 任务启动记录已保存: {task_file_path}")
