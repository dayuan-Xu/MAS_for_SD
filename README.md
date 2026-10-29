# 用于软件开发的多智能体系统
## 1、灵感来源
- ChatDev
- MetaGPT
- [langhcain academy：introduction to langchain](https://github.com/langchain-ai/lca-lc-foundations/blob/main/notebooks/module-2/2.4_wedding_planners.ipynb)

## 2、技术框架
- LangChain Agents及其中间件系统
- FastAPI

## 3、前后端缺陷和TODOs
1. subagent的主调智能体在调用subagent（which is a tool）时，下达的具体指令的具备一定的随机性，会增加subagent任务执行行为的不可控性。
2. 没有合理利用LangChain Agents的Runtime Context作为只读信息源供智能体工具执行时使用。
3. 没有合理利用LangChain Agents的Custom AgentState作为一个可读可写的信息源供Planner智能体用来保存一些任务相关信息，用于指导Planner该从用户那里获取哪些任务细节，或者用于构建subagent的可控的输入HumanMessage。

    比如`功能需求`可以占据Custom AgentState中的一个字段（可用于构建对Evaluator的输入HumanMessage，作为Eva评审的ground truth），`技术约束`也可以占据其中一个字段（可用于构建对Builder的输入HumanMessage），任务特定的`Context Box id`也可以占据其中一个字段（用于？？？在AgentTeam发现项目历史不存在于当前沙盒会话时手动调用项目历史恢复工具，在该工具中会读取context box id执行项目历史恢复）。
4. 部分代码未很好遵循Python编程最佳实践。
5. 前端可以基于langchain开源的[agent-chat-ui](https://github.com/langchain-ai/agent-chat-ui)进行改进。
6. 对AgentBay MCP的使用有待改进，完全可以将`sandbox_id(or session id)`作为一个Runtime Context中的一个字段，当AgentBay MCP中的任何工具被调用时，可以通过MCP tool interceptor自动将当前`sandbox_id`注入到实际被调用的agentbay MCP tool中，为智能体减少一定的工具认知负担。