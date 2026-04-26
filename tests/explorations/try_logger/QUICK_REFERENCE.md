# Python Logger 快速参考卡片

## 🚀 最简用法（3步）

```python
import logging

# 1. 获取 logger
logger = logging.getLogger(__name__)

# 2. 记录日志
logger.info("这是一条信息")
logger.error("这是一个错误")
```

## 📋 常用日志级别

| 级别 | 方法 | 使用场景 |
|------|------|----------|
| DEBUG | `logger.debug()` | 调试信息，详细的数据流 |
| INFO | `logger.info()` | 一般信息，确认程序正常运行 |
| WARNING | `logger.warning()` | 警告信息，程序仍可运行 |
| ERROR | `logger.error()` | 错误信息，某些功能失败 |
| CRITICAL | `logger.critical()` | 严重错误，程序可能崩溃 |

## 💡 最佳实践

### ✅ 推荐做法

```python
# 1. 在模块顶部定义 logger
import logging
logger = logging.getLogger(__name__)

# 2. 记录变量
logger.info(f"用户 {username} 登录成功")

# 3. 记录异常（包含堆栈）
try:
    result = 1 / 0
except Exception as e:
    logger.error(f"计算失败: {e}", exc_info=True)

# 4. 条件日志（避免不必要的性能开销）
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"详细数据: {expensive_operation()}")
```

### ❌ 避免做法

```python
# 不要使用 print
print("调试信息")  # ❌

# 不要在每个模块重复配置
logging.basicConfig(...)  # ❌ 只在主程序配置一次

# 不要记录敏感信息
logger.info(f"密码: {password}")  # ❌ 危险！
```

## 🔧 多模块项目配置

### 步骤 1: 创建配置模块 (config_logging.py)

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(log_level=logging.DEBUG):
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 文件 Handler
    file_handler = RotatingFileHandler(
        "logs/app.log",
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding="utf-8"
    )
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 控制台 Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
```

### 步骤 2: 在主程序初始化

```python
# main.py
from config_logging import setup_logging

setup_logging()  # 只需调用一次
```

### 步骤 3: 在各模块中使用

```python
# module_a.py
import logging
logger = logging.getLogger(__name__)  # 自动继承配置

def my_function():
    logger.info("模块 A 的函数被调用")
```

## 📊 日志格式说明

```
%(asctime)s       - 时间戳
%(levelname)s     - 日志级别 (DEBUG, INFO, etc.)
%(name)s          - Logger 名称 (通常是模块名)
%(funcName)s      - 函数名
%(lineno)d        - 行号
%(message)s       - 日志消息
```

示例输出：
```
2026-04-23 16:39:37 - INFO - module_a - process_data:19 - 开始处理数据，共 5 条
```

## 🎯 常见场景

### 1. 记录函数调用

```python
def process_data(data):
    logger.info(f"开始处理 {len(data)} 条数据")
    # ... 处理逻辑 ...
    logger.info("数据处理完成")
```

### 2. 记录异常

```python
try:
    result = risky_operation()
except Exception as e:
    logger.error(f"操作失败: {e}", exc_info=True)  # 包含堆栈
```

### 3. 记录性能

```python
import time

start = time.time()
# ... 执行操作 ...
elapsed = time.time() - start
logger.debug(f"操作耗时: {elapsed:.2f}秒")
```

### 4. 记录关键决策

```python
if user_age < 18:
    logger.warning(f"用户 {username} 未成年，限制访问")
    return False
```

## 🔍 调试技巧

### 查看特定模块的日志

```python
# 只查看 module_a 的 DEBUG 日志
logging.getLogger("module_a").setLevel(logging.DEBUG)
```

### 临时增加日志级别

```python
# 临时启用 DEBUG 日志
logging.getLogger().setLevel(logging.DEBUG)
```

### 禁用某个模块的日志

```python
# 禁用第三方库的日志
logging.getLogger("noisy_library").setLevel(logging.CRITICAL)
```

## 📁 项目结构示例

```
my_project/
├── config_logging.py      # 日志配置
├── main.py                # 主程序入口
├── module_a.py            # 业务模块 A
├── module_b.py            # 业务模块 B
└── logs/                  # 日志目录（自动生成）
    ├── app.log            # 所有日志
    └── error.log          # 错误日志
```

## ⚡ 一行代码快速开始

```python
import logging; logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'); logger = logging.getLogger(__name__); logger.info("Hello!")
```

---

**记住**: 
1. 使用 `__name__` 作为 logger 名称
2. 只配置一次日志系统
3. 选择合适的日志级别
4. 异常记录用 `exc_info=True`
