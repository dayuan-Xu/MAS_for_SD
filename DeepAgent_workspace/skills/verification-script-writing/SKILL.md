---
name: verification-script-writing
description: Use this skill for writing automated verification scripts to validate code deliverables.
license: MIT
compatibility: None
metadata:
  author: boss
  version: "2.0"
allowed-tools: write, read, execute
---

# 验证脚本编写

## 概述

作为工程师 David，使用本技能完成`代码质量验证编写任务`，用于证明代码交付物质量，帮助团队领导 Tim 快速核验。

## 核心原则

1. **自动化**：脚本独立运行，无交互输入。
2. **本地化**：不依赖外部网络，本地完成检查。
3. **简洁性**：输出写入文件，避免大量日志。
4. **可重复**：多次运行结果一致。

## 使用说明

### 1. 创建脚本目录

在当前项目空间根目录下创建 `scripts/code_deliverables_check/`。

### 2. 编写必选脚本

按顺序编写：

| 脚本名称                    | 目的         | 要求要点                                                  | 产出文件（均在`scripts/code_deliverables_check/`下） |
|-------------------------|------------|-------------------------------------------------------|---------------------------------------------|
| run_tests.sh/bat        | 运行测试并生成报告  | 使用pytest/jest，生成JUnit XML和覆盖率报告，退出码0=通过               | tests.xml, coverage.json                    |
| check_quality.sh/bat    | 检查代码风格和bug | Python: ruff/flake8+mypy；Node.js: eslint+tsc，退出码0=无阻断 | lint_report.json                            |
| coverage_check.py       | 验证覆盖率门槛    | 参数--fail-under/--branch-fail-under，默认80%/70%，退出码0=通过  | coverage.json                               |
| generate_summary.sh/bat | 汇总结果生成结论   | 读取子检查结果，给出通过/不通过                                      | summary.json                                |

### 3. 编写使用说明文档 (README.md)

在目录下创建README.md，包含：

- 执行顺序（步骤列表）。
- 输出文件说明（要点）。
- 通过标准（summary.json overall_passed=true）。
- 预计执行时间和前置依赖。

### 4. 输出规范

- 退出码：0=通过，非0=失败。
- JSON格式：UTF-8，缩进2空格，相对路径。
- 错误信息：包含文件路径、行号、类型、建议。

### 5. 可选脚本（按复杂度选择）

- run_smoke.sh：冒烟测试。
- todo_scan.py：扫描TODO占位符。
- func_length_check.py：检查函数长度>50行。

## 注意事项

- ✅ 所有必选脚本创建。
- ✅ 独立运行，无用户交互。
- ✅ 输出文件位置正确。
- ✅ summary.json真实反映结果。
- ✅ README.md清晰。