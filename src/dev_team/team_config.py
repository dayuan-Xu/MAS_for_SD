# 本模块保存agentbay based agent的一些配置信息
from deepagents.backends import FilesystemBackend

from src.paths import AGENT_RESOURCES_PATH

AGENTBAY_BASED_AGENT_SKILL_PATH = AGENT_RESOURCES_PATH / "skills"
AGENTBAY_BASED_AGENT_MEMORY_PATH = AGENT_RESOURCES_PATH / "memory"

# 将智能体对不同路径的文件操作路由到不同的后端
MY_COMPOSITE_BACKEND_ROUTES = {
    "windows": {
        "C:/tmp/persistent/agent_workspace/skills/": FilesystemBackend(root_dir=AGENTBAY_BASED_AGENT_SKILL_PATH,
                                                                       virtual_mode=True),
        "C:/tmp/persistent/agent_workspace/memory/": FilesystemBackend(root_dir=AGENTBAY_BASED_AGENT_MEMORY_PATH,
                                                                       virtual_mode=True),
    },
    "linux": {
        "/tmp/persistent/agent_workspace/skills/": FilesystemBackend(root_dir=AGENTBAY_BASED_AGENT_SKILL_PATH,
                                                                     virtual_mode=True),
        "/tmp/persistent/agent_workspace/memory/": FilesystemBackend(root_dir=AGENTBAY_BASED_AGENT_MEMORY_PATH,
                                                                     virtual_mode=True),
    }
}

# 基于不同的沙盒类型，技能中间件应该从不同的路径中加载技能sources
LEADER_SKILL_PATH = {
    "linux": "/tmp/persistent/agent_workspace/skills/leader",
    "windows": "C:/tmp/persistent/agent_workspace/skills/leader"
}

ENGINEER_SKILL_PATH = {
    "linux": "/tmp/persistent/agent_workspace/skills/engineer",
    "windows": "C:/tmp/persistent/agent_workspace/skills/engineer"}

QA_ENGINEER_SKILL_PATH = {
    "linux": "/tmp/persistent/agent_workspace/skills/QA_engineer",
    "windows": "C:/tmp/persistent/agent_workspace/skills/QA_engineer"}

MY_FILESYSTEM_MIDDLEWARE_SYSTEM_PROMPT = """## 遵循规范

- 编辑文件前先阅读内容——在修改前理解文件现有内容。
- 模仿项目现有风格、命名规范与代码模式。

## 沙盒文件系统工具 `ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep`

你可通过以下工具与当前沙盒中的文件系统进行交互。所有文件路径必须以 `/` 开头。
按照工具的文档字符串使用对应功能，读取大文件时请使用分页（偏移量/限制数）。

- ls：列出目录下的文件（需传入绝对路径）
- read_file：从文件系统读取文件
- write_file：向文件系统中的文件写入内容
- edit_file：编辑文件系统中的文件
- glob：查找匹配指定模式的文件（如 `"**/*.py"`）
- grep：在文件内搜索文本内容

注意！由于目前上面6个文件系统工具目前仅仅在linux沙盒环境下适合使用。已知当前沙盒环境为{sandbox_type}，若沙盒环境不是linux，你可以不使用上面的6个工具。

## 大型工具返回结果

当工具返回结果过大时，内容可能不会直接内联返回，而是转存至文件系统。
这种情况下，使用 `read_file` 分块查看保存的结果；若你需要在转存结果中搜索但不清楚具体路径，
可在 `/large_tool_results/` 目录下使用 `grep`。转存的工具结果会存储在 `/large_tool_results/<tool_call_id>` 路径下。

## 执行工具 `execute`

你可以使用 `execute` 工具在沙箱环境中运行 Shell 命令，linux下的shell一般为Bash，windows下的shell为一般为CMD，已知当前沙盒环境为{sandbox_type}。
使用该工具运行指令、脚本、测试、构建操作及其他 Shell 相关任务。

- execute：在当前沙箱中运行 Shell 命令（返回stdout+stderr与退出码）"""

MY_WRITE_FILE_TOOL_DESCRIPTION = """
Writes to a new file in the filesystem.
Usage:
- The write_file tool will create the a new file.
- Prefer to edit existing files (with the edit_file tool) over creating new ones when possible.
- **分段创建长文档**：禁止一次性调用该工具生成长文档，而是应该先调用该工具一次以创建文档骨架（包含文档元数据和所有章节标题），之后再多次调用edit_file tool逐个章节填充内容，每次将章节标题替换为完整章节。 
- 若不知道当前创建的是否为长文档，就默认使用分段创建方式。"""

# 开发新任务时，将新任务工作空间挂载到该目录下
CONTEXT_MOUNT_PATH_PREFIX_OF_NEW_TASK_CONTEXT_BOX = {
    "linux": "/tmp/persistent/agent_workspace/warehouse",
    "windows": "C:/tmp/persistent/agent_workspace/warehouse"
}

# 下面是从远程沙箱下载成果物到本地机器时的相关配置
TEXT_FILE_EXTENSIONS = {
    '.txt', '.md', '.py', '.js', '.ts', '.html', '.css', '.json', '.yaml', '.yml',
    '.xml', '.csv', '.log', '.ini', '.cfg', '.conf', '.sh', '.bat'
}
EXCLUDED_DIRS = {
    '__pycache__',
    '.pytest_cache',
    'node_modules',
    'dist',
    'build',
    '.git',
    '.venv',
    'venv',
    'env',
    '.idea',
    '.vscode',
    '*.egg-info',
}
EXCLUDED_FILE_EXTENSIONS = {
    '.pyc',
    '.pyo',
    '.pyd',
    '.so',
    '.dll',
    '.exe',
    '.log',
    '.tmp',
    '.temp',
    '.swp',
    '.swo',
    '.DS_Store',
    '.coverage',
}
PRESERVED_HIDDEN_FILES = {'.env', '.gitignore', '.dockerignore'}

AGENTBAY_IMAGE_ID = "imgc-0a8urjag1l02wa4og"
AGENTBAY_MCP_SERVER_NAME = "sandbox"
