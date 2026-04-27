# 本模块保存agentbay based agent的一些配置信息
from deepagents.backends import FilesystemBackend

from src.paths import AGENTBAY_BASED_AGENT_RESOURCES_PATH

AGENTBAY_BASED_AGENT_SKILL_PATH = AGENTBAY_BASED_AGENT_RESOURCES_PATH / "skills"
AGENTBAY_BASED_AGENT_MEMORY_PATH = AGENTBAY_BASED_AGENT_RESOURCES_PATH / "memory"

my_composite_backend_routes = {
    "/tmp/persistent/agent_workspace/skills/": FilesystemBackend(root_dir=AGENTBAY_BASED_AGENT_SKILL_PATH,
                                                                 virtual_mode=True),
    "/tmp/persistent/agent_workspace/memory/": FilesystemBackend(root_dir=AGENTBAY_BASED_AGENT_MEMORY_PATH,
                                                                 virtual_mode=True),
}

LEADER_SKILL_PATH = "/tmp/persistent/agent_workspace/skills/leader"
ENGINEER_SKILL_PATH = "/tmp/persistent/agent_workspace/skills/engineer"
QA_ENGINEER_SKILL_PATH = "/tmp/persistent/agent_workspace/skills/QA_engineer"

MY_WRITE_FILE_TOOL_DESCRIPTION = """
Writes to a new file in the filesystem.
Usage:
- The write_file tool will create the a new file.
- Prefer to edit existing files (with the edit_file tool) over creating new ones when possible.
- **分段创建长文档**：禁止一次性调用该工具生成长文档，而是应该先调用该工具一次以创建文档骨架（包含文档元数据和所有章节标题），之后再多次调用edit_file tool逐个章节填充内容，每次将章节标题替换为完整章节。 
- 若不知道当前创建的是否为长文档，就默认使用分段创建方式。"""
