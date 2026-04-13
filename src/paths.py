from pathlib import Path

SRC_DIR = Path(__file__).parent

ROOT_DIR = SRC_DIR.parent  # 项目根目录
AGENT_WORKSPACE = ROOT_DIR / "agent_workspace"
DOT_ENV_FILE = ROOT_DIR / ".env"

PROMPTS_DIR = SRC_DIR / "prompts_md_files"

DEEP_AGENT_SYSTEM_PROMPTS_FILES = PROMPTS_DIR / "deep_agent_based_dev_team"
AGENT_SYSTEM_PROMPTS_FILES = PROMPTS_DIR / "agent_based_dev_team"

DATASETS_PATH = ROOT_DIR / "datasets"
