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

# 智能体的工作空间和项目仓库路径
LOCAL_AGENT_WORKSPACE = PROJECT_ROOT_DIR / "local_agent_workspace"
PROJECTS_WAREHOUSE_BY_AGENTS = LOCAL_AGENT_WORKSPACE / "warehouse"

# 用户提交的软件开发任务
USER_SOFTWARE_DEV_TASKS_PATH = PROJECT_ROOT_DIR / "user_tasks"

DEV_TEAM_SKILLS_PATH = LOCAL_AGENT_WORKSPACE / "skills"
