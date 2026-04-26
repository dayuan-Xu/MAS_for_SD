# 本模块保存agentbay based agent的一些配置信息
from deepagents.backends import FilesystemBackend, CompositeBackend

from src.paths import AGENTBAY_BASED_AGENT_RESOURCES_PATH
from src.utils.my_sandbox import MySandbox

my_sandbox_backend = MySandbox()

AGENTBAY_BASED_AGENT_SKILL_PATH = AGENTBAY_BASED_AGENT_RESOURCES_PATH / "skills"
AGENTBAY_BASED_AGENT_MEMORY_PATH = AGENTBAY_BASED_AGENT_RESOURCES_PATH / "memory"

my_composite_backend_routes = {
    "/tmp/persistent/agent_workspace/skills/": FilesystemBackend(root_dir=AGENTBAY_BASED_AGENT_SKILL_PATH,
                                                                 virtual_mode=True),
    "/tmp/persistent/agent_workspace/memory/": FilesystemBackend(root_dir=AGENTBAY_BASED_AGENT_MEMORY_PATH,
                                                                 virtual_mode=True),
}
my_composite_backend = CompositeBackend(
    default=my_sandbox_backend,
    routes=my_composite_backend_routes
)

LEADER_SKILL_PATH = "/tmp/persistent/agent_workspace/skills/leader"
ENGINEER_SKILL_PATH = "/tmp/persistent/agent_workspace/skills/engineer"
QA_ENGINEER_SKILL_PATH = "/tmp/persistent/agent_workspace/skills/QA_engineer"
