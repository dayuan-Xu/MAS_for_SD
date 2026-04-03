---
name: deliverables-check
description: Use this skill for evaluating stage deliverables or coding task deliverables produced by subagents.
license: MIT
compatibility: None
metadata:
  author: boss
  version: "6.0"
allowed-tools: read, edit, task
---

# 交付物检查

## 概述

本技能用于团队领导 Tim 在收到团队专家的任务完成消息后，对交付物依照不同**检查指南**进行检查。

## 使用说明

### 1. 选择检查标准

基于当前专家提交的交付物类型，读取对应的**检查指南**：

| 阶段     | 专家角色       | 交付物                                     | 检查指南                                                     |
| -------- | -------------- | ------------------------------------------ | ------------------------------------------------------------ |
| 需求分析 | 产品经理 Alice | 《产品需求.md》                            | [product_requirements_check_guide.md](references/product_requirements_check_guide.md) |
| 架构设计 | 架构师 Bob     | 《系统概要设计.md》                        | [system_architecture_check_guide.md](references/system_architecture_check_guide.md) |
| 详细设计 | 项目经理 Cindy | 《系统详细设计.md》                        | [detailed_design_check_guide.md](references/detailed_design_check_guide.md) |
| 编码实现 | 工程师 David   | 代码文件 + 文档 + （代码质量验证脚本文件） | [code_delivery_check_guide.md](references/code_delivery_check_guide.md) |
| 测试验证 | QA 工程师 Eva  | 《系统测试报告.md》                        | [system_test_report_check_guide.md](references/system_test_report_check_guide.md) |

### 2. 执行检查

对照检查指南逐项检查，标记不符合项。

### 3. 检查结果后处理

- **不通过** → 使用下方反馈模板给出问题清单和修改要求
- **通过**：
    - **文档交付物** → 编辑文档文件，将 YAML Frontmatter 中的 `state` 字段改为"已通过"
    - **编码任务交付物** → 不给予专家反馈，仅更新 DEVLOG.md 记录进展

**反馈模板：**

```
【评审结果】不通过

【存在问题】
1. ...
2. ...

【修改要求】
1. ...
2. ...
```

### 4. 重新核验

专家修改后重新提交，再次检查，通过后进入下一阶段。