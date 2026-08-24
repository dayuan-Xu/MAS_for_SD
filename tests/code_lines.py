import os
from pathlib import Path


def count_lines(directory, extensions):
    """统计目录下指定扩展名文件的行数"""
    total_lines = 0
    total_files = 0
    file_stats = []

    for root, dirs, files in os.walk(directory):
        dirs[:] = [
            d
            for d in dirs
            if d not in ["__pycache__", "node_modules", ".cache", "build", ".git"]
        ]

        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_path = Path(root) / file
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        line_count = len(lines)
                        total_lines += line_count
                        total_files += 1
                        file_stats.append((str(file_path), line_count))
                except Exception as e:
                    print(f"读取文件失败 {file_path}: {e}")

    return total_files, total_lines, file_stats


def print_stats(name, directory, extensions, base_path):
    """打印统计信息"""
    total_files, total_lines, file_stats = count_lines(directory, extensions)
    file_stats.sort(key=lambda x: x[1], reverse=True)

    print(f"\n{'=' * 70}")
    print(f"{name}")
    print(f"{'=' * 70}")
    print(f"目录: {directory}")
    print(f"总文件数: {total_files}")
    print(f"总行数: {total_lines}")
    print(f"\n前10个大文件:")
    print(f"{'-' * 70}")
    for i, (filepath, count) in enumerate(file_stats[:10], 1):
        rel_path = filepath.replace(base_path, "").lstrip("\\")
        print(f"{i:2d}. {count:5d} 行 - {rel_path}")

    return total_files, total_lines


if __name__ == "__main__":
    base_dir = r"D:\Python\VS Code WorkSpace\MAS_for_SD"

    frontend_dir = os.path.join(base_dir, "frontend")
    backend_dir = os.path.join(base_dir, "backend")
    src_dir = os.path.join(base_dir, "src")

    frontend_files, frontend_lines = print_stats(
        "前端代码行数统计 (React/JavaScript)",
        frontend_dir,
        [".js", ".jsx", ".ts", ".tsx", ".vue"],
        base_dir,
    )

    backend_files, backend_lines = print_stats(
        "后端代码行数统计 (Python)", backend_dir, [".py"], base_dir
    )

    src_files, src_lines = print_stats(
        "后端依赖的src模块代码行数统计 (Python)", src_dir, [".py"], base_dir
    )

    total_backend_lines = backend_lines + src_lines
    total_backend_files = backend_files + src_files

    print(f"\n{'=' * 70}")
    print("汇总统计")
    print(f"{'=' * 70}")
    print(f"{'前端':　<20} 文件数: {frontend_files:>5}  行数: {frontend_lines:>6}")
    print(
        f"{'后端 (含src)':　<20} 文件数: {total_backend_files:>5}  行数: {total_backend_lines:>6}"
    )
    print(
        f"{'  - 后端本身':　<20} 文件数: {backend_files:>5}  行数: {backend_lines:>6}"
    )
    print(f"{'  - src模块':　<20} 文件数: {src_files:>5}  行数: {src_lines:>6}")
    print(f"{'-' * 70}")
    print(
        f"{'总计':　<20} 文件数: {frontend_files + total_backend_files:>5}  行数: {frontend_lines + total_backend_lines:>6}"
    )
    print(f"{'=' * 70}")
