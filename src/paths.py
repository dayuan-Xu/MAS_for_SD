from pathlib import Path

SRC_DIR = Path(__file__).parent

# 项目根目录
PROJECT_ROOT_DIR = SRC_DIR.parent

# 日志文件路径
LOG_PATH = PROJECT_ROOT_DIR / "logs"

# .env 文件路径
DOT_ENV_FILE = PROJECT_ROOT_DIR / ".env"

# 数据集路径
DATASETS_PATH = PROJECT_ROOT_DIR / "datasets"

# 智能体提示词文件路径
PROMPTS_DIR = SRC_DIR / "prompts_md_files"

# agent_team的提示词文件路径
AGENT_SYSTEM_PROMPTS_FILES = PROMPTS_DIR / "agent"

# agentbay_based_dev_team子包目录
DEV_TEAM_PATH = SRC_DIR / "dev_team"

# 注册用户提交的软件开发任务
REGISTERED_TASKS_PATH = PROJECT_ROOT_DIR / "registered_tasks"

# agent的资源文件路径
AGENT_RESOURCES_PATH = DEV_TEAM_PATH / "agent_resources"

# 仓库路径
LOCAL_WAREHOUSE_FOR_TASK_RESULT = PROJECT_ROOT_DIR / "warehouse"

# 数据集文件路径
SOFTWARE_DEV_7_PATH = DATASETS_PATH / "software_dev_7.yaml"
