import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal

import yaml
from deepagents import SubAgentMiddleware
from deepagents.backends import CompositeBackend
from deepagents.middleware import FilesystemMiddleware
from deepagents.middleware.subagents import SubAgent
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph

from src.Tools import get_current_time, internet_search
from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.agent_activity_monitor import AgentActivityMonitor
from src.custom_middleware.message import CommunicateMiddleware, create_compiled_expert_agent
from src.custom_middleware.my_skills import MySkillsMiddleware
from src.custom_middleware.prompt_inject import SystemPromptInjectMiddleware
from src.dev_team.my_backend import LinuxSandboxBackend
from src.dev_team.shared_middles import todo_list_middleware, summarization_middleware, \
    model_retry_middleware, tool_retry_middleware
from src.dev_team.team_config import LEADER_SKILL_PATH, ENGINEER_SKILL_PATH, QA_ENGINEER_SKILL_PATH, \
    MY_COMPOSITE_BACKEND_ROUTES, MY_FILESYSTEM_MIDDLEWARE_SYSTEM_PROMPT, \
    MY_WRITE_FILE_TOOL_DESCRIPTION, AGENTBAY_MCP_SERVER_NAME, BUILDER_SKILL_PATH, EVALUATOR_SKILL_PATH, \
    SHARED_INFORMATION_AFTER_SYSTEM_PROMPT, MY_EXECUTE_TOOL_DESCRIPTION
from src.paths import PROMPTS_DIR, LOCAL_WAREHOUSE_PATH, \
    REGISTERED_TASKS_PATH
from src.utils.datasets import Task, TraceableTask
from src.utils.mcp import get_excluded_tools, load_wuying_mcp_tools
from src.utils.roles_prompt_manager import get_system_prompt

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """智能体配置"""
    role: str  # 角色名称（用于获取系统提示词）
    name: str  # 智能体显示名称
    skill_paths: list[str] = field(default_factory=list)  # 技能路径列表（文件系统基于Backend）
    mcp_tools: list = field(default_factory=list)  # MCP工具
    experts: list = field(default_factory=list)  # 专家列表（用于assign）
    use_subagent: bool = True  # 是否使用子智能体中间件
    base_tools: list = None  # 基础工具（默认 [get_current_time]）
    log_activity: bool = False  # 是否启用活动监控

    def __post_init__(self):
        if self.base_tools is None:
            self.base_tools = [get_current_time]


