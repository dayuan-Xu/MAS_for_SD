import os
from pathlib import Path


def count_python_lines(directory):
    """统计目录下所有Python文件的行数"""
    total_lines = 0
    total_files = 0
    file_stats = []

    for root, dirs, files in os.walk(directory):
        # 跳过 __pycache__ 和 langchain_learning 目录
        dirs[:] = [d for d in dirs if d not in ['__pycache__', 'langchain_learning']]

        for file in files:
            if file.endswith('.py'):
                file_path = Path(root) / file
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        line_count = len(lines)
                        total_lines += line_count
                        total_files += 1
                        file_stats.append((str(file_path), line_count))
                except Exception as e:
                    print(f"读取文件失败 {file_path}: {e}")

    # 按行数排序
    file_stats.sort(key=lambda x: x[1], reverse=True)

    print(f"\n{'=' * 60}")
    print(f"SRC 目录 Python 源代码行数统计")
    print(f"{'=' * 60}")
    print(f"总文件数: {total_files}")
    print(f"总行数: {total_lines}")
    print(f"\n前20个大文件:")
    print(f"{'-' * 60}")
    for i, (filepath, count) in enumerate(file_stats[:20], 1):
        rel_path = filepath.replace(str(Path(directory)), 'src')
        print(f"{i:2d}. {count:5d} 行 - {rel_path}")

    return total_files, total_lines


if __name__ == "__main__":
    src_dir = r"D:\Python\VS Code WorkSpace\MAS_for_SD\src"
    count_python_lines(src_dir)
