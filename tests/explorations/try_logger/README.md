# Python Logger 日常使用指南

本教程演示如何在多模块 Python 项目中正确使用 logging 模块。

## 目录结构

```
try_logger/
├── README.md                    # 本文件
├── basic_usage.py              # 基础用法示例
├── module_a.py                 # 模块 A（模拟业务模块）
├── module_b.py                 # 模块 B（模拟业务模块）
├── main.py                     # 主程序入口
└── config_logging.py           # 统一的日志配置
```

## 核心概念

### 1. Logger 的层级结构
- Logger 名称通常使用 `__name__`，形成层级关系
- 例如：`main` -> `module_a` -> `module_b`
- 子 logger 会自动继承父 logger 的配置

### 2. 日志级别（从低到高）
- DEBUG: 调试信息
- INFO: 一般信息
- WARNING: 警告信息（默认级别）
- ERROR: 错误信息
- CRITICAL: 严重错误

### 3. Handler（处理器）
- ConsoleHandler: 输出到控制台
- FileHandler: 输出到文件
- RotatingFileHandler: 按大小轮转的文件处理器

### 4. Formatter（格式化器）
控制日志输出的格式，包括时间、级别、模块名、消息等

## 使用步骤

### 第一步：统一配置（推荐）
在 `config_logging.py` 中集中配置日志系统

### 第二步：在各模块中获取 logger
```python
import logging
logger = logging.getLogger(__name__)
```

### 第三步：记录日志
```python
logger.debug("调试信息")
logger.info("一般信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")
```

## 运行示例

```bash
# 运行主程序
python tests/explorations/try_logger/main.py

# 查看生成的日志文件
cat logs/app.log
```

## 最佳实践

1. **不要在每个模块重复配置** - 使用统一的配置模块
2. **使用 `__name__` 作为 logger 名称** - 自动形成层级
3. **选择合适的日志级别** - 不要全部用 info 或 error
4. **在生产环境调整级别** - 开发时用 DEBUG，生产用 INFO 或 WARNING
5. **异常记录使用 `exc_info=True`** - 自动记录堆栈信息
6. **避免在日志中记录敏感信息** - 如密码、密钥等

## 常见问题

### Q: 为什么我的日志没有输出？
A: 检查日志级别设置，默认是 WARNING，低于此级别的日志不会输出

### Q: 如何同时输出到控制台和文件？
A: 添加多个 Handler，一个 ConsoleHandler，一个 FileHandler

### Q: 如何按天或按大小分割日志文件？
A: 使用 TimedRotatingFileHandler 或 RotatingFileHandler
