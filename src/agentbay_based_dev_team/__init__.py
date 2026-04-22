"""
1. 基于无影AgentBay来为智能体开发团队提供真正的沙盒环境，
首先重新基于无影AgentBay提供的session，重新实现LangChain agents框架中的一些中间件：
比如先基于无影agentbay实现MySandboxBackend，之后将该沙盒提供给FilesystemMiddleware即可！

2. 基于文件系统创建通信工具，实现真正的多智能体协作！
"""
