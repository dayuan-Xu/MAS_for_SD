import datetime
import logging
import uuid
from pathlib import Path

import yaml
from agentbay import AgentBay
from deepagents.backends import CompositeBackend
from deepagents.middleware import FilesystemMiddleware
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph

from src.config.database import get_async_connection_pool
from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.agent_activity_monitor import AgentActivityMonitor
from src.custom_middleware.message import create_compiled_expert_agent, CommunicateMiddleware
from src.custom_middleware.my_skills import MySkillsMiddleware
from src.custom_middleware.prompt_inject import SystemPromptInjectMiddleware
from src.custom_middleware.unicode_encode_error_handler import UnicodeEncodeErrorHandlerMiddleware
from src.dev_team.my_backend import LinuxSandboxBackend
from src.dev_team.shared_middles import shared_todo_list_middleware, shared_summarization_middleware, \
    tool_retry_middleware, \
    shared_model_retry_middleware, shared_message_sequence_validator
from src.dev_team.team_config import LEADER_SKILL_PATH, ENGINEER_SKILL_PATH, QA_ENGINEER_SKILL_PATH, \
    MY_COMPOSITE_BACKEND_ROUTES, MY_FILESYSTEM_MIDDLEWARE_SYSTEM_PROMPT, \
    MY_WRITE_FILE_TOOL_DESCRIPTION, AGENTBAY_MCP_SERVER_NAME, BUILDER_SKILL_PATH, EVALUATOR_SKILL_PATH, \
    SHARED_INFORMATION_AFTER_SYSTEM_PROMPT, MY_EXECUTE_TOOL_DESCRIPTION, EXCEPTION_IDENTIFIER, TeamType
from src.paths import LOCAL_WAREHOUSE_PATH, \
    REGISTERED_TASKS_PATH, SOFTWARE_DEV_7_PATH, PROMPTS_DIR
from src.tools import get_current_time, internet_search
from src.utils.datasets import TraceableTask, load_dataset
from src.utils.mcp import get_excluded_tools, load_wuying_mcp_tools
from src.utils.roles_prompt_manager import get_system_prompt

logger = logging.getLogger(__name__)


