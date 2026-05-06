import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from deepagents import SubAgentMiddleware, create_deep_agent
from deepagents.backends import CompositeBackend
from deepagents.middleware import FilesystemMiddleware, SkillsMiddleware
from deepagents.middleware.subagents import SubAgent
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import MemorySaver, InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

from src.Tools import get_current_time, internet_search
from src.config.llm import LLMs
from src.config.settings import settings
from src.custom_middleware.enhanced_assign import EnhancedAssignMiddleware, create_compiled_expert_agent
from src.custom_middleware.prompt_inject import SystemPromptInjectMiddleware
from src.paths import AGENTBAY_SYSTEM_PROMPTS_FILES, LOCAL_PROJECTS_WAREHOUSE_FOR_REMOTE_TASK_RESULT, \
    USER_SOFTWARE_DEV_TASKS_PATH
from src.remote_dev_team.agent_team_config import LEADER_SKILL_PATH, ENGINEER_SKILL_PATH, QA_ENGINEER_SKILL_PATH, \
    MY_COMPOSITE_BACKEND_ROUTES, MY_FILESYSTEM_MIDDLEWARE_SYSTEM_PROMPT, \
    MY_WRITE_FILE_TOOL_DESCRIPTION
from src.remote_dev_team.my_sandbox_backend import AgentBayBasedLinuxSandboxBackend
from src.remote_dev_team.shared_middleware import todo_list_middleware, summarization_middleware, \
    model_retry_middleware, agent_activity_monitor, tool_retry_middleware
from src.utils.datasets import Task, TraceableTask
from src.utils.roles_prompt_manager import get_system_prompt

logger = logging.getLogger(__name__)

middleware_list = """
智能体中间件列表:
            todo_list_middleware,  # 共享
            skills_middleware,  # 专属
            fs_middleware,  # 共享
            subagent_middleware,  # 专属
            assign_middleware,  # 专属（因为包含专属 experts）
            summarization_middleware,  # 共享
            tool_retry_middleware,    # 共享
            model_retry_middleware,  # 共享
"""

BACKGROUND_INFORMATION = """
## 背景信息
1. 已知当前软件开发任务基于的沙箱的ID是sandbox id="{sandbox_id}"，所以当你调用那些需要传入sandbox id的工具的时候，**只能用**该sandbox id。
2. 本次软件开发任务仅允许基于当前这个已有沙箱（sandbox id="{sandbox_id}"），**禁止**调用 create_sandbox 新建任何其他sandbox。"""


