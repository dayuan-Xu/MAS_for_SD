"""ContextBoxManager 快速测试脚本。

用于快速验证 ContextBoxManager 的基本功能。
"""

from pathlib import Path
from src.utils.context_box import ContextBoxManager


def main():
    """运行快速测试。"""
    print("=" * 60)
    print("ContextBoxManager 快速测试")
    print("=" * 60)
    
    # 创建管理器
    manager = ContextBoxManager()
    print(f"\n✅ {manager}")
    
    # 1. 列出所有 Context
    print("\n" + "-" * 60)
    print("1. 列出所有 Context Box")
    print("-" * 60)
    contexts = manager.list_all_contexts(max_results=5)
    
    if not contexts:
        print("⚠️  没有找到任何 Context Box")
        return
    
    print(f"\n找到 {len(contexts)} 个 Context Box:")
    for i, ctx in enumerate(contexts, 1):
        print(f"\n  [{i}] ID: {ctx.id}")
        print(f"      Name: {ctx.name}")
        print(f"      Created: {ctx.created_at}")
        print(f"      Last Used: {ctx.last_used_at}")
    
    # 2. 测试获取第一个 Context
    print("\n" + "-" * 60)
    print("2. 根据 ID 获取 Context")
    print("-" * 60)
    test_context_id = contexts[0].id
    print(f"\n尝试获取 Context (ID: {test_context_id})...")
    
    context = manager.get_context_by_id(test_context_id)
    if context:
        print(f"✅ 成功获取 Context:")
        print(f"   - Name: {context.name}")
        print(f"   - ID: {context.id}")
        print(f"   - Created: {context.created_at}")
    else:
        print("❌ 获取失败")
        return
    
    # 3. 列出文件
    print("\n" + "-" * 60)
    print("3. 列出 Context 文件结构")
    print("-" * 60)
    print(f"\n根目录 (/) 下的内容:")
    
    files = manager.list_context_files(context.id, "/", page_size=20)
    
    if not files:
        print("  (空目录)")
    else:
        print(f"  共 {len(files)} 个条目:\n")
        for file_entry in files[:15]:  # 只显示前 15 个
            icon = "📁" if file_entry.file_type == "folder" else "📄"
            size_str = f"{file_entry.size:,} bytes" if file_entry.size else "N/A"
            print(f"  {icon} {file_entry.file_path}")
            print(f"     Type: {file_entry.file_type}, Size: {size_str}")
        
        if len(files) > 15:
            print(f"\n  ... 还有 {len(files) - 15} 个条目未显示")
    
    # 4. 获取详细信息
    print("\n" + "-" * 60)
    print("4. 获取 Context 详细信息")
    print("-" * 60)
    
    info = manager.get_context_info(context.id)
    if info:
        print(f"\n  Context 信息:")
        for key, value in info.items():
            print(f"    {key}: {value}")
    
    # 5. 可选：下载文件测试（需要用户确认）
    print("\n" + "-" * 60)
    print("5. 下载文件测试（可选）")
    print("-" * 60)
    
    response = input("\n是否要测试下载文件到本地？(y/n，默认 n): ").strip().lower()
    
    if response == 'y':
        local_dir = Path("./test_context_download")
        print(f"\n开始下载文件到: {local_dir}")
        
        try:
            count = manager.download_all_files(
                context_id=context.id,
                remote_root_path="/",
                local_download_dir=local_dir,
                overwrite=True
            )
            print(f"\n✅ 成功下载 {count} 个文件到 {local_dir}")
            
            # 显示下载的目录结构
            print(f"\n本地目录结构:")
            for item in local_dir.rglob("*"):
                if item.is_file():
                    rel_path = item.relative_to(local_dir)
                    print(f"  📄 {rel_path}")
                elif item.is_dir():
                    rel_path = item.relative_to(local_dir)
                    print(f"  📁 {rel_path}/")
                    
        except Exception as e:
            print(f"\n❌ 下载失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("\n⏭️  跳过下载测试")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
