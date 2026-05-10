"""
系统提示词管理器模块

提供懒加载、缓存机制来管理角色提示词文件。
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict

from src.paths import PROMPTS_DIR

logger = logging.getLogger(__name__)

# 全局提示词目录（用于缓存键）
_PROMPTS_DIR = PROMPTS_DIR

# 确保目录存在（模块加载时执行一次）
_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)


def list_available_roles(prompts_dir: Path = _PROMPTS_DIR) -> list:
    """
    扫描指定目录下的所有 md 文件，列出所有可用的角色

    Args:
        prompts_dir: 提示词文件目录

    Returns:
        角色名称列表
    """
    if not prompts_dir.exists():
        return []

    return [
        file.stem
        for file in prompts_dir.glob("*.md")
        if file.is_file()
    ]


@lru_cache(maxsize=None)
def get_system_prompt(role: str, prompts_dir: Path = _PROMPTS_DIR) -> str:
    """
    懒加载获取指定角色的系统提示词

    Args:
        role: 角色、身份 (team_leader, product_manager, architect,
                   project_manager, engineer, qa_engineer)
        prompts_dir: 提示词文件目录

    Returns:
        角色对应的系统提示词内容

    Raises:
        FileNotFoundError: 当提示词文件不存在时
        UnicodeDecodeError: 当文件编码错误时
    """
    prompt_file = prompts_dir / f"{role}.md"

    if not prompt_file.exists():
        available_roles = list_available_roles(prompts_dir)
        raise FileNotFoundError(
            f"Role prompt file not found: {prompt_file}\n"
            f"Available roles: {available_roles}"
        )

    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError as e:
        logger.error(f"Failed to read prompt file {prompt_file}: {e}")
        raise


# 获取某些角色系统提示词
@lru_cache(maxsize=None)
def get_system_prompts_for_roles(role_names: tuple, prompts_dir: Path = _PROMPTS_DIR) -> Dict[str, str]:
    """
    获取指定角色的系统提示词

    Args:
        role_names: 角色名称列表
        prompts_dir: 提示词文件目录

    Returns:
        包含指定角色提示词的字典
    """
    return {
        role_name: get_system_prompt(role_name, prompts_dir)
        for role_name in role_names
    }


@lru_cache(maxsize=1)
def get_all_system_prompts(prompts_dir: Path = _PROMPTS_DIR) -> Dict[str, str]:
    """
    获取所有角色的系统提示词（带缓存）

    Args:
        prompts_dir: 提示词文件目录

    Returns:
        包含所有角色提示词的字典
    """
    roles = list_available_roles(prompts_dir)

    return {
        role: get_system_prompt(role, prompts_dir)
        for role in roles
    }
