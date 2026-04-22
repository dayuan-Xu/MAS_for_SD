from deepagents import create_deep_agent, CompiledSubAgent

from src.Tools import internet_search, get_current_time
from src.config.llm import LLMs
from src.config.settings import settings
from src.local_dev_team.QA_engineer import QA_engineer_subagent
from src.local_dev_team.engineer_agent import engineer_subagent
from src.local_dev_team.shared_middleware import retry_middleware, my_local_backend
from src.paths import AGENT_SYSTEM_PROMPTS_FILES
from src.utils.roles_prompt_manager import get_system_prompts_for_roles

team_system_prompts = get_system_prompts_for_roles(("product_manager", "architect", "project_manager", "QA_engineer"),
                                                   prompts_dir=AGENT_SYSTEM_PROMPTS_FILES)

llm = LLMs["minimax-m2.7"] if settings.USE_PAID_LLM_API else LLMs["gpt-5-mini"]

product_manager_graph = create_deep_agent(
    model=llm,
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["product_manager"],
    middleware=[retry_middleware],
    backend=my_local_backend,
    name="Alice_ProductManager"
)
product_manager_subagent = CompiledSubAgent(
    name="Alice",
    description="一名产品经理，可根据需求描述，交付一份产品需求文档。",
    runnable=product_manager_graph,
)

architect_graph = create_deep_agent(
    model=llm,
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["architect"],
    middleware=[retry_middleware],
    backend=my_local_backend,
    name="Bob_Architect"
)
architect_subagent = CompiledSubAgent(
    name="Bob",
    description="一名架构师，可根据产品需求文档，交付一份软件架构设计文档。",
    runnable=architect_graph,
)

project_manager_graph = create_deep_agent(
    model=llm,
    tools=[get_current_time, internet_search],
    system_prompt=team_system_prompts["project_manager"],
    middleware=[retry_middleware],
    backend=my_local_backend,
    name="Cindy_ProjectManager"  # langchain在给AIMessage添加name属性时使用
)
project_manager_subagent = CompiledSubAgent(
    name="Cindy",  # SubAgentMiddleware在注入系统提示词时使用
    description="一名项目经理，可根据软件架构设计文档，交付软件详细设计文档。",
    runnable=project_manager_graph,
)

subagents = [product_manager_subagent, architect_subagent, project_manager_subagent,  # 全是一次性deep agent
             engineer_subagent,  # 需要执行工具，所以提示词和工具描述需要一定的定制化，不能直接用deep agent
             QA_engineer_subagent]  # 需要执行工具，所以提示词和工具描述需要一定的定制化，不能直接用deep agent
