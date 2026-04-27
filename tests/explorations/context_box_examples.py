"""ContextBoxManager 使用示例。

展示如何使用 ContextBoxManager 进行常见的操作。
"""

from pathlib import Path
from src.utils.context_box import ContextBoxManager


def example_list_all_contexts():
    """示例1: 列出所有 Context Box"""
    print("=" * 60)
    print("示例1: 列出所有 Context Box")
    print("=" * 60)
    
    manager = ContextBoxManager()
    contexts = manager.list_all_contexts(max_results=10)
    
    print(f"\n找到 {len(contexts)} 个 Context Box:\n")
    for i, ctx in enumerate(contexts, 1):
        print(f"{i}. ID: {ctx.id}")
        print(f"   Name: {ctx.name}")
        print(f"   Created: {ctx.created_at}")
        print(f"   Last Used: {ctx.last_used_at}")
        print()


def example_get_context_by_id():
    """示例2: 根据 ID 获取 Context"""
    print("=" * 60)
    print("示例2: 根据 ID 获取 Context")
    print("=" * 60)
    
    manager = ContextBoxManager()
    
    # 替换为你实际的 Context ID
    context_id = "SdkCtx-04poml0ue21och2li"
    
    print(f"\n尝试获取 Context (ID: {context_id})...\n")
    context = manager.get_context_by_id(context_id)
    
    if context:
        print(f"✅ 成功获取 Context:")
        print(f"   - Name: {context.name}")
        print(f"   - ID: {context.id}")
        print(f"   - Created: {context.created_at}")
        print(f"   - Last Used: {context.last_used_at}")
    else:
        print(f"❌ 未找到 ID 为 {context_id} 的 Context")


def example_browse_files():
    """示例3: 浏览 Context 文件结构"""
    print("=" * 60)
    print("示例3: 浏览 Context 文件结构")
    print("=" * 60)
    
    manager = ContextBoxManager()
    
    # 先获取一个 Context
    contexts = manager.list_all_contexts(max_results=1)
    if not contexts:
        print("⚠️  没有找到任何 Context")
        return
    
    context = contexts[0]
    print(f"\n浏览 Context: {context.name} (ID: {context.id})\n")
    
    # 列出根目录
    print("根目录 (/) 内容:")
    files = manager.list_context_files(context.id, "/", page_size=20)
    
    if not files:
        print("  (空目录)")
    else:
        for file_entry in files:
            icon = "📁" if file_entry.file_type == "folder" else "📄"
            size_str = f"{file_entry.size:,} bytes" if file_entry.size else "N/A"
            print(f"  {icon} {file_entry.file_path}")
            print(f"     Type: {file_entry.file_type}, Size: {size_str}")
    
    # 如果有子目录，可以递归浏览
    folders = [f for f in files if f.file_type == "folder"]
    if folders:
        print(f"\n\n第一个子目录 ({folders[0].file_path}) 内容:")
        sub_files = manager.list_context_files(
            context.id, 
            folders[0].file_path, 
            page_size=10
        )
        for file_entry in sub_files[:5]:  # 只显示前5个
            print(f"  - {file_entry.file_path}")


def example_download_files():
    """示例4: 下载 Context 文件到本地"""
    print("=" * 60)
    print("示例4: 下载 Context 文件到本地")
    print("=" * 60)
    
    manager = ContextBoxManager()
    
    # 先获取一个 Context
    contexts = manager.list_all_contexts(max_results=1)
    if not contexts:
        print("⚠️  没有找到任何 Context")
        return
    
    context = contexts[0]
    
    # 设置本地下载目录
    local_dir = Path("./context_downloads") / context.name
    
    print(f"\n开始下载 Context 文件...")
    print(f"  Context: {context.name}")
    print(f"  本地目录: {local_dir}")
    print()
    
    # 下载所有文件
    count = manager.download_all_files(
        context_id=context.id,
        remote_root_path="/",
        local_download_dir=local_dir,
        overwrite=False  # 不覆盖已存在的文件
    )
    
    print(f"\n✅ 下载完成!")
    print(f"   成功下载: {count} 个文件")
    print(f"   保存位置: {local_dir.absolute()}")
    
    # 显示下载的目录结构（前10个文件）
    print(f"\n本地目录结构（前10个文件）:")
    for i, item in enumerate(local_dir.rglob("*"), 1):
        if i > 10:
            print(f"  ... 还有更多文件")
            break
        
        if item.is_file():
            rel_path = item.relative_to(local_dir)
            size = item.stat().st_size
            print(f"  📄 {rel_path} ({size:,} bytes)")
        elif item.is_dir():
            rel_path = item.relative_to(local_dir)
            print(f"  📁 {rel_path}/")


def example_get_context_info():
    """示例5: 获取 Context 详细信息"""
    print("=" * 60)
    print("示例5: 获取 Context 详细信息")
    print("=" * 60)
    
    manager = ContextBoxManager()
    
    # 先获取一个 Context
    contexts = manager.list_all_contexts(max_results=1)
    if not contexts:
        print("⚠️  没有找到任何 Context")
        return
    
    context = contexts[0]
    
    print(f"\n获取 Context 详细信息 (ID: {context.id})...\n")
    
    info = manager.get_context_info(context.id)
    
    if info:
        print("Context 信息:")
        print("-" * 40)
        for key, value in info.items():
            print(f"  {key:20s}: {value}")
    else:
        print("❌ 无法获取 Context 信息")


def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("ContextBoxManager 使用示例集合")
    print("=" * 60 + "\n")
    
    # 运行各个示例
    try:
        example_list_all_contexts()
        print("\n")
        
        example_get_context_by_id()
        print("\n")
        
        example_browse_files()
        print("\n")
        
        example_get_context_info()
        print("\n")
        
        # 下载示例需要较长时间，可以选择性运行
        response = input("是否运行下载示例？(y/n，默认 n): ").strip().lower()
        if response == 'y':
            example_download_files()
        
    except Exception as e:
        print(f"\n❌ 示例运行出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