class AgentTeam:
    """基于 AgentBay 的自动化软件开发团队。"""

    # Team 对象完整初始化的入口
    @classmethod
    async def create_with_agentbay_mcp(cls, sandbox: LinuxSandboxBackend,
                                       local_warehouse: Path = LOCAL_WAREHOUSE_PATH):
        """异步工厂方法：创建带有 Wuying AgentBay MCP 工具的 AgentBayBasedDevTeamV2 实例。

        这是推荐的初始化方式，会自动加载 Wuying AgentBay MCP 工具并传递给工程师和 QA 工程师。

        Args:
            sandbox: 沙盒实例
            local_warehouse: 本地项目仓库路径

        Returns:
            AgentTeam: 配置好 MCP 工具的团队实例

        """
        # 1. 创建实例
        instance = cls(sandbox, local_warehouse)

        # 2. 初始化异步资源
        await instance._initialize_async_resources()

        # 3. 创建所有智能体
        instance._create_all_agents()

        logger.info("✅ AgentTeam 初始化完成")
        logger.info(f"{instance}")
        return instance

    def __init__(self, sandbox: LinuxSandboxBackend,
                 local_warehouse_path: Path = LOCAL_WAREHOUSE_PATH,
                 team_type: Literal["simple", "complex"] = "simple"):
        """初始化开发团队 V2（同步资源初始化）。
        
        ⚠️ 注意：此方法仅初始化同步资源（中间件、backend、LLM等），不会创建 checkpointer 和智能体。
        请使用异步工厂方法 create_with_agentbay_mcp() 进行完整初始化。
        
        Args:
            sandbox: 沙盒实例，充当每次任务的项目空间
            local_warehouse_path: 本地项目仓库根目录，用于保存任务成果物。
            team_type: 团队类型
        """
        logger.info("开始同步初始化 AgentTeam的同步资源")

        # 验证 sandbox
        if not sandbox.task_name:
            raise ValueError("AgentTeam 实例所用的sandbox必须有一个软件开发任务")
        if not sandbox.sandbox_id:
            raise ValueError("AgentTeam 使用的AgentBay MCP 工具必须依赖传入的sandbox的sandbox_id")

        # 基本属性
        self.sandbox = sandbox
        self.sandbox_id = sandbox.sandbox_id
        self.sandbox_type = sandbox.sandbox_type
        self.task_working_dir = sandbox.task_context_box_mount_path  # 本次开发任务的云端项目空间的文件路径
        self.team_type = team_type
        self.local_warehouse_path = local_warehouse_path

        # 1. 设置 LLM
        self._llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]
        logger.info(f"智能体开发团队使用的模型: {self._llm.model_name}，温度: {self._llm.temperature}")

        # 2. 创建 injected prompt middleware
        injected_prompt = SHARED_INFORMATION_AFTER_SYSTEM_PROMPT.format(sandbox_id=self.sandbox_id)
        self.injected_prompt_middleware_1 = SystemPromptInjectMiddleware(prompt=injected_prompt)

        # 3. 创建 composite backend
        self.composite_backend = CompositeBackend(
            default=self.sandbox,
            routes=MY_COMPOSITE_BACKEND_ROUTES[f"{self.sandbox_type}"],
        )
        # 4. 创建文件系统中间件
        logger.debug("开始创建共享的文件系统中间件...")
        self._shared_filesystem_middleware = FilesystemMiddleware(
            backend=self.composite_backend,
            system_prompt=MY_FILESYSTEM_MIDDLEWARE_SYSTEM_PROMPT.format(sandbox_type=self.sandbox_type),
            custom_tool_descriptions={
                "write_file": MY_WRITE_FILE_TOOL_DESCRIPTION,
                "execute": MY_EXECUTE_TOOL_DESCRIPTION,
            },
            max_execute_timeout=3600,
            # Maximum allowed value in seconds for per-command timeout overrides on the execute tool.
        )
        logger.debug(f"成功创建共享的文件系统中间件，该文件系统中间件基于{self.sandbox_type}镜像")

        # 5. 设置技能路径
        self.leader_skill_path = LEADER_SKILL_PATH[f"{self.sandbox_type}"]
        self.engineer_skill_path = ENGINEER_SKILL_PATH[f"{self.sandbox_type}"]
        self.QA_engineer_skill_path = QA_ENGINEER_SKILL_PATH[f"{self.sandbox_type}"]

        self.builder_skill_path = BUILDER_SKILL_PATH[f"{self.sandbox_type}"]
        self.evaluator_skill_path = EVALUATOR_SKILL_PATH[f"{self.sandbox_type}"]

        # 6. 设置时间戳和本地存储路径
        self._dev_start_timestamp = datetime.now().strftime("%m%d_%H%M")
        logger.info(f"🕒 开发团队启动时间戳: {self._dev_start_timestamp}")
        self.local_dir_for_task_products = local_warehouse_path / sandbox.task_name / self._dev_start_timestamp

        # 延迟初始化的属性
        self.mcp_tools = []
        self._checkpointer = None

        self.product_manager = None
        self.architect = None
        self.project_manager = None
        self.engineer = None
        self.QA_engineer = None
        self.compiled_expert_agents = None
        self.leader = None

        self.planner = None
        self.builder = None
        self.evaluator = None
        self.role_to_agent = None

        logger.info("✅ 同步资源初始化完成")

    async def _initialize_async_resources(self):
        """初始化异步资源：MCP tools 和 checkpointer。"""
        logger.info("开始初始化异步资源 mcp tools、checkpointer...")

        # 1. 异步加载 MCP 工具
        excluded_tools = get_excluded_tools()
        excluded_tools = {AGENTBAY_MCP_SERVER_NAME + "_" + item for item in excluded_tools}
        mcp_tools = await load_wuying_mcp_tools(self.sandbox.image_id, mcp_tool_name_prefix=True,
                                                excluded_tools=excluded_tools)
        self.mcp_tools = mcp_tools  # 设置 MCP 工具

        # 2. 初始化 checkpointer
        if settings.USE_POSTGRES_CHECKPOINTER:
            from src.config.database import get_async_connection_pool

            # 获取异步连接池（单例）
            pool = get_async_connection_pool()

            # 显式打开连接池（避免弃用警告）
            await pool.open()

            # 直接使用连接池创建 checkpointer（推荐方式）
            self._checkpointer = AsyncPostgresSaver(pool)
            await self._checkpointer.setup()
            logger.info("✅ AsyncPostgres checkpointer 已初始化")
        else:
            self._checkpointer = InMemorySaver()
            logger.info("✅ Memory checkpointer 已初始化")

    def _create_all_agents(self):
        """创建所有智能体"""
        # 创建团队
        logger.info("开始创建团队专家...")
        self.product_manager = self._create_product_manager()
        self.architect = self._create_architect()
        self.project_manager = self._create_project_manager()

        self.engineer = self._create_engineer(name="David", mcp_tools=self.mcp_tools)
        self.QA_engineer = self._create_QA_engineer(name="Eva", mcp_tools=self.mcp_tools)

        self.leader = self._create_leader(mcp_tools=self.mcp_tools)
        logger.info("✅ 复杂6人团队创建完成")

        # 创建简化版三人团队（Planner/Builder/Evaluator）
        logger.info("开始创建简化版三人团队...")
        self.evaluator = self._create_evaluator(mcp_tools=self.mcp_tools)
        self.builder = self._create_builder(mcp_tools=self.mcp_tools, log_agent_activity=True)
        self.planner = self._create_planner()
        logger.info("✅ 简单3人团队创建完成")

        self.role_to_agent = {
            "product_manager": self.product_manager,
            "architect": self.architect,
            "project_manager": self.project_manager,
            "engineer": self.engineer,
            "QA_engineer": self.QA_engineer,
            "leader": self.leader,
            "planner": self.planner,
            "builder": self.builder,
            "evaluator": self.evaluator
        }

        logger.info("✅ 所有智能体创建完成")

    def __str__(self):
        return ("AgentTeam(\n"
                f"      sandbox={self.sandbox},\n"
                f"      sandbox_id={self.sandbox_id},\n"
                f"      sandbox_type={self.sandbox_type}\n"
                f"      team_type={self.team_type}"
                )

    def _create_skills_middleware(self, sources: list[str]):
        """创建基于 composite backend 的技能中间件，不可在多个智能体间共享
        
        Args:
            sources: 技能路径列表，如 [LEADER_SKILL_PATH] 或 [ENGINEER_SKILL_PATH]
        """
        logger.debug(f"创建技能中间件，来源: {sources}")
        return MySkillsMiddleware(backend=self.composite_backend, sources=sources)

    def _build_agent_middlewares(self, config: AgentConfig, skills_middleware=None, subagent_middleware=None,
                                 communicate_middleware=None):
        """构建智能体中间件列表
        
        Args:
            config: 智能体配置
            skills_middleware: 技能中间件（可选）
            subagent_middleware: 子智能体中间件（可选）
            communicate_middleware: 分配中间件（可选）
        
        Returns:
            list: 中间件列表
        """
        middlewares = [
            self.injected_prompt_middleware_1,
            todo_list_middleware,
            self._shared_filesystem_middleware]

        # 添加专属中间件
        if skills_middleware:
            middlewares.append(skills_middleware)

        if subagent_middleware:
            middlewares.append(subagent_middleware)

        if communicate_middleware:
            middlewares.append(communicate_middleware)

        # 添加共享中间件
        middlewares.extend([
            summarization_middleware,
            tool_retry_middleware,
            model_retry_middleware,
        ])

        # 可选：添加活动监控
        if config.log_activity:
            logger.info(f"对智能体 {config.name} (身份：{config.role}) 启用智能体活动监控日志")
            middlewares.insert(0, AgentActivityMonitor(agent_name=config.name))

        return middlewares

    def _create_agent_from_config(self, config: AgentConfig):
        """从配置创建智能体（统一入口）
        
        Args:
            config: 智能体配置对象
        
        Returns:
            CompiledStateGraph
        """
        logger.debug(f"开始创建智能体：{config.name} (身份：{config.role})")

        # 1. 获取系统提示词
        sys_prompt = get_system_prompt(config.role, prompts_dir=PROMPTS_DIR)

        # 2. 准备工具
        tools = config.base_tools + config.mcp_tools if config.mcp_tools else []

        # 3. 创建技能中间件（如果需要）
        skills_middleware = None
        if config.skill_paths:
            skills_middleware = self._create_skills_middleware(config.skill_paths)

        # 4. 创建子智能体中间件（如果需要）
        subagent_middleware = None
        if config.use_subagent and skills_middleware:
            subagent_middleware = self._create_subagent_middleware(tools, skills_middleware)

        # 5. 创建分配中间件（如果有专家）
        communicate_middleware = None
        if config.experts:
            communicate_middleware = CommunicateMiddleware(user_name=config.name, experts=config.experts)

        # 6. 构建中间件列表
        middlewares = self._build_agent_middlewares(
            config,
            skills_middleware=skills_middleware,
            subagent_middleware=subagent_middleware,
            communicate_middleware=communicate_middleware
        )

        # # 7. 生成智能体名称
        # agent_name = f"{config.name}_{config.role.title().replace('_', '')}"
        agent_name = config.name

        # 8. 创建智能体
        agent = create_agent(
            model=self._llm,
            tools=tools,
            system_prompt=sys_prompt,
            middleware=middlewares,
            checkpointer=self._checkpointer,
            name=agent_name
        )

        logger.debug(f"智能体 {config.name} (身份：{config.role}) 创建完成")
        return agent

    def _create_subagent_middleware(self, tools, skills_middleware):
        """创建基于 composite backend 的子智能体中间件，用于作为主智能体的分身，不可共享"""
        if skills_middleware is None:
            raise ValueError("技能中间件对象不能为None")
        # 通用子智能体描述
        general_purpose_description = """
        General-purpose agent for researching complex questions, searching for files and content,
        and executing multi-step tasks. 
        When you are searching for a keyword or file and are not confident that you will find the right match in the first few tries,
        use this agent to perform the search for you. 
        This agent has access to all tools, skills as you can access, just think of it as your ephemeral clone."
        """

        general_purpose_subagent: SubAgent = {
            "model": self._llm,
            "tools": tools,
            "name": "general-purpose",
            "description": general_purpose_description,
            "system_prompt": "In order to complete the objective that the user asks of you, you have access to a number of standard tools.",
            "middleware": [
                self._shared_filesystem_middleware,
                skills_middleware,
                summarization_middleware,
                model_retry_middleware,
            ],
        }

        return SubAgentMiddleware(backend=self.composite_backend, subagents=[general_purpose_subagent])

    def _create_product_manager(self, *, name="Alice", log_agent_activity=False):
        """创建产品经理智能体"""
        config = AgentConfig(
            role="product_manager",
            name=name,
            use_subagent=False,
            base_tools=[get_current_time, internet_search],
            log_activity=log_agent_activity
        )
        return self._create_agent_from_config(config)

    def _create_architect(self, *, name="Bob", log_agent_activity=False):
        """创建架构师智能体"""
        config = AgentConfig(
            role="architect",
            name=name,
            use_subagent=False,
            base_tools=[get_current_time, internet_search],
            log_activity=log_agent_activity
        )
        return self._create_agent_from_config(config)

    def _create_project_manager(self, *, name="Cindy", log_agent_activity=False):
        """创建项目经理智能体"""
        config = AgentConfig(
            role="project_manager",
            name=name,
            use_subagent=False,
            base_tools=[get_current_time, internet_search],
            log_activity=log_agent_activity
        )
        return self._create_agent_from_config(config)

    def _create_engineer(self, *, role="engineer", name, mcp_tools: Optional[list] = None, log_agent_activity=False):
        """创建工程师智能体"""
        config = AgentConfig(
            role=role,
            name=name,
            skill_paths=[self.engineer_skill_path],
            mcp_tools=mcp_tools or [],
            log_activity=log_agent_activity
        )
        return self._create_agent_from_config(config)

    def _create_QA_engineer(self, *, role="QA_engineer", name, mcp_tools: Optional[list] = None,
                            log_agent_activity=False):
        """创建QA工程师智能体"""
        config = AgentConfig(
            role=role,
            name=name,
            skill_paths=[self.QA_engineer_skill_path],
            mcp_tools=mcp_tools or [],
            log_activity=log_agent_activity
        )
        return self._create_agent_from_config(config)

    def _create_leader(self, *, mcp_tools: Optional[list] = None, log_agent_activity=False):
        """创建团队 Leader"""
        logger.debug("开始创建 Team Leader...")

        compiled_expert_agents = [
            create_compiled_expert_agent(self.product_manager,
                                         "一个产品经理，擅长根据需求描述，交付产品需求文档。"),
            create_compiled_expert_agent(self.architect,
                                         "一个架构师，擅长根据产品需求文档，交付软件架构设计文档。"),
            create_compiled_expert_agent(self.project_manager,
                                         "一个项目经理，擅长根据软件架构设计文档，交付软件详细设计文档。"),
            create_compiled_expert_agent(self.engineer,
                                         "一名软件工程师，可根据明确的编码任务需求，交付功能性代码文件和测试代码文件，同时完成代码调试、单元测试、集成测试。"),
            create_compiled_expert_agent(self.QA_engineer,
                                         "一名软件测试员，可对指定的软件项目进行系统测试，交付一份系统测试报告。"),
        ]
        logger.info(
            f"已为Leader 创建 {len(compiled_expert_agents)} 个专家: {[expert['name'] for expert in compiled_expert_agents]}")

        config = AgentConfig(
            role="team_leader",
            name="Tim",
            skill_paths=[self.leader_skill_path],
            mcp_tools=mcp_tools or [],
            experts=compiled_expert_agents,
            log_activity=log_agent_activity
        )

        leader = self._create_agent_from_config(config)
        logger.info("✅ Team Leader 创建完成")
        return leader

    def _create_planner(self, *, mcp_tools: Optional[list] = None, log_agent_activity=False):
        """创建 Planner Alice（简化版三人团队）"""
        logger.debug("开始创建 Planner Alice...")

        # 创建 Builder 作为 Planner 的专家
        builder_expert = create_compiled_expert_agent(
            self.builder,
            "一名全栈开发工程师，负责功能点的迭代实现和质量保证。"
        )

        config = AgentConfig(
            role="Planner",
            name="Alice",
            mcp_tools=mcp_tools or [],
            experts=[builder_expert],
            use_subagent=False,  # Planner 不使用子智能体
            log_activity=log_agent_activity
        )

        planner = self._create_agent_from_config(config)
        logger.info("✅ Planner Alice 创建完成")
        return planner

    def _create_builder(self, *, mcp_tools: Optional[list] = None, log_agent_activity=False):
        """创建 Builder Bob（简化版三人团队）"""
        logger.debug("开始创建 Builder Bob...")

        # 创建 Evaluator 作为 Builder 的专家
        evaluator_expert = create_compiled_expert_agent(
            self.evaluator,
            "一名严格的质量保证工程师和技术评审专家。"
        )

        config = AgentConfig(
            role="Builder",
            name="Bob",
            skill_paths=[self.builder_skill_path],
            mcp_tools=mcp_tools or [],
            experts=[evaluator_expert],
            log_activity=log_agent_activity
        )

        builder = self._create_agent_from_config(config)
        logger.info("✅ Builder Bob 创建完成")
        return builder

    def _create_evaluator(self, *, mcp_tools: Optional[list] = None, log_agent_activity=False):
        """创建 Evaluator Eva（简化版三人团队）"""
        config = AgentConfig(
            role="Evaluator",
            name="Eva",
            skill_paths=[self.evaluator_skill_path],
            mcp_tools=mcp_tools or [],
            log_activity=log_agent_activity
        )

        evaluator = self._create_agent_from_config(config)
        logger.info("✅ Evaluator Eva 创建完成")
        return evaluator

    def download_and_cleanup(self, success: bool = True):
        """先下载成果物到本地，后清理会话资源。

        Args:
            success: 任务是否成功完成，用于日志记录
        """
        logger.info(f"开始成果物下载和会话资源清理 (success={success})")

        # 1. 下载成果物
        if self.sandbox.task_name:
            local_dir = self.local_dir_for_task_products
            logger.info(f"下载任务成果物到: {local_dir}")
            try:
                downloaded_count = self.sandbox.download_task_artifacts(local_dir)
                if not downloaded_count >= 1:
                    raise Exception(f"没有成功下载任何成果物文件：已下载成果物文件数 = {downloaded_count}")
                logger.info(f"成果物下载完成")
            except Exception as e:
                logger.error(f"成果物下载失败: {e}", exc_info=True)
                logger.warning("跳过下载，继续清理会话")
        else:
            logger.warning("sandbox.task_name 为空，跳过下载")

        # 2. 清理云端会话（无论下载是否成功都要执行）
        self.sandbox.delete_session()

    def save_traceable_task_to_file(self, thread_id: str, task: Task):
        """保存任务启动记录到 YAML 文件。

        Args:
            thread_id: 线程ID
            task: 任务对象
        """
        # 1 从 sandbox 获取 task_context_box_id
        task_context_box_id = self.sandbox.task_context_box_id
        if not task_context_box_id:
            logger.warning("⚠️ sandbox.task_context_box_id 为空，无法保存任务记录")
            return

        # 2 创建 TraceableTask 实例
        traceable_task = TraceableTask(
            thread_id=thread_id,
            task_context_box_id=task_context_box_id,
            task=task
        )

        # 3 构造文件路径
        task_file_path = REGISTERED_TASKS_PATH / f"{traceable_task.task.name}.yaml"

        # 4 确保父目录存在
        task_file_path.parent.mkdir(parents=True, exist_ok=True)

        # 5 保存到 YAML 文件
        with open(task_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(traceable_task.to_dict(), f, allow_unicode=True)
            logger.info(f"✅ 任务启动记录已保存: {task_file_path}")

    def green_or_brown(self, task: Task, force_using_new_thread: bool = False) -> str:
        """判断任务是否是绿色开发，如果是，则返回新的thread_id，
        否则若强制在旧存储盒基础上新开thread_id，则返回新的thread_id,反之返回已存在的thread_id"""
        task_file_path = REGISTERED_TASKS_PATH / f"{task.name}.yaml"
        if not task_file_path.exists():
            logger.info(f"任务记录不存在: {task_file_path}")
            logger.info(f"将创建新的thread_id，开展绿地开发")
            thread_id = str(uuid.uuid4())
            self.save_traceable_task_to_file(thread_id, task)
            return thread_id

        logger.info(f"任务记录已存在: {task_file_path}")
        if force_using_new_thread:
            logger.info(f"但是本次强制新开thread_id，将覆盖原有thread_id，开展绿地开发")
            thread_id = str(uuid.uuid4())
            self.save_traceable_task_to_file(thread_id, task)
            return thread_id

        logger.info(f"将复用已有的thread_id，开展棕地开发")

        # 读取任务记录文件
        traceable_task = TraceableTask.from_dict(yaml.load(task_file_path.open(), Loader=yaml.FullLoader))
        return traceable_task.thread_id

    # ========== 代理所有调用方法 ==========

    def invoke(self, input, config=None, **kwargs):
        """同步调用 leader"""
        if self.team_type == "simple":
            agent: CompiledStateGraph = self.planner
            return agent.invoke(input, config, **kwargs)
        if self.team_type == "complex":
            agent: CompiledStateGraph = self.leader
            return self.leader.invoke(input, config, **kwargs)
        raise NotImplementedError(f"不支持的 team_type: {self.team_type}")

    def stream(self, input, config=None, stream_mode=None, subgraphs=False, version=None, **kwargs):
        """流式调用 leader"""
        if self.team_type == "simple":
            return self.planner.stream(input, config=config, stream_mode=stream_mode, subgraphs=subgraphs,
                                       version=version, **kwargs)
        if self.team_type == "complex":
            return self.leader.stream(input, config=config, stream_mode=stream_mode, subgraphs=subgraphs,
                                      version=version,
                                      **kwargs)
        raise NotImplementedError(f"不支持的 team_type: {self.team_type}")

    async def ainvoke(self, input, config=None, **kwargs):
        """异步调用 leader"""
        if self.team_type == "simple":
            return await self.planner.ainvoke(input, config, **kwargs)
        if self.team_type == "complex":
            return await self.leader.ainvoke(input, config, **kwargs)
        raise NotImplementedError(f"不支持的 team_type: {self.team_type}")

    async def astream(self, input, config=None, stream_mode=None, subgraphs=False, version=None, **kwargs):
        """异步流式调用 leader"""
        if self.team_type == "simple":
            async for chunk in self.planner.astream(input, config=config, stream_mode=stream_mode, subgraphs=subgraphs,
                                                    version=version, ):
                yield chunk
        if self.team_type == "complex":
            async for chunk in self.leader.astream(input, config=config, stream_mode=stream_mode, subgraphs=subgraphs,
                                                   version=version,
                                                   **kwargs):
                yield chunk
        raise NotImplementedError(f"不支持的 team_type: {self.team_type}")
