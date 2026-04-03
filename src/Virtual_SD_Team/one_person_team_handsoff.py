# 只有一个智能体，通过在不同阶段加载不同角色的SKILL来实现软件开发的全流程。
# 或者说是状态机/切换handsoff 模式，软件开发的不同阶段加载不同的配置（系统提示词+当前阶段可用工具），
# 每次某模型调用前从state中读取当前阶段，进而加载对应配置，
# 每当从用户输入判断出可以调用工具后，就调用工具记录收集到得信息并设置state中得状态标志为下一个阶段。
# 优点：
# 实现简单，只需要加一个 wrap model call 中间件就可以实现配置加载。
# 或者通过子图实现切换模式，即在图的节点内调用子图，需要精细化管理传入子图的state。
# 可以持续和用户对话，同时根据用户反馈推进工作流的阶段。
# 缺点：
# 任务完成的整个过程都在同一个上下文窗口中进行，消息列表会逐渐变长，需要添加总结中间件。
# 参考：
# https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs-customer-support
# https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs
