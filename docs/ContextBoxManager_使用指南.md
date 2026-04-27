# ContextBoxManager 使用指南

## 概述

`ContextBoxManager` 是一个用于管理 AgentBay Context Box（持久化存储上下文）的工具类。它提供了完整的 Context Box 管理能力，包括查询、浏览和下载功能。

## 主要功能

1. **列出所有 Context Box** - 获取当前 API Key 下所有的 context box 及其元信息
2. **根据 ID 获取 Context** - 通过指定的 context id 获取 context 对象
3. **查看内部结构** - 浏览该 context box 的文件目录结构
4. **下载所有文件** - 将 context box 中的所有文件下载到本地

## 快速开始

### 基本用法

```python
from src.utils.context_box import ContextBoxManager

# 创建管理器实例
manager = ContextBoxManager()

# 1. 列出所有 Context Box
contexts = manager.list_all_contexts(max_results=10)
for ctx in contexts:
    print(f"ID: {ctx.id}, Name: {ctx.name}")

# 2. 根据 ID 获取 Context
context = manager.get_context_by_id("SdkCtx-04poml0ue21och2li")
if context:
    print(f"Context Name: {context.name}")
    
    # 3. 查看内部结构
    files = manager.list_context_files(context.id, "/")
    for file_entry in files:
        print(f"  - {file_entry.file_path} ({file_entry.size} bytes)")
    
    # 4. 下载所有文件到本地
    from pathlib import Path
    local_dir = Path("./downloaded_context")
    count = manager.download_all_files(context.id, "/", local_dir)
    print(f"下载了 {count} 个文件")
```

### 按名称获取 Context

```python
# 通过名称获取 Context
context = manager.get_context_by_name("my_task_context")
if context:
    print(f"找到 Context: {context.name} (ID: {context.id})")
```

### 获取 Context 详细信息

```python
# 获取 Context 的详细信息
info = manager.get_context_info("SdkCtx-04poml0ue21och2li")
if info:
    print(f"Context 信息:")
    for key, value in info.items():
        print(f"  {key}: {value}")
```

### 分页浏览文件

```python
# 分页浏览大目录中的文件
page_size = 50
files = manager.list_context_files(
    context_id="SdkCtx-xxx",
    parent_folder_path="/warehouse/my_task",
    page_size=page_size
)

print(f"共 {len(files)} 个文件/目录")
```

### 选择性下载

```python
from pathlib import Path

# 只下载特定目录下的文件
local_dir = Path("./my_downloads")
count = manager.download_all_files(
    context_id="SdkCtx-xxx",
    remote_root_path="/warehouse/my_task/src",  # 只下载 src 目录
    local_download_dir=local_dir,
    overwrite=True  # 覆盖已存在的文件
)
```

## API 参考

### ContextBoxManager 类

#### `__init__(api_key: str = settings.WUYING_AGENTBAY_API_KEY)`

初始化 ContextBoxManager。

**参数:**
- `api_key`: AgentBay API 密钥，默认从 settings 中读取

#### `list_all_contexts(max_results: int = 100, session_id: Optional[str] = None) -> List[Context]`

列出当前 API Key 下的所有 Context Box。

**参数:**
- `max_results`: 最大返回数量，默认 100
- `session_id`: 可选，按 Session ID 过滤

**返回:**
- `List[Context]`: Context 对象列表，包含 id, name, created_at, last_used_at 等元信息

#### `get_context_by_id(context_id: str) -> Optional[Context]`

根据 Context ID 获取 Context 对象。

**参数:**
- `context_id`: Context 的唯一标识符，如 "SdkCtx-04poml0ue21och2li"

**返回:**
- `Optional[Context]`: Context 对象，如果不存在则返回 None

#### `get_context_by_name(name: str) -> Optional[Context]`

根据 Context 名称获取 Context 对象。

**参数:**
- `name`: Context 的名称

**返回:**
- `Optional[Context]`: Context 对象，如果不存在则返回 None

#### `list_context_files(context_id: str, parent_folder_path: str = "/", page_size: int = 50) -> List[ContextFileEntry]`

列出 Context Box 中指定目录下的文件和子目录。

**参数:**
- `context_id`: Context 的唯一标识符
- `parent_folder_path`: 父目录路径，默认为根目录 "/"
- `page_size`: 每页返回的文件数量，默认 50

**返回:**
- `List[ContextFileEntry]`: 文件条目列表，包含以下属性：
  - `file_id`: 文件 ID
  - `file_name`: 文件名
  - `file_path`: 文件路径
  - `file_type`: 文件类型 ("file" 或 "folder")
  - `size`: 文件大小（字节）
  - `gmt_create`: 创建时间
  - `gmt_modified`: 修改时间
  - `status`: 状态

#### `download_all_files(context_id: str, remote_root_path: str = "/", local_download_dir: Path = None, overwrite: bool = False) -> int`

下载 Context Box 中的所有文件到本地目录。

**参数:**
- `context_id`: Context 的唯一标识符
- `remote_root_path`: 远程根目录路径，默认为 "/"
- `local_download_dir`: 本地下载目标目录，如果为 None 则使用当前工作目录下的 "context_downloads/{context_id}" 目录
- `overwrite`: 是否覆盖已存在的文件，默认 False（跳过已存在文件）

**返回:**
- `int`: 成功下载的文件数量

#### `get_context_info(context_id: str) -> Optional[dict]`

获取 Context 的详细信息。

**参数:**
- `context_id`: Context ID

**返回:**
- `Optional[dict]`: 包含 Context 详细信息的字典，包括：
  - `id`: Context ID
  - `name`: Context 名称
  - `created_at`: 创建时间
  - `last_used_at`: 最后使用时间
  - `has_files`: 是否包含文件

## 测试

运行测试脚本验证功能：

```bash
python tests/explorations/test_context_box.py
```

或者直接在模块中运行内置测试：

```bash
python src/utils/context_box.py
```

## 注意事项

1. **API 密钥安全**: 确保你的 `.env` 文件中正确配置了 `WUYING_AGENTBAY_API_KEY`
2. **网络超时**: 下载大文件时可能需要较长时间，模块内部使用了 60 秒的超时设置
3. **磁盘空间**: 下载大量文件前请确保有足够的磁盘空间
4. **并发限制**: AgentBay API 可能有速率限制，避免同时发起过多请求
5. **临时文件清理**: 下载过程中会使用临时文件，模块会自动清理，但如果程序异常退出可能需要手动清理

## 错误处理

所有方法都包含了完善的错误处理和日志记录。如果操作失败，会返回适当的结果（如空列表、None 或 0），并在日志中记录错误信息。

建议在使用时检查返回值：

```python
context = manager.get_context_by_id("invalid-id")
if context is None:
    print("未找到该 Context")
    # 处理错误情况
```

## 相关文件

- 实现代码: `src/utils/context_box.py`
- 测试脚本: `tests/explorations/test_context_box.py`
- 相关模块: `src/utils/my_sandbox.py` (使用了类似的 AgentBay API)
