import logging
import re
from pathlib import Path
from typing import Literal

from deepagents.backends.protocol import FileOperationError
from langchain_core.messages import AIMessage

from src.dev_team.team_config import EXCLUDED_DIRS, EXCLUDED_FILE_EXTENSIONS, PRESERVED_HIDDEN_FILES, \
    TEXT_FILE_EXTENSIONS, TASK_DONE_IDENTIFIER, TASK_REJECTED_IDENTIFIER

logger = logging.getLogger(__name__)


def get_time_str(elapsed_time: float) -> str:
    minutes = int(elapsed_time // 60)
    seconds = elapsed_time % 60
    if minutes > 0:
        time_str = f"{minutes}分{seconds:.1f}秒"
    else:
        time_str = f"{seconds:.1f}秒"
    return time_str


def to_snake_case(name: str) -> str:
    """将任务名称转换为蛇形命名（snake_case）。

    转换规则：
    1. 将所有字符转为小写
    2. 将空格、连字符等非字母数字字符替换为下划线
    3. 去除连续的下划线
    4. 去除首尾的下划线

    Args:
        name: 原始任务名称，如 "Snake game", "Excel data process"

    Returns:
        蛇形命名的字符串，如 "snake_game", "excel_data_process"

    Examples:
        >>> to_snake_case("Snake game")
        'snake_game'
        >>> to_snake_case("Excel data process")
        'excel_data_process'
        >>> to_snake_case("CRUD manage")
        'crud_manage'
    """
    # 转为小写
    name = name.lower()
    # 将空格、连字符等非字母数字字符替换为下划线
    name = re.sub(r'[^a-z0-9]+', '_', name)
    # 去除连续的下划线
    name = re.sub(r'_+', '_', name)
    # 去除首尾的下划线
    name = name.strip('_')
    return name


def should_skip_path(relative_path: Path) -> bool:
    """判断是否应该跳过该路径（不下载）。

    使用黑名单机制排除中间产物、缓存、临时文件等。

    Args:
        relative_path: 相对于任务根目录的路径

    Returns:
        bool: True 表示应该跳过，False 表示应该下载
    """
    name = relative_path.name

    # 检查是否在排除目录中
    for part in relative_path.parts:
        if part in EXCLUDED_DIRS:
            return True

    # 检查文件扩展名
    if name.endswith(tuple(EXCLUDED_FILE_EXTENSIONS)):
        return True

    # 特殊文件模式：排除隐藏文件（除了常见的配置文件）
    if name.startswith('.') and name not in PRESERVED_HIDDEN_FILES:
        return True

    return False


def write_content_to_file(local_path: Path, content: bytes) -> None:
    """将字节内容写入本地文件，根据文件类型自动选择文本或二进制模式。

    Args:
        local_path: 本地文件路径
        content: 文件内容（字节）
    """
    # 确保父目录存在
    local_path.parent.mkdir(parents=True, exist_ok=True)

    # 根据文件类型选择写入方式
    file_ext = local_path.suffix.lower()

    if file_ext in TEXT_FILE_EXTENSIONS:
        # 文本文件：尝试 UTF-8 解码
        try:
            local_path.write_text(content.decode('utf-8'), encoding='utf-8')
        except UnicodeDecodeError:
            # 如果解码失败，当作二进制文件处理
            local_path.write_bytes(content)
    else:
        # 二进制文件：直接写入 bytes
        local_path.write_bytes(content)


def process_command_parts(cmd):
    """处理命令字符串，在每个 python 子命令前添加 PYTHONUTF8=1"""
    # 匹配命令分隔符：&& || ; | （前后可能有空格）
    # 同时保留分隔符以便重组
    parts = re.split(r'(\s*[;&|]\s*)', cmd)

    result = []
    for i, part in enumerate(parts):
        # 如果是命令分隔符，直接添加
        if re.match(r'^\s*[;&|]\s*$', part):
            result.append(part)
        else:
            # 这是实际命令部分，检查是否以 python 开头
            stripped = part.strip()
            if stripped and not stripped.startswith('PYTHONUTF8='):
                # 检查是否以 python 或 python3 开头（忽略前导空格）
                if re.match(r'^python3?\b', stripped, re.IGNORECASE):
                    # 在 python 命令前添加 PYTHONUTF8=1
                    # 保持原有的前导空格
                    leading_spaces = len(part) - len(part.lstrip())
                    result.append(' ' * leading_spaces + f'PYTHONUTF8=1 {stripped}')
                else:
                    result.append(part)
            else:
                result.append(part)

    return ''.join(result)


def map_agentbay_error_to_file_operation_error(error_message: str) -> FileOperationError | Literal[
    "Empty error message", "File operation error parse failure"]:
    """将 AgentBay 的错误信息映射到标准的 FileOperationError 类型。
    
    Args:
        error_message: AgentBay 返回的错误信息
        
    Returns:
        标准化的 FileOperationError 类型
    """
    if not error_message:
        logger.error("无法映射错误信息到 FileOperationError: 错误信息为空")
        return "Empty error message"
    logger.debug(f"开始尝试映射错误信息到 FileOperationError")
    error_lower = error_message.lower()

    # 文件不存在相关错误
    if any(keyword in error_lower for keyword in [
        "not found", "no such file", "doesn't exist", "does not exist",
        "file not found", "path not found"
    ]):
        return "file_not_found"

    # 权限拒绝相关错误
    if any(keyword in error_lower for keyword in [
        "permission denied", "access denied", "forbidden",
        "unauthorized", "permission", "access"
    ]):
        return "permission_denied"

    # 目录相关错误
    if any(keyword in error_lower for keyword in [
        "is a directory", "is_directory", "directory",
        "expected file but got directory"
    ]):
        return "is_directory"

    # 路径无效相关错误
    if any(keyword in error_lower for keyword in [
        "invalid path", "invalid", "malformed",
        "bad path", "path syntax"
    ]):
        return "invalid_path"

    # 默认返回 file_not_found（最常见的错误）
    logger.error(f"无法映射错误信息到 FileOperationError。错误信息：\n{error_message}")
    return "File operation error parse failure"


def target_str_in_AIMessage(target: str, msg: AIMessage):
    """检查消息是否包含 TASK_DONE 标识"""
    content = msg.content
    # 情况1：纯字符串
    if isinstance(content, str):
        return target in content

    # 情况2：列表类型
    if isinstance(content, list):
        for item in content:
            # 子项是字符串
            if isinstance(item, str):
                if target in item:
                    return True
            # 子项是字典（OpenAI 消息格式）
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    text_content = item.get("text", "")
                    if target in text_content:
                        return True
                # 处理其他类型的 content（如 image_url 等）
                elif item.get("type"):
                    logger.warning(f"跳过非文本内容类型: {item.get('type')}")

    return False


def is_task_done(msg: AIMessage):
    """检查消息是否包含 TASK_DONE 标识"""
    return target_str_in_AIMessage(TASK_DONE_IDENTIFIER, msg)


def is_task_rejected(msg: AIMessage):
    """检查消息是否包含 TASK_REJECTED 标识"""
    return target_str_in_AIMessage(TASK_REJECTED_IDENTIFIER, msg)
