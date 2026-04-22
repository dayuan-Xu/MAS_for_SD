from deepagents import CompiledSubAgent, SubAgentMiddleware, create_deep_agent
from deepagents.middleware import SkillsMiddleware
from deepagents.middleware.subagents import SubAgent
from langchain.agents import create_agent

from src.Tools import get_current_time, internet_search
from src.agentbay_based_dev_team.shared_middleware import my_sandbox_backend, filesystem_middleware, \
    summarization_middleware, todo_list_middleware
from src.config.llm import LLMs
from src.config.settings import settings
from src.local_dev_team.shared_middleware import retry_middleware
from src.paths import AGENTBAY_SYSTEM_PROMPTS_FILES
from src.utils.roles_prompt_manager import get_system_prompt, get_system_prompts_for_roles

team_system_prompts = get_system_prompts_for_roles(("product_manager", "architect", "project_manager", "QA_engineer"),
                                                   prompts_dir=AGENTBAY_SYSTEM_PROMPTS_FILES)

llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]

product_manager_graph = create_deep_agent(
    model=llm,
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["product_manager"],
    middleware=[retry_middleware],
    backend=my_sandbox_backend,
    name="Alice_ProductManager"
)
product_manager = CompiledSubAgent(
    name="Alice",
    description="一名产品经理，可根据需求描述，交付一份产品需求文档。",
    runnable=product_manager_graph,
)

architect_graph = create_deep_agent(
    model=llm,
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["architect"],
    middleware=[retry_middleware],
    backend=my_sandbox_backend,
    name="Bob_Architect"
)
architect = CompiledSubAgent(
    name="Bob",
    description="一名架构师，可根据产品需求文档，交付一份软件架构设计文档。",
    runnable=architect_graph,
)

project_manager_graph = create_deep_agent(
    model=llm,
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["project_manager"],
    middleware=[retry_middleware],
    backend=my_sandbox_backend,
    name="Cindy_ProjectManager"  # langchain在给AIMessage添加name属性时使用
)
project_manager = CompiledSubAgent(
    name="Cindy",  # SubAgentMiddleware在注入系统提示词时使用
    description="一名项目经理，可根据软件架构设计文档，交付软件详细设计文档。",
    runnable=project_manager_graph,
)

# 设置主干模型
llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]

# 通用子智能体描述
DEFAULT_GENERAL_PURPOSE_DESCRIPTION = ("General-purpose agent for "
                                       "researching complex questions, "
                                       "searching for files and content,"
                                       " and executing multi-step tasks. "
                                       "When you are searching for a keyword or file "
                                       "and are not confident that you will find the right match in the first few tries "
                                       "use this agent to perform the search for you. "
                                       "This agent has access to all tools as the main agent.")  # noqa: E501

DEFAULT_SUBAGENT_PROMPT = "In order to complete the objective that the user asks of you, you have access to a number of standard tools."


def create_expert_agent(
        role_name: str,
        skill_path: str,
        agent_name_in_AIMessage: str,
        expert_name: str,
        expert_description: str,
        checkpointer_enabled: bool = True,
) -> CompiledSubAgent:
    """创建专家智能体及其对应的CompiledSubAgent。
    
    Args:
        role_name: 角色名称（用于获取系统提示词，如 "engineer", "QA_engineer"）
        skill_path: 技能路径（如 ENGINEER_SKILL_PATH）
        agent_name_in_AIMessage: 该智能体发出的AIMessage中的name值（如 "David_Engineer"）
        expert_name: assign主调智能体可见的专家名称（如 "Alice"、"David"）
        expert_description: 专家描述
        checkpointer_enabled: 专家在多次assign间是否保持记忆
    
    Returns:
        team_expert
    """
    # 创建技能中间件
    skills_middleware = SkillsMiddleware(
        backend=my_sandbox_backend,
        sources=[skill_path]
    )

    # 获取系统提示词
    sys_prompt = get_system_prompt(role_name, prompts_dir=AGENTBAY_SYSTEM_PROMPTS_FILES)

    # 配置通用子智能体
    general_purpose_subagent: SubAgent = {
        "model": llm,
        "tools": [],
        "name": "general-purpose",
        "description": DEFAULT_GENERAL_PURPOSE_DESCRIPTION,
        "system_prompt": DEFAULT_SUBAGENT_PROMPT,
        "middleware": [
            filesystem_middleware,
            skills_middleware,
            summarization_middleware,
            retry_middleware,
        ],
    }

    subagent_middleware = SubAgentMiddleware(
        backend=my_sandbox_backend,
        subagents=[general_purpose_subagent]
    )

    # 创建智能体
    agent = create_agent(
        model=llm,
        tools=[get_current_time],
        system_prompt=sys_prompt,
        middleware=[
            todo_list_middleware,
            skills_middleware,
            filesystem_middleware,
            subagent_middleware,
            summarization_middleware,
            retry_middleware,
        ],
        checkpointer=checkpointer_enabled,
        name=agent_name_in_AIMessage,
    )

    # 创建CompiledSubAgent,视为可assign的团队专家
    team_expert = CompiledSubAgent(
        name=expert_name,
        description=expert_description,
        runnable=agent,
    )

    return team_expert


# 从 custom_middleware.my_sandbox 导入技能路径常量
from src.custom_middleware.my_sandbox import ENGINEER_SKILL_PATH, QA_ENGINEER_SKILL_PATH

# 创建工程师
engineer = create_expert_agent(
    role_name="engineer",
    skill_path=ENGINEER_SKILL_PATH,
    agent_name_in_AIMessage="David_Engineer",
    expert_name="David",
    expert_description="一名软件工程师，可根据明确的编码任务需求，交付功能性代码文件和测试代码文件，同时完成代码调试、单元测试、集成测试。",
    checkpointer_enabled=True,  # David应该在多次assign间保持记忆
)

# 创建QA工程师
QA_engineer = create_expert_agent(
    role_name="QA_engineer",
    skill_path=QA_ENGINEER_SKILL_PATH,
    agent_name_in_AIMessage="Eva_QA_Engineer",
    expert_name="Eva",
    expert_description="一名软件测试员，可对指定的软件项目进行系统测试，交付一份系统测试报告。",
    checkpointer_enabled=True,  # Eva应该在多次assign间保持记忆
)

team_experts = [product_manager, architect, project_manager,  # 全是一次性deep agent
                engineer,  # 需要执行工具，所以提示词和工具描述需要一定的定制化，不能直接用deep agent
                QA_engineer]  # 需要执行工具，所以提示词和工具描述需要一定的定制化，不能直接用deep agent
