# 学习路径建议

## 📚 推荐学习顺序

### 1️⃣ 初学者 - 从基础开始

**文件**: `basic_usage.py`

**学习目标**:
- 理解什么是 logger
- 掌握 5 种日志级别的使用
- 学会记录变量和异常
- 了解条件日志

**运行方式**:
```bash
python tests/explorations/try_logger/basic_usage.py
```

**预计时间**: 15-20 分钟

---

### 2️⃣ 进阶 - 理解配置

**文件**: `config_logging.py`

**学习目标**:
- 理解为什么需要统一配置
- 掌握 Handler 的概念（控制台、文件）
- 学会使用 RotatingFileHandler
- 理解日志格式化的作用

**运行方式**:
```bash
python tests/explorations/try_logger/config_logging.py
```

**查看生成的文件**:
- `logs/app.log` - 详细日志
- `logs/error.log` - 错误日志

**预计时间**: 20-30 分钟

---

### 3️⃣ 实战 - 多模块项目

**文件**: `module_a.py`, `module_b.py`, `main.py`

**学习目标**:
- 理解 `__name__` 的作用
- 掌握多模块日志的层级关系
- 学会在类和函数中使用 logger
- 理解日志如何帮助调试

**运行方式**:
```bash
python tests/explorations/try_logger/main.py
```

**观察重点**:
- 控制台的简洁输出
- 日志文件中的详细信息（包含模块名、函数名、行号）
- 不同模块的日志如何区分

**预计时间**: 30-40 分钟

---

### 4️⃣ 速查 - 日常开发参考

**文件**: `QUICK_REFERENCE.md`

**用途**:
- 快速查找常用 API
- 复制粘贴代码模板
- 避免常见错误
- 解决实际问题

**建议**: 收藏此文件，日常开发时随时查阅

---

## 🎯 核心概念总结

### Logger 的工作原理（通俗解释）

想象你有一个**智能录音系统**：

1. **Logger（录音机）**
   - 每个模块都有自己的录音机
   - 录音机有名字（`__name__`），方便识别来源
   - 录音机可以设置灵敏度（日志级别）

2. **Handler（输出渠道）**
   - 可以把录音输出到扬声器（控制台）
   - 可以把录音保存到磁带（文件）
   - 可以同时使用多个渠道

3. **Formatter（格式化器）**
   - 决定录音的格式
   - 可以包含时间、说话人、内容等

4. **Level（级别过滤）**
   - DEBUG: 最详细，连呼吸声都录
   - INFO: 正常对话
   - WARNING: 重要的提醒
   - ERROR: 出错了
   - CRITICAL: 严重问题

### 为什么要用 logging 而不是 print？

| 特性 | print | logging |
|------|-------|---------|
| 分级管理 | ❌ | ✅ |
| 输出到文件 | ❌ | ✅ |
| 自动加时间戳 | ❌ | ✅ |
| 显示来源模块 | ❌ | ✅ |
| 性能优化 | ❌ | ✅ |
| 灵活控制 | ❌ | ✅ |

**实际例子**:
```python
# 用 print - 生产环境要手动删除
print("调试信息: x =", x)  # 忘记删除会一直输出

# 用 logging - 可以轻松控制
logger.debug("调试信息: x = %s", x)  # 设置级别为 INFO 就不会输出
```

---

## 💡 实际应用建议

### 小型脚本（单文件）

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("程序开始")
# ... 你的代码 ...
```

### 中型项目（3-10 个文件）

使用本教程的结构：
- 一个配置模块
- 各业务模块使用 `getLogger(__name__)`
- 主程序初始化配置

### 大型项目（10+ 文件）

考虑：
- 使用配置文件（YAML/JSON）
- 按模块设置不同级别
- 添加日志轮转策略
- 集成日志分析工具

---

## 🔗 延伸阅读

- Python 官方文档: https://docs.python.org/3/library/logging.html
- Logging Cookbook: https://docs.python.org/3/howto/logging-cookbook.html
- 本项目的实际使用: 查看 `src/` 目录下的代码

---

## ✅ 学习检查清单

完成本教程后，你应该能够：

- [ ] 解释为什么使用 logging 而不是 print
- [ ] 说出 5 种日志级别及其使用场景
- [ ] 在多模块项目中正确配置和使用 logger
- [ ] 记录包含变量的日志消息
- [ ] 记录异常信息（包含堆栈）
- [ ] 理解日志文件的格式和内容
- [ ] 根据需求调整日志级别
- [ ] 在日常开发中熟练使用 logging

---

**下一步**: 在你的实际项目中应用这些知识！

从一个简单的脚本开始，逐步扩展到更复杂的项目结构。记住：**好的日志习惯会让调试变得轻松十倍**。
