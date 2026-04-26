import os
from pathlib import Path


def print_project_tree(
    root_path: str = ".",
    max_depth: int = 5,
    show_files: bool = True,
    file_patterns: list = None
):
    """
    树形打印 Python 项目结构，自动忽略不必要的目录和文件

    Args:
        root_path: 项目根路径，默认为当前目录
        max_depth: 最大递归深度，默认 5 层
        show_files: 是否显示文件，默认 True
        file_patterns: 要显示的文件模式列表，如 ['*.py', '*.json', '*.yaml']，None 表示显示所有文件

    自动忽略的目录:
        - 虚拟环境：.venv, venv, env, .env
        - IDE 配置：.idea, .vscode, *.iml
        - 缓存目录：__pycache__, .pytest_cache, .langgraph_api, .mypy_cache
        - Git 相关：.git
        - 其他：dist, build, node_modules
    """
    # 需要忽略的目录名
    ignore_dirs = {
        '.venv', 'venv', 'env', '.env',
        '__pycache__', '.pytest_cache', '.langgraph_api', '.mypy_cache',
        '.git', '.hg', '.svn',
        'dist', 'build', 'node_modules', '.eggs', '*.egg-info',
        '.tox', '.coverage', 'htmlcov', '.hypothesis'
    }

    # 需要忽略的文件模式
    ignore_file_patterns = {
        '*.pyc', '*.pyo', '*.pyd', '.DS_Store', '*.so', '.gitignore'
    }

    # IDE 配置文件
    ignore_files = {
        '.idea', '.vscode', '.vim', '.emacs.d', '.vs',
        '*.iml', '.project', '.classpath'
    }

    if file_patterns is None:
        file_patterns = ['*.py', '*.md', '*.txt', '*.json', '*.yaml', '*.yml', '*.toml', '*.cfg', '*.ini']

    root = Path(root_path).resolve()

    def should_ignore_dir(dir_name: str) -> bool:
        """判断是否应该忽略该目录"""
        return dir_name in ignore_dirs or dir_name.startswith('.')

    def should_ignore_file(file_name: str) -> bool:
        """判断是否应该忽略该文件"""
        if file_name in ignore_files:
            return True
        for pattern in ignore_file_patterns:
            if pattern.startswith('*'):
                if file_name.endswith(pattern[1:]):
                    return True
        return False

    def should_show_file(file_name: str) -> bool:
        """判断是否应该显示该文件"""
        if should_ignore_file(file_name):
            return False
        if not file_patterns:
            return True
        for pattern in file_patterns:
            if pattern.startswith('*'):
                if file_name.endswith(pattern[1:]):
                    return True
            elif file_name == pattern:
                return True
        return False

    def get_tree_string(path: Path, prefix: str = "", depth: int = 0) -> str:
        """递归生成树形结构字符串"""
        if depth > max_depth:
            return ""

        result = []

        # 获取所有子项
        try:
            items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return f"{prefix}{path.name}/ (无权限访问)\n"

        # 过滤掉需要忽略的目录和文件
        filtered_items = []
        for item in items:
            if item.is_dir():
                if not should_ignore_dir(item.name):
                    filtered_items.append(item)
            elif show_files and should_show_file(item.name):
                filtered_items.append(item)

        # 生成当前层的树形结构
        for i, item in enumerate(filtered_items):
            is_last = i == len(filtered_items) - 1

            if item.is_dir():
                # 目录
                result.append(f"{prefix}{'└── ' if is_last else '├── '}{item.name}/\n")
                # 递归处理子目录
                extension = "│   " if not is_last else "    "
                result.append(get_tree_string(item, prefix + extension, depth + 1))
            else:
                # 文件
                result.append(f"{prefix}{'└── ' if is_last else '├── '}{item.name}\n")

        return "".join(result)

    # 打印根目录
    print(f"{root.name}/")
    # 打印树形结构
    tree_str = get_tree_string(root, depth=0)
    print(tree_str, end='')


# 使用示例
if __name__ == "__main__":
    # 示例 1: 打印当前项目结构
    print("=" * 60)
    print("项目结构:")
    print("=" * 60)
    print_project_tree(".")

    # 示例 2: 只打印 Python 文件
    print("\n" + "=" * 60)
    print("仅显示 Python 文件:")
    print("=" * 60)
    print_project_tree(".", file_patterns=['*.py'])

    # 示例 3: 指定最大深度
    print("\n" + "=" * 60)
    print("最大深度为 3:")
    print("=" * 60)
    print_project_tree(".", max_depth=3)

