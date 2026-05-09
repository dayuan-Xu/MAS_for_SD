from pathlib import Path

from src.dev_team.team_config import EXCLUDED_DIRS, EXCLUDED_FILE_EXTENSIONS, PRESERVED_HIDDEN_FILES, \
    TEXT_FILE_EXTENSIONS


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
    import re
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
