from deepagents import create_deep_agent, CompiledSubAgent
from deepagents.backends import FilesystemBackend

from src.Tools import internet_search, get_current_time
from src.agent_based_dev_team.QA_engineer import QA_engineer_subagent
from src.agent_based_dev_team.engineer_agent import engineer_subagent
from src.agent_based_dev_team.shared_middleware import shared_retry_middleware
from src.config.llm import LLMs
from src.config.settings import settings
from src.paths import LOCAL_AGENT_WORKSPACE, AGENT_SYSTEM_PROMPTS_FILES
from src.utils.roles_prompt_manager import get_system_prompts_for_roles

team_system_prompts = get_system_prompts_for_roles(("product_manager", "architect", "project_manager", "QA_engineer"),
                                                   prompts_dir=AGENT_SYSTEM_PROMPTS_FILES)

llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]

product_manager_graph = create_deep_agent(
    model=llm,
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["product_manager"],
    middleware=[shared_retry_middleware],
    backend=FilesystemBackend(LOCAL_AGENT_WORKSPACE, virtual_mode=True),
    name="Alice_ProductManager"
)
product_manager_subagent = CompiledSubAgent(
    name="Alice",
    description="一名资深产品经理，可根据需求描述，交付一份产品需求文档。",
    runnable=product_manager_graph,
)

architect_graph = create_deep_agent(
    model=llm,
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["architect"],
    middleware=[shared_retry_middleware],
    backend=FilesystemBackend(LOCAL_AGENT_WORKSPACE, virtual_mode=True),
    name="Bob_Architect"
)
architect_subagent = CompiledSubAgent(
    name="Bod",
    description="一名资深架构师，可根据产品需求文档，交付一份软件架构设计文档。",
    runnable=architect_graph,
)

project_manager_graph = create_deep_agent(
    model=llm,
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["project_manager"],
    middleware=[shared_retry_middleware],
    backend=FilesystemBackend(LOCAL_AGENT_WORKSPACE, virtual_mode=True),
    name="Cindy_ProjectManager"
)
project_manager_subagent = CompiledSubAgent(
    name="Cindy",
    description="一名资深项目经理，可根据软件架构设计文档，交付软件详细设计文档。",
    runnable=project_manager_graph,
)

subagents = [product_manager_subagent, architect_subagent, project_manager_subagent,  # 全是一次性deep agent
             engineer_subagent,  # 需要执行工具，所以提示词和工具描述需要一定的定制化，不能直接用deep agent
             QA_engineer_subagent]  # 需要执行工具，所以提示词和工具描述需要一定的定制化，不能直接用deep agent
