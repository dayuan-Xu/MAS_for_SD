---
name: langgraph-docs
description: Use this skill for requests related to LangGraph in order to fetch relevant documentation to provide accurate, up-to-date guidance.
---

# LangGraph 文档
## 概述
本技能说明如何查阅 LangGraph Python 官方文档，以辅助解答问题并指导具体实现。

## 使用说明
1. **获取文档索引**
使用 `fetch_url` 工具访问以下链接：https://docs.langchain.com/llms.txt
该链接会返回一份包含所有可用文档及对应说明的结构化清单。

2. **筛选相关文档**
根据问题内容，从索引中挑选 2–4 个最相关的文档链接，优先选择：
- 针对实现类问题的具体操作指南
- 用于理解核心概念的说明页面
- 提供完整流程示例的教程
- 包含 API 详细信息的参考文档

3. **获取选中的文档内容**
使用 `fetch_url` 工具读取筛选出的文档链接。

4. **提供精准指导**
在查阅文档后，完成用户提出的需求。