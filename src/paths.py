from pathlib import Path

SRC_DIR = Path(__file__).parent

# 项目根目录
PROJECT_ROOT_DIR = SRC_DIR.parent

# .env 文件路径
DOT_ENV_FILE = PROJECT_ROOT_DIR / ".env"

# 数据集路径
DATASETS_PATH = PROJECT_ROOT_DIR / "datasets"

# 智能体提示词文件路径
PROMPTS_DIR = SRC_DIR / "prompts_md_files"
DEEP_AGENT_SYSTEM_PROMPTS_FILES = PROMPTS_DIR / "deep_agent_based_dev_team"
AGENT_SYSTEM_PROMPTS_FILES = PROMPTS_DIR / "agent_based_dev_team"

# 本地智能体团队的本地工作空间和项目仓库路径
LOCAL_AGENT_WORKSPACE = PROJECT_ROOT_DIR / "local_agent_workspace"

# 本地智能体团队的技能文件路径
DEV_TEAM_SKILLS_PATH = LOCAL_AGENT_WORKSPACE / "skills"

# agentbay_based_dev_team的提示词文件路径
AGENTBAY_SYSTEM_PROMPTS_FILES = PROMPTS_DIR / "agentbay_based_dev_team"

# agentbay_based_dev_team子包目录
AGENTBAY_BASED_DEV_TEAM_PATH = SRC_DIR / "remote_dev_team"

# 注册用户提交的软件开发任务
USER_SOFTWARE_DEV_TASKS_PATH = AGENTBAY_BASED_DEV_TEAM_PATH / "registered_tasks"

# agentbay_based_agent的资源文件路径
AGENTBAY_BASED_AGENT_RESOURCES_PATH = AGENTBAY_BASED_DEV_TEAM_PATH / "agent_resources"

# 仓库路径
LOCAL_PROJECTS_WAREHOUSE_FOR_REMOTE_TASK_RESULT = AGENTBAY_BASED_DEV_TEAM_PATH / "warehouse"

# 日志文件路径
LOG_PATH = AGENTBAY_BASED_DEV_TEAM_PATH / "my_logs"
