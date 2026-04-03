from pathlib import Path

# 项目根目录（整个项目唯一的路径基准）
ROOT_DIR = Path(__file__).parent.parent
DEEP_AGENT_WORKSPACE = ROOT_DIR / "DeepAgent_workspace"
DOT_ENV_FILE = ROOT_DIR / ".env"

DEEP_AGENT_SYSTEM_PROMPTS_FILES = ROOT_DIR / "src" / "Virtual_SD_Team" / "prompts_md_files" / "Deep_Agent_Dev_Team"
