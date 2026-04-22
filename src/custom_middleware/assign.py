# 1. 参考资料：langchain内置的SubAgentMiddleware，位于.venv/Lib/site-packages/deepagents/middleware/subagents.py
# 2。 核心需求：
# 基于SubAgentMiddleware在src/custom_middleware/assign.py，
# 实现一个AssignMiddleware，提供一个assign工具，后续装配给leader（src/agentbay_based_dev_team/leader.py:66），
# 从而允许leader只做为一个协调组织者，负责将软件开发中的某个阶段性任务，信任地委派给其他成员智能体（比如david、cindy、alice、eva）去完成。
# 同时配分配到阶段性任务地智能体，有些是必须具备长期记忆的，因此这些智能体在creat_agent创建时必须使checkpointer为True，
# 以此显式指明被调用的智能体专家可以使用，leader所用的那个thread id，以便它们在leader多次调用assign工具多次分配任务之间保持记忆。
# 即通过assign调用的团队专家，可以在多次assign间保持记忆。
from deepagents import SubAgentMiddleware


# 3. 需求产生原因：
# langchain内置的SubAgentMiddleware核心是为智能体提供task工具，用于主调智能体将一些复杂多步骤任务上下文交给一个短暂存在的subagent处理，同时隔离这部分上下文，只获取最终成果。
# 但是这个中间件对系统提示词的注入内容、提供的task工具的工具描述和工具参数schema中对task工具入参的描述，不太符合我想要的assign工具的特征！！！

# 满足我的需求的必须实现点：
# 实现AssignMiddleware，
# 重写：
# 1、task工具入参schema，表明只需要description一个简短的任务描述和expert_name专家名字。
# 2、系统提示词注入部分，介绍assign工具可分配任务的智能体专家的名字，替换SubAgen在提示词中t注入的available subagents。

# 4. 预期效果：
# AssignMiddleware实现的assign工具做为双智能体间（leader和其他智能体专家间）的交流工具，每次assign直接触发被分配的智能体的一次运行。
# 即不仅leader可以通过task和其他团队成员通信，engineer也可以通过该工具和其他团队成员（比如前驱成员）进行通讯。


# 其他想法，不仅仅是只给leader用的AssignMiddleware，而是可以给大部分团队成员用的AskMiddleware，提供ask工具用于获取信息或提供评估者反馈，
# 一个团队专家（非leader的团队专家）可以ask的对象只能是它所负责的软件开发阶段的前驱阶段

class AssignMiddleware(SubAgentMiddleware):
    pass