class DevTeamWithLinuxSandboxAndMCP:
    """基于 AgentBay 的自动化软件开发团队。

    该类负责：
    1. 基于传入的 sandbox 创建composite backend，之后创建统一的文件系统中间件
    2. 使用这些中间件创建所有团队专家（Product Manager、Architect、Project Manager、Engineer、QA Engineer）
    3. 创建 Team Leader，并将所有专家注册到 EnhancedAssignMiddleware
    4. 暴露 leader 的所有调用方法（invoke、stream 等）
    
    所有团队成员共享同一个 composite backend，智能体只能感知到一个文件系统
    但实际上，不同的文件操作会被路由到不同后端（项目操作路由到沙盒后端，技能读取、记忆存取操作路由到本地文件系统后端）。
    """
    # 共享的 checkpointer，供 Leader 和所有专家智能体使用
    shared_checkpointer = MemorySaver()

    if isinstance(shared_checkpointer, InMemorySaver):
        logger.info("当前智能体团队使用的检查器类型：Memory checkpointer")
    elif isinstance(shared_checkpointer, PostgresSaver):
        logger.info("当前智能体团队使用的检查器类型：Postgres checkpointer")

    def __init__(self, sandbox: AgentBayBasedLinuxSandboxBackend,
                 local_warehouse_for_remote_task_result: Path = LOCAL_PROJECTS_WAREHOUSE_FOR_REMOTE_TASK_RESULT,
                 agentbay_mcp_tools: Optional[list] = None):
        """初始化开发团队 V2。
        
        Args:
            sandbox: 沙盒实例，充当每次任务的项目空间
            local_warehouse_for_remote_task_result: 本地项目仓库根目录，用于保存任务成果物。
            agentbay_mcp_tools: 可选的 AgentBay MCP 工具列表，如果提供则会被添加到工程师和 QA 工程师的工具集中
        """
        logger.info(f"开始初始化 DevTeamWithLinuxSandboxAndMCP")
        logger.debug(f"获得的沙盒实例: \n{sandbox}")
        if not sandbox.task_name:
            raise ValueError("DevTeamWithLinuxSandboxAndMCP 实例所用的sandbox必须有一个软件开发任务")

        if not sandbox.sandbox_id:
            raise ValueError("DevTeamWithLinuxSandboxAndMCP 使用的AgentBay MCP 工具必须依赖传入的sandbox的sandbox_id")

        self.sandbox = sandbox
        self.sandbox_type = sandbox.sandbox_type
        self.sandbox_id = sandbox.sandbox_id

        self.injected_prompt = BACKGROUND_INFORMATION.format(sandbox_id=self.sandbox_id)

        self.injected_prompt_middleware_1 = SystemPromptInjectMiddleware(prompt=self.injected_prompt)

        self.mcp_tools = agentbay_mcp_tools or []  # 存储 MCP 工具

        # 组合式后端，在智能体看来就像是一个后端一样
        self.composite_backend = CompositeBackend(
            default=self.sandbox,
            routes=MY_COMPOSITE_BACKEND_ROUTES[f"{self.sandbox_type}"],
        )

        # 技能中间件读取技能文件夹的源头路径
        self.leader_skill_path = LEADER_SKILL_PATH[f"{self.sandbox_type}"]
        self.engineer_skill_path = ENGINEER_SKILL_PATH[f"{self.sandbox_type}"]
        self.QA_engineer_skill_path = QA_ENGINEER_SKILL_PATH[f"{self.sandbox_type}"]

        logger.debug(f"开始创建共享的文件系统中间件...")

        # 该langchain deepagents框架内置的文件系统中间件中提供的6个文件操作工具仅友好支持linux系统下的绝对路径，不支持windows系统下的绝对路径
        self._shared_filesystem_middleware = FilesystemMiddleware(
            backend=self.composite_backend,
            system_prompt=MY_FILESYSTEM_MIDDLEWARE_SYSTEM_PROMPT.format(sandbox_type=self.sandbox_type),
            custom_tool_descriptions={
                "write_file": MY_WRITE_FILE_TOOL_DESCRIPTION
            })
        logger.debug(f"成功创建共享的文件系统中间件，该文件系统中间件基于{self.sandbox_type}镜像")

        self._llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]
        logger.info(f"智能体开发团队使用的模型: {self._llm.model_name}，温度: {self._llm.temperature}")

        # 创建团队
        logger.info("开始创建团队专家...")
        self.product_manager = self._create_deep_agent(role="product_manager", name="Alice")
        self.architect = self._create_deep_agent(role="architect", name="Bob")
        self.project_manager = self._create_deep_agent(role="project_manager", name="Cindy")

        # 创建工程师和QA工程师时添加额外工具，比如 MCP 工具
        # self.extr_tools = [self.multimodal_browser_review_tool, self.multimodal_computer_review_tool]
        # self.extr_tools = [self.run_browser_use_aget_tool] + self.agentbay_mcp_tools
        logger.info(f"工程师和 QA 工程师将使用 {len(self.mcp_tools)} 个 MCP 工具)")

        self.engineer = self._create_engineer(name="David", extra_tools=self.mcp_tools)
        self.QA_engineer = self._create_QA_engineer(name="Eva", extra_tools=self.mcp_tools)

        self.compiled_expert_agents = [
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
            f"已创建 {len(self.compiled_expert_agents)} 个专家: {[expert['name'] for expert in self.compiled_expert_agents]}")

        self.leader = self._create_leader(extra_tools=self.mcp_tools)

        self.role_to_agent = {
            "product_manager": self.product_manager,
            "architect": self.architect,
            "project_manager": self.project_manager,
            "engineer": self.engineer,
            "QA_engineer": self.QA_engineer,
            "Leader": self.leader
        }

        # 记录开发团队启动时间戳，用于成果物版本管理
        self._dev_start_timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        logger.info(f"🕒 开发团队启动时间戳: {self._dev_start_timestamp}")

        # 针对task的本次运行，本地存储任务成果物的地址
        logger.debug(f"本地用于保存任务成果物的项目仓库路径: {local_warehouse_for_remote_task_result}")
        self.local_dir_storing_task_products = local_warehouse_for_remote_task_result / self.sandbox.task_name / self._dev_start_timestamp

        logger.info("✅ DevTeamWithLinuxSandboxAndMCP 初始化完成")
        logger.info(f"{self}")

    def __str__(self):
        return (f"DevTeamWithLinuxSandboxAndMCP(\n"
                f"      sandbox={self.sandbox},\n"
                f"      sandbox_type={self.sandbox_type},\n"
                f"      sandbox_id={self.sandbox_id},\n"
                )

    def _create_skills_middleware(self, sources: list[str]):
        """创建基于 composite backend 的技能中间件，不可在多个智能体间共享
        
        Args:
            sources: 技能路径列表，如 [LEADER_SKILL_PATH] 或 [ENGINEER_SKILL_PATH]
        """
        logger.debug(f"创建技能中间件，来源: {sources}")
        return SkillsMiddleware(backend=self.composite_backend, sources=sources)

    def _create_subagent_middleware(self, skills_middleware):
        """创建基于 composite backend 的子智能体中间件，用于作为主智能体的分身，不可共享"""
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
            "tools": [],
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

    def _create_deep_agent(self, *, role, name, log_agent_activity=False):
        """创建deep agent，其name属性将会是f"{name}_{role.title().replace('_', '')}"

        Args:
            role: 角色、身份（用于获取系统提示词，如 "product_manager", "architect", "project_manager", "QA_engineer"）
            name: assign主调智能体可见的专家名称（如 "Alice", "Bob", "Cindy"）

        Returns:
            CompiledStateGraph
        """
        logger.debug(f"开始创建智能体：{name} (身份：{role})")
        sys_prompt = get_system_prompt(role, prompts_dir=AGENTBAY_SYSTEM_PROMPTS_FILES)

        deep_agent_middleware = [
            model_retry_middleware
        ]
        if log_agent_activity:
            logger.info(f"对智能体{name} (身份：{role}) 启用智能体活动监控日志")
            deep_agent_middleware.insert(0, agent_activity_monitor)

        agent = create_deep_agent(
            model=self._llm,
            tools=[get_current_time, internet_search],
            system_prompt=sys_prompt,
            middleware=deep_agent_middleware,
            checkpointer=DevTeamWithLinuxSandboxAndMCP.shared_checkpointer,
            backend=self.composite_backend,
            name=f"{name}_{role.title().replace('_', '')}"
        )
        logger.debug(f"创建智能体 {name} (身份：{role}) 完成")
        return agent

    def _create_engineer(self, *, role="engineer", name, extra_tools: Optional[list] = None, log_agent_activity=False):
        """创建工程师智能体"""
        logger.debug(f"开始建智能体 {name} (身份：{role})")
        skills_middleware = self._create_skills_middleware([self.engineer_skill_path])
        fs_middleware = self._shared_filesystem_middleware
        subagent_middleware = self._create_subagent_middleware(skills_middleware)

        sys_prompt = get_system_prompt(role, prompts_dir=AGENTBAY_SYSTEM_PROMPTS_FILES)

        engineer_middleware = [
            self.injected_prompt_middleware_1,
            todo_list_middleware,
            skills_middleware,
            fs_middleware,
            subagent_middleware,
            summarization_middleware,
            tool_retry_middleware,
            model_retry_middleware,
        ]

        if log_agent_activity:
            logger.info(f"对智能体{name} (身份：{role}) 启用智能体活动监控日志")
            engineer_middleware.insert(0, agent_activity_monitor)

        # 传入 checkpointer，使专家能够自主持久化状态
        agent = create_agent(
            model=self._llm,
            tools=[get_current_time] + extra_tools if extra_tools else [],
            system_prompt=sys_prompt,
            middleware=engineer_middleware,
            checkpointer=DevTeamWithLinuxSandboxAndMCP.shared_checkpointer,
            name=f"{name}_{role.title().replace('_', '')}"
        )

        logger.debug(f"智能体 {name} (身份：{role})创建完成")
        return agent

    def _create_QA_engineer(self, *, role="QA_engineer", name, extra_tools: Optional[list] = None,
                            log_agent_activity=False):
        """创建QA工程师智能体"""
        logger.debug(f"创建 {name} (身份：{role})")
        skills_middleware = self._create_skills_middleware([self.QA_engineer_skill_path])
        fs_middleware = self._shared_filesystem_middleware
        subagent_middleware = self._create_subagent_middleware(skills_middleware)

        sys_prompt = get_system_prompt(role, prompts_dir=AGENTBAY_SYSTEM_PROMPTS_FILES)

        qa_engineer_middleware = [
            self.injected_prompt_middleware_1,
            todo_list_middleware,
            skills_middleware,
            fs_middleware,
            subagent_middleware,
            summarization_middleware,
            tool_retry_middleware,
            model_retry_middleware,
        ]
        if log_agent_activity:
            logger.info(f"对智能体{name} (身份：{role}) 启用智能体活动监控日志")
            qa_engineer_middleware.insert(0, agent_activity_monitor)

        # 传入 checkpointer，使专家能够自主持久化状态
        agent = create_agent(
            model=self._llm,
            tools=[get_current_time] + extra_tools if extra_tools else [],
            system_prompt=sys_prompt,
            middleware=qa_engineer_middleware,
            checkpointer=DevTeamWithLinuxSandboxAndMCP.shared_checkpointer,  # ⭐ 传入共享的 checkpointer
            name=f"{name}_{role.title().replace('_', '')}"  # langchain在给AIMessage添加name属性时使用
        )

        logger.debug(f"智能体 {name} (身份：{role})创建完成")
        return agent

    def _create_leader(self, *, extra_tools: Optional[list] = None, log_agent_activity=False):
        """创建团队 Leader"""
        logger.debug("开始创建 Team Leader...")

        fs_middleware = self._shared_filesystem_middleware

        # 创建 Leader 专属的 middleware
        logger.debug("创建 Leader 的技能中间件")
        skills_middleware = self._create_skills_middleware([self.leader_skill_path])

        logger.debug("创建 Leader 的子智能体中间件")
        subagent_middleware = self._create_subagent_middleware(skills_middleware)

        logger.debug(f"创建 EnhancedAssignMiddleware，注册 {len(self.compiled_expert_agents)} 个专家")

        # 使用 EnhancedAssignMiddleware
        assign_middleware = EnhancedAssignMiddleware(experts=self.compiled_expert_agents)

        # 获取系统提示词
        logger.debug("加载 Team Leader 系统提示词")
        leader_sys_prompt = get_system_prompt("team_leader", prompts_dir=AGENTBAY_SYSTEM_PROMPTS_FILES)

        leader_middleware = [
            self.injected_prompt_middleware_1,
            todo_list_middleware,  # 共享
            skills_middleware,  # 专属
            fs_middleware,  # 共享
            subagent_middleware,  # 专属
            assign_middleware,  # 专属（因为包含专属 experts）
            summarization_middleware,  # 共享
            tool_retry_middleware,  # 共享
            model_retry_middleware,  # 共享
        ]

        if log_agent_activity:
            logger.info("对Leader 启用智能体活动监控日志")
            leader_middleware.insert(0, agent_activity_monitor)

        # 创建 Leader agent
        logger.info("创建 Leader Agent (包含多个中间件)...")
        leader = create_agent(
            model=self._llm,
            tools=[get_current_time] + extra_tools if extra_tools else [],
            system_prompt=leader_sys_prompt,
            middleware=leader_middleware,
            checkpointer=DevTeamWithLinuxSandboxAndMCP.shared_checkpointer,
            name="Tim_Leader",
        )

        logger.info("✅ Team Leader 创建完成")
        return leader

    def download_and_cleanup(self, success: bool = True):
        """先下载成果物到本地，后清理会话资源。

        Args:
            success: 任务是否成功完成，用于日志记录
        """
        logger.info(f"开始成果物下载和会话资源清理 (success={success})")

        # 1. 下载成果物
        if self.sandbox.task_name:
            local_dir = self.local_dir_storing_task_products
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
        task_file_path = USER_SOFTWARE_DEV_TASKS_PATH / f"{traceable_task.task.name}.yaml"

        # 4 确保父目录存在
        task_file_path.parent.mkdir(parents=True, exist_ok=True)

        # 5 保存到 YAML 文件
        with open(task_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(traceable_task.to_dict(), f, allow_unicode=True)
            logger.info(f"✅ 任务启动记录已保存: {task_file_path}")

    def green_or_brown(self, task: Task, force_using_new_thread: bool = False) -> str:
        """判断任务是否是绿色开发，如果是，则返回新的thread_id，
        否则若强制在旧存储盒基础上新开thread_id，则返回新的thread_id,反之返回已存在的thread_id"""
        task_file_path = USER_SOFTWARE_DEV_TASKS_PATH / f"{task.name}.yaml"
        if not task_file_path.exists():
            logger.info(f"任务记录不存在: {task_file_path}")
            logger.info(f"说明是绿地开发，将创建新的thread_id")
            thread_id = str(uuid.uuid4())
            self.save_traceable_task_to_file(thread_id, task)
            return thread_id

        logger.info(f"任务记录已存在: {task_file_path}")
        if force_using_new_thread:
            logger.info(f"说明是棕地开发，并且本次强制在存储盒基础上新开thread_id，同时覆盖原有的任务记录")
            thread_id = str(uuid.uuid4())
            self.save_traceable_task_to_file(thread_id, task)
            return thread_id

        logger.info(f"说明是棕地开发，将复用已有的thread_id")

        # 读取任务记录文件
        traceable_task = TraceableTask.from_dict(yaml.load(task_file_path.open(), Loader=yaml.FullLoader))
        return traceable_task.thread_id

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

    @staticmethod
    async def _load_wuying_mcp_tools() -> list:
        """异步加载 Wuying MCP 服务器提供的工具。

        Returns:
            list: MCP 工具列表
        """
        logger.info("开始加载 Wuying MCP 服务器工具...")
        try:
            client = MultiServerMCPClient(
                {
                    "wuying_mcp_server": {
                        "transport": "http",
                        "url": f"https://agentbay.wuying.aliyuncs.com/v2/mcp?APIKEY={settings.WUYING_AGENTBAY_API_KEY}&IMAGEID=linux_latest",
                    }
                }
            )
            tools = await client.get_tools()
            logger.info(f"✅ 成功加载 {len(tools)} 个 Wuying MCP 工具")
            logger.debug(f"工具名称: {[tool.name for tool in tools]}")
            return tools
        except Exception as e:
            logger.error(f"❌ 加载 Wuying MCP 工具失败: {e}", exc_info=True)
            logger.warning("将不使用 Wuying MCP 工具，继续初始化")
            return []

    @classmethod
    async def create_with_mcp_tools(cls, sandbox: AgentBayBasedLinuxSandboxBackend,
                                    local_warehouse_for_remote_task_result: Path = LOCAL_PROJECTS_WAREHOUSE_FOR_REMOTE_TASK_RESULT):
        """异步工厂方法：创建带有 Wuying MCP 工具的 AgentBayBasedDevTeamV2 实例。

        这是推荐的初始化方式，会自动加载 MCP 工具并传递给工程师和 QA 工程师。

        Args:
            sandbox: 沙盒实例
            local_warehouse_for_remote_task_result: 本地项目仓库路径

        Returns:
            DevTeamWithLinuxSandboxAndMCP: 配置好 MCP 工具的团队实例

        Example:
            >>> async def main():
            ...     with AgentBayBasedLinuxSandboxBackend(task_name="test") as sandbox:
            ...         team = await DevTeamWithLinuxSandboxAndMCP.create_with_mcp_tools(sandbox)
            ...         result = await team.ainvoke({"messages": [...]})
        """
        # 1. 先异步加载 MCP 工具
        mcp_tools = await cls._load_wuying_mcp_tools()

        # 2. 创建实例（传入 MCP 工具）
        instance = cls(sandbox, local_warehouse_for_remote_task_result, agentbay_mcp_tools=mcp_tools)

        logger.info("✅ DevTeamWithLinuxSandboxAndMCP 初始化完成")
        return instance