class AgentTeam:
    """基于 AgentBay 的自动化软件开发团队。"""

    def __init__(self, *,
                 task_name: str = "",
                 local_warehouse_path: Path = LOCAL_WAREHOUSE_PATH,
                 team_type: TeamType | str = TeamType.SIMPLE,
                 enable_brown: bool = False,
                 monitor_agent_activity: bool = False):
        """初始化开发团队同步资源
        
        ⚠️ 注意：此方法仅初始化同步资源（中间件、沙盒后端、LLM等），不会创建 checkpointer 和智能体。
        请使用异步工厂方法 create_with_agentbay_mcp() 进行完整初始化。
        
        Args:
            sandbox: 沙盒实例，充当每次任务的项目空间
            local_warehouse_path: 本地项目仓库根目录，用于保存任务成果物。
            team_type: 团队类型
        """

        if isinstance(team_type, str):
            team_type = TeamType(team_type)

        if team_type not in TeamType:
            raise ValueError(f"无效的团队类型: {team_type}")

        self.task_name = task_name
        self.local_warehouse_path = local_warehouse_path
        self.team_type = team_type
        self.enable_brown = enable_brown
        self.monitor_agent_activity = monitor_agent_activity

        # 判断是否开启棕地开发，并根据判断结果初始化沙盒"""
        self.context_service = AgentBay(api_key=settings.WUYING_AGENTBAY_API_KEY).context
        self.thread_id, self.task_context_box_name, self.task_context_box_id, self.is_brown = self.init_dev_config()


        logger.info(f"\n"
                    f"是否棕地开发: {self.is_brown}\n"
                    f"线程ID: {self.thread_id}\n"
                    f"任务上下文盒子名称: {self.task_context_box_name}\n"
                    f"任务上下文盒子ID: {self.task_context_box_id}\n"
                    )

        # 本地存储路径
        self.local_dir_for_task_products = local_warehouse_path / self.task_name / datetime.datetime.now().strftime(
            "%m%d_%H%M")

        # 初始化沙盒
        self.sandbox = LinuxSandboxBackend(
            task_name=task_name,
            task_context_box_name=self.task_context_box_name,
            local_dir_for_task_products=self.local_dir_for_task_products,
        )
        self.sandbox_type = self.sandbox.sandbox_type
        self.task_working_dir = self.sandbox.task_context_box_mount_path  # 本次开发任务的云端项目空间的文件路径

        # 验证 sandbox中沙盒会话是否成功创建
        if not self.sandbox.sandbox_id:
            raise ValueError("AgentTeam 使用的AgentBay MCP 工具必须依赖传入的sandbox的sandbox_id")

        self.sandbox_id = self.sandbox.sandbox_id

        # 创建 injected prompt middleware
        injected_prompt = SHARED_INFORMATION_AFTER_SYSTEM_PROMPT[self.team_type].format(
            sandbox_id=self.sandbox_id,
            exception_identifier=EXCEPTION_IDENTIFIER
        )

        if self.sandbox_id not in injected_prompt:
            raise ValueError(f"sandbox id 注入失败，因为注入的提示词中未找到 {self.sandbox_id}")

        self.injected_prompt_middleware_1 = SystemPromptInjectMiddleware(prompt=injected_prompt)

        # 设置 LLM
        self._llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]
        logger.info(f"智能体开发团队使用的模型: {self._llm.model_name}，温度: {self._llm.temperature}")

        # 创建 composite backend
        self.composite_backend = CompositeBackend(
            default=self.sandbox,
            routes=MY_COMPOSITE_BACKEND_ROUTES[f"{self.sandbox_type}"],
        )

        # 创建文件系统中间件
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

        # 设置技能路径
        self.leader_skill_path = LEADER_SKILL_PATH[f"{self.sandbox_type}"]
        self.engineer_skill_path = ENGINEER_SKILL_PATH[f"{self.sandbox_type}"]
        self.QA_engineer_skill_path = QA_ENGINEER_SKILL_PATH[f"{self.sandbox_type}"]

        self.builder_skill_path = BUILDER_SKILL_PATH[f"{self.sandbox_type}"]
        self.evaluator_skill_path = EVALUATOR_SKILL_PATH[f"{self.sandbox_type}"]

        logger.info("✅ 智能体开发团队同步资源初始化完成")

        # 异步资源
        self.mcp_tools = []
        self._checkpointer = None

        self.planner = None
        self.builder = None
        self.evaluator = None
        self.agents = []
        self.role_to_agent = None
        self.team_type_to_agent = None

    def __str__(self):
        return ("AgentTeam(\n"
                f"      sandbox={self.sandbox},\n"
                f"      sandbox_id={self.sandbox_id},\n"
                f"      sandbox_type={self.sandbox_type},\n"
                f"      team_type={self.team_type},\n"
                f"      is_brown={self.is_brown},\n"
                f"      local_dir_for_task_products={self.local_dir_for_task_products}."
                )

    def init_dev_config(self):
        thread_id, task_context_box_name, task_context_box_id, is_brown = ("", "", "", False)
        task_name = self.task_name
        task_file_path = REGISTERED_TASKS_PATH / f"{task_name}.yaml"

        if self.enable_brown:
            if task_file_path.exists():
                logger.info(f"任务记录已存在: {task_file_path}\n"
                            f"将使用任务记录中的最近的thread_id")
                # 读取任务记录文件
                with open(task_file_path, 'r', encoding='utf-8') as f:
                    traceable_task = TraceableTask.from_dict(yaml.load(f, Loader=yaml.FullLoader))
                thread_id = traceable_task.thread_ids[-1]
                task_context_box_name = traceable_task.task_context_box_names[-1]
                task_context_box_id = traceable_task.task_context_box_ids[-1]
                is_brown = True
            else:
                logger.info(f"任务记录文件不存在: {task_file_path}\n"
                            f"将创建任务记录文件，开展绿地开发")
                thread_id = str(uuid.uuid4())
                task_context_box_name = f"{task_name}_{datetime.datetime.now().strftime('%m%d_%H%M')}"
                task_context_box_id = self.context_service.get(task_context_box_name, create=True).context_id
                is_brown = False
                self.save_traceable_task_to_file(
                    new_thread_id=thread_id,
                    new_box_name=task_context_box_name,
                    new_box_id=task_context_box_id
                )

        else:
            logger.info(f"本次强制绿地开发，将更新任务记录文件，开展绿地开发")
            thread_id = str(uuid.uuid4())
            task_context_box_name = f"{task_name}_{datetime.datetime.now().strftime('%m%d_%H%M')}"
            task_context_box_id = self.context_service.get(task_context_box_name, create=True).context_id
            is_brown = False
            self.save_traceable_task_to_file(
                new_thread_id=thread_id,
                new_box_name=task_context_box_name,
                new_box_id=task_context_box_id
            )

        return thread_id, task_context_box_name, task_context_box_id, is_brown

    # Team 对象完整初始化的入口
    @classmethod
    async def create_with_agentbay_mcp(cls,
                                       task_name: str,
                                       local_warehouse: Path = LOCAL_WAREHOUSE_PATH,
                                       team_type: TeamType | str = TeamType.SIMPLE,
                                       enable_brown: bool = False,
                                       monitor_agent_activity: bool = False):
        """异步工厂方法：创建带有 Wuying AgentBay MCP 工具的 AgentTeam 实例。

        这是推荐的初始化方式，会自动创建沙盒、加载 MCP 工具并初始化智能体。

        Args:
            :param task_name: 软件开发任务名称
            :param team_type: 团队类型
            :param local_warehouse:  本地项目仓库路径
            :param enable_brown: 是否启用 棕地开发 探测

        Returns:
            AgentTeam: 配置好 MCP 工具的团队实例
        """

        # 1. 初始化同步资源（sandbox、LLM、中间件等）
        instance = cls(
            task_name=task_name,
            local_warehouse_path=local_warehouse,
            team_type=team_type,
            enable_brown=enable_brown,
            monitor_agent_activity=monitor_agent_activity,
        )

        # 初始化异步资源 (MCP Tools, checkpointer)
        await instance._initialize_async_resources()

        # 创建所有智能体
        instance._create_all_agents()

        logger.info("✅ AgentTeam实例 初始化完成")
        logger.info(f"{instance}")
        return instance

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
        # 创建简化版三人团队（Planner/Builder/Evaluator）
        logger.info("开始创建多智能体团队...")
        self.evaluator = self._create_evaluator(use_mcp=True, log_agent_activity=self.monitor_agent_activity)
        self.builder = self._create_builder(use_mcp=True, log_agent_activity=self.monitor_agent_activity)
        self.planner = self._create_planner(log_agent_activity=self.monitor_agent_activity)
        if self.monitor_agent_activity:
            logger.info("✅ 多智能体（Alice、Bob、Eva创建完成，三者均添加了活动监控中间件，将记录智能体活动日志")
        

        self.agents = [self.planner, self.builder, self.evaluator]

        self.role_to_agent = {
            "planner": self.planner,
            "builder": self.builder,
            "evaluator": self.evaluator
        }

        self.team_type_to_agent = {
            "single": self.builder,
            "dual": self.builder,
            "simple": self.planner,
        }

    def _create_planner(self, *, use_mcp=False, log_agent_activity=False):
        """创建 Planner Alice（简化版三人团队）"""
        logger.debug("开始创建 Planner Alice...")

        # 创建 Builder 作为 Planner 的专家
        experts = create_compiled_expert_agent(
            self.builder,
            "一名全栈开发工程师，负责功能点的迭代实现。"
        )

        sys_prompt = get_system_prompt("Planner", prompts_dir=PROMPTS_DIR)

        tools = [get_current_time, internet_search] + self.mcp_tools if use_mcp else []

        middlewares = [
            UnicodeEncodeErrorHandlerMiddleware(),
            shared_message_sequence_validator,
            self.injected_prompt_middleware_1,
            shared_todo_list_middleware,
            self._shared_filesystem_middleware,
            CommunicateMiddleware(user_name="Planner Alice", experts=[experts]),
            shared_summarization_middleware,
            tool_retry_middleware,
            shared_model_retry_middleware
        ]
        if log_agent_activity:
            middlewares.insert(0, AgentActivityMonitor(agent_name="Planner Alice"))

        planner = create_agent(
            model=self._llm,
            tools=tools,
            system_prompt=sys_prompt,
            middleware=middlewares,
            checkpointer=self._checkpointer,
            name="Alice"
        )
        logger.info("✅ Planner Alice 创建完成")
        return planner

    def _create_builder(self, *, use_mcp=False, log_agent_activity=False):
        """创建 Builder Bob（简化版三人团队）"""
        logger.debug("开始创建 Builder Bob...")

        experts = []
        if self.team_type != "single":
            # 创建 Evaluator 作为 Builder 的专家
            evaluator_expert = create_compiled_expert_agent(
                self.evaluator,
                "一名严格的质量保证工程师和技术评审专家。"
            )
            experts.append(evaluator_expert)

        sys_prompt = get_system_prompt("Builder", prompts_dir=PROMPTS_DIR)

        tools = [get_current_time, internet_search] + self.mcp_tools if use_mcp else []

        middlewares = [
            UnicodeEncodeErrorHandlerMiddleware(),
            shared_message_sequence_validator,
            self.injected_prompt_middleware_1,
            shared_todo_list_middleware,
            self._shared_filesystem_middleware,
            MySkillsMiddleware(backend=self.composite_backend, sources=[self.builder_skill_path]),
            CommunicateMiddleware(user_name="Builder Bob", experts=experts),
            shared_summarization_middleware,
            tool_retry_middleware,
            shared_model_retry_middleware
        ]
        if log_agent_activity:
            middlewares.insert(0, AgentActivityMonitor(agent_name="Builder Bob"))

        builder = create_agent(
            model=self._llm,
            tools=tools,
            system_prompt=sys_prompt,
            middleware=middlewares,
            checkpointer=self._checkpointer,
            name="Bob"
        )
        logger.info("✅ Builder Bob 创建完成")
        return builder

    def _create_evaluator(self, *, use_mcp=False, log_agent_activity=False):
        """创建 Evaluator Eva（简化版三人团队）"""
        logger.debug("开始创建 Evaluator Eva...")

        sys_prompt = get_system_prompt("Evaluator", prompts_dir=PROMPTS_DIR)

        tools = [get_current_time, internet_search] + self.mcp_tools if use_mcp else []

        middlewares = [
            UnicodeEncodeErrorHandlerMiddleware(),
            shared_message_sequence_validator,
            self.injected_prompt_middleware_1,
            shared_todo_list_middleware,
            self._shared_filesystem_middleware,
            MySkillsMiddleware(backend=self.composite_backend, sources=[self.evaluator_skill_path]),
            shared_summarization_middleware,
            tool_retry_middleware,
            shared_model_retry_middleware
        ]
        if log_agent_activity:
            middlewares.insert(0, AgentActivityMonitor(agent_name="Builder Bob"))

        evaluator = create_agent(
            model=self._llm,
            tools=tools,
            system_prompt=sys_prompt,
            middleware=middlewares,
            checkpointer=self._checkpointer,
            name="Eva"
        )
        logger.info("✅ Evaluator Eva 创建完成")
        return evaluator

    def download_and_cleanup(self, success: bool = True):
        """先下载成果物到本地，后清理会话资源。

        Args:
            success: 任务是否成功完成，用于日志记录
        """
        logger.info(f"开始成果物下载和会话资源清理 (success={success})")

        # 1. 下载成果物
        if self.task_name:
            local_dir = self.local_dir_for_task_products
            logger.info(f"下载任务成果物到: {local_dir}")
            try:
                self.sandbox.download_task_artifacts(local_dir)
            except Exception as e:
                logger.error(f"成果物下载失败: {e}", exc_info=True)
                logger.warning("跳过下载，继续清理会话")
        else:
            logger.warning("self.task_name 为空，跳过下载")

        # 2. 清理云端会话（无论下载是否成功都要执行）
        self.sandbox.delete_session()

    def save_traceable_task_to_file(self, *, new_thread_id: str, new_box_name, new_box_id):
        """保存任务启动记录到 YAML 文件。 """
        # 1 基于当前已知的任务名，构造文件路径
        task_name = self.task_name
        task_file_path = REGISTERED_TASKS_PATH / f"{task_name}.yaml"

        # 2 确保父目录存在
        task_file_path.parent.mkdir(parents=True, exist_ok=True)

        # 3 若已有记录，则更新式写入
        if task_file_path.exists():
            # 读取任务记录文件
            with open(task_file_path, 'r', encoding='utf-8') as f:
                traceable_task = TraceableTask.from_dict(yaml.load(f, Loader=yaml.FullLoader))
            logger.warning(f"⚠️ 任务记录文件在该路径下已经存在: {task_file_path}\n"
                           f"⚠️ 已有任务记录的内容:\n"
                           f" {traceable_task}")
            traceable_task.update(new_thread_id, new_box_name, new_box_id)

            logger.info(f"将更新任务记录并写入文件: {task_file_path}")
        else:
            logger.warning(f"⚠️ 任务记录文件在该路径下不存在: {task_file_path}")
            datasets = load_dataset(SOFTWARE_DEV_7_PATH)
            task = datasets.task_name_to_task[task_name]
            traceable_task = TraceableTask([new_thread_id], [new_box_name], [new_box_id], task)
            logger.info(f"将写入以下任务记录内容: {traceable_task}")

        # 4 保存到 YAML 文件
        with open(task_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(traceable_task.to_dict(), f, allow_unicode=True)
            logger.info(f"✅ 任务启动记录已保存: {task_file_path}")

    # ========== 代理所有调用方法 ==========

    def invoke(self, input, config=None, **kwargs):
        """同步调用"""
        agent: CompiledStateGraph = self.team_type_to_agent[self.team_type]
        return agent.invoke(input, config, **kwargs)

    def stream(self, input, config=None, stream_mode=None, subgraphs=False, version=None, **kwargs):
        """流式调用"""
        agent: CompiledStateGraph = self.team_type_to_agent[self.team_type]
        return agent.stream(input, config, stream_mode=stream_mode, subgraphs=subgraphs, version=version, **kwargs)

    async def ainvoke(self, input, config=None, **kwargs):
        """异步调用"""
        agent: CompiledStateGraph = self.team_type_to_agent[self.team_type]
        return await agent.ainvoke(input, config, **kwargs)

    async def astream(self, input, config=None, stream_mode=None, subgraphs=False, version=None, **kwargs):
        """异步流式调用"""
        agent: CompiledStateGraph = self.team_type_to_agent[self.team_type]
        async for chunk in agent.astream(input, config=config, stream_mode=stream_mode, subgraphs=subgraphs,
                                         version=version,
                                         **kwargs):
            yield chunk

    # ========== 异步上下文管理器支持 ==========

    async def __aenter__(self):
        """支持 async with 语句：进入时返回实例"""
        logger.info(f"🔓 进入 AgentTeam 异步上下文 (task={self.task_name})")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """支持 async with 语句：退出时自动清理资源"""
        logger.info(f"🔒 退出 AgentTeam 异步上下文 (task={self.task_name})")

        # 自动下载成果物并清理沙盒会话
        if self.sandbox and self.sandbox.session:
            try:
                logger.info("🧹 开始自动清理沙盒资源...")

                # 1. 下载成果物到本地
                if self.task_name:
                    try:
                        logger.info(f"📥 下载任务成果物到: {self.local_dir_for_task_products}")
                        self.sandbox.download_task_artifacts(self.local_dir_for_task_products)
                        logger.info("✅ 成果物下载成功")
                    except Exception as e:
                        logger.warning(f"⚠️ 成果物下载失败: {e}，继续清理会话")

                # 2. 删除沙盒会话
                logger.info("🗑️ 删除沙盒会话...")
                self.sandbox.delete_session()
                logger.info("✅ 沙盒会话已清理")

            except Exception as e:
                logger.error(f"❌ 清理资源时出错: {e}", exc_info=True)

        # 如果有异常，记录但不吞掉
        if exc_type:
            logger.error(f"❌ AgentTeam 运行期间发生出现异常。", exc_info=True)

        return False  # 不吞掉异常
