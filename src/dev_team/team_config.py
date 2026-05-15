# 本模块保存agentbay based agent的一些配置信息
from deepagents.backends import FilesystemBackend

from src.paths import AGENT_RESOURCES_PATH

AGENT_SKILL_PATH = AGENT_RESOURCES_PATH / "skills"
AGENT_MEMORY_PATH = AGENT_RESOURCES_PATH / "memory"

# 将智能体对不同路径的文件操作路由到不同的后端
MY_COMPOSITE_BACKEND_ROUTES = {
    "windows": {
        "C:/tmp/persistent/agent_workspace/skills/": FilesystemBackend(root_dir=AGENT_SKILL_PATH,
                                                                       virtual_mode=True),
        "C:/tmp/persistent/agent_workspace/memory/": FilesystemBackend(root_dir=AGENT_MEMORY_PATH,
                                                                       virtual_mode=True),
    },
    "linux": {
        "/tmp/persistent/agent_workspace/skills/": FilesystemBackend(root_dir=AGENT_SKILL_PATH,
                                                                     virtual_mode=True),
        "/tmp/persistent/agent_workspace/memory/": FilesystemBackend(root_dir=AGENT_MEMORY_PATH,
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
    "windows": "C:/tmp/persistent/agent_workspace/skills/engineer"
}

QA_ENGINEER_SKILL_PATH = {
    "linux": "/tmp/persistent/agent_workspace/skills/QA_engineer",
    "windows": "C:/tmp/persistent/agent_workspace/skills/QA_engineer"
}

PLANNER_SKILL_PATH = {
    "linux": "/tmp/persistent/agent_workspace/skills/planner",
    "windows": "C:/tmp/persistent/agent_workspace/skills/planner"
}

BUILDER_SKILL_PATH = {
    "linux": "/tmp/persistent/agent_workspace/skills/builder",
    "windows": "C:/tmp/persistent/agent_workspace/skills/builder"
}

EVALUATOR_SKILL_PATH = {
    "linux": "/tmp/persistent/agent_workspace/skills/evaluator",
    "windows": "C:/tmp/persistent/agent_workspace/skills/evaluator"
}

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

MY_EXECUTE_TOOL_DESCRIPTION = """Executes a shell command in the sandbox environment.

Usage:
Executes a given command in the sandbox environment with proper handling and security measures.
Before executing the command, please follow these steps:
1. Directory Verification:
   - If the command will create new directories or files, first use the ls tool to verify the parent directory exists and is the correct location
   - For example, before running "mkdir foo/bar", first use ls to check that "foo" exists and is the intended parent directory
2. Command Execution:
   - Always quote file paths that contain spaces with double quotes (e.g., cd "path with spaces/file.txt")
   - Examples of proper quoting:
     - cd "/Users/name/My Documents" (correct)
     - cd /Users/name/My Documents (incorrect - will fail)
     - python "/path/with spaces/script.py" (correct)
     - python /path/with spaces/script.py (incorrect - will fail)
   - After ensuring proper quoting, execute the command
   - Capture the output of the command
Usage notes:
  - Commands run in an the sandbox environment
  - Returns combined stdout/stderr output with exit code
  - If the output is very large, it may be truncated
  - For long-running commands, use the timeout parameter to override the default timeout (e.g., execute(command="make build", timeout=300))
  - The default timeout is 50 seconds.
  - VERY IMPORTANT: You MUST avoid using search commands like find and grep. Instead use the grep, glob tools to search. You MUST avoid read tools like cat, head, tail, and use read_file to read files.
  - When issuing multiple commands, use the ';' or '&&' operator to separate them. DO NOT use newlines (newlines are ok in quoted strings)
    - Use '&&' when commands depend on each other (e.g., "mkdir dir && cd dir")
    - Use ';' only when you need to run commands sequentially but don't care if earlier commands fail
  - Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of cd

Examples:
  Good examples:
    - execute(command="pytest /foo/bar/tests")
    - execute(command="python /path/to/script.py")
    - execute(command="npm install && npm test", timeout=300)
    - execute(command="make build", timeout=300)

  Bad examples (avoid these):
    - execute(command="cd /foo/bar && pytest tests")  # Use absolute path instead
    - execute(command="cat file.txt")  # Use read_file tool instead
    - execute(command="find . -name '*.py'")  # Use glob tool instead
    - execute(command="grep -r 'pattern' .")  # Use grep tool instead

Note: Remember set the appropriate timeout for long-running commands."""

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

AGENTBAY_IMAGE_ID = "imgc-0aae4rgke8zkhucji"
AGENTBAY_MCP_SERVER_NAME = "sandbox"

SHARED_INFORMATION_AFTER_SYSTEM_PROMPT = {
    # 3人团队
    "simple": """
## 团队成员
1. 当前团队人数：3
2. Planner Alice：负责用户原始需求接收，创建SOFTWARE_DEFINITION.md、TASKS.md，以及指派Builder Bob进行软件功能点开发；仅能和用户、Bob交互。
3. Builder Bob：负责从Alice处接收软件功能点开发请求，实现软件功能点；仅能和Alice、Eva交互。
4. Evaluator Eva：负责评审Bob对每个软件功能点提出的验收标准提议和其具体实现；仅能和Bob交互。

## 团队工作环境 
1. 已知每次团队进行软件开发任务的环境，是一个具备图形化界面的计算机沙箱。
2. 该沙盒ID是sandbox id="{sandbox_id}"，所以当调用那些需要传入sandbox id的工具的时候，**可以并且只能**使用该sandbox id。
3. 本次软件开发任务仅允许基于当前这个已有沙箱（sandbox id="{sandbox_id}"），**禁止**调用 create_sandbox 新建任何其他sandbox。

## 项目工作空间
- 项目工作空间路径：对于每个项目，其所有项目文件必须存放在 `/tmp/persistent/agent_workspace/warehouse/{{project_name}}/` 目录下
- 项目名通常使用蛇形命名法（snake_case），例如：`tank_battle_game`、`flappy_bird`
- 完整示例：`/tmp/persistent/agent_workspace/warehouse/tank_battle_game/`

## 标准目录结构
/tmp/persistent/agent_workspace/warehouse/{{project_name}}/
├── docs/              # 存放除了README.md外的所有文档
├── src/               # 源代码目录（根据技术栈可能不同）
├── tests/             # 测试代码目录
└── README.md          # 项目说明文档

## 特殊文件
- `/tmp/persistent/agent_workspace/warehouse/{{project_name}}/docs/SOFTWARE_DEFINITION.md`用于记录用户原始需求和软件整体功能定义，仅由Alice创建，其他成员只读不能写！
- `/tmp/persistent/agent_workspace/warehouse/{{project_name}}/docs/TASKS.md`用于定义软件功能点列表，由Alice负责创建（创建后只能读不能写），由Eva负责维护（更新）每个功能点状态，Bob只能读不能写！

## 工具使用原则
1. 绝不调用那些会返回无法解读信息的工具，尤其是snapshot、screenshot这类返回base64编码字符串的截图工具，避免摄入大量无用信息。
2. 若想调用的某个工具返回效果不理想，你可以自己编写python脚本并且通过`execute`工具执行。

## 异常情况处理
1. 若`/tmp/persistent/agent_workspace/`下不存在项目工作空间，则应该停止工作并主动汇报"{exception_identifier}：项目工作空间不存在，拒绝继续执行"。
2. 若当前sandbox id为None，则应该主动汇报"{exception_identifier}：沙盒ID异常，拒绝继续执行"。
3. 若出现“沙盒会话即将达到最大运行时间限制！”情况，工作中的Eva应该停止工作并向Bob汇报，工作中的Bob应该停止工作并向Alice汇报，工作中的Alice应该停止工作并向用户汇报"{exception_identifier}：沙盒会话已经断开"。
""",

    # 双人团队
    "dual": """
    
""",
    # 单人团队
    "single": """

""",
}

# 自动开发的配置
TASK_DONE_IDENTIFIER = "TASK_DONE"
TASK_REJECTED_IDENTIFIER = "REQUEST_REJECTED"
EXCEPTION_IDENTIFIER = "EXCEPTION"
MAX_REACT_LOOP_COUNT = 5  # dev_team最多运行5次
