from src.config.config_logging import setup_logging

# 配置日志系统
setup_logging()

import uuid
from langchain_core.runnables import RunnableConfig

from src.utils.graph_running import multi_turn_conversation


# 基于langchain deepagents实现的智能体开发团队。
# 缺点：
# 1. 无沙盒，execute工具执行时需要人类干预
# 2. 非端到端开发，一次用户输入不保证产出可交付软件
# 3. deepagents内置中间件不符合
def local_dev_team_v1():
    from src.local_dev_team.deep_agent_based_team import leader, run_config

    multi_turn_conversation(leader, run_config)


# 基于langchain agents实现的智能体开发团队。
# 主派副智能体模式的缺点：
# 1. 只有主智能体具备用户接口，用户无法干预副智能体
# 2. 主副智能体件通信同步而非异步，降低效率，无法并行化工作
# 3. 使用内置的SubAgentMiddleware完成的任务指派并不是真正的“多智能体协作”，
# 因为其内置的工具附加提示词、工具描述、工具参数schema不符合“通信工具”的定义。
def local_dev_team_v2():
    from src.local_dev_team.leader_agent import leader

    run_config: RunnableConfig = {
        "tags": ["agent_based_dev_team", "Leader"],
        "run_name": "本地开发团队测试",  # 模型所见提示词包含：工具描述和工具入参schema、开发者指定提示词、中间件注入提示词。
        "configurable": {"thread_id": str(uuid.uuid4())}
    }

    multi_turn_conversation(leader, run_config)


def local_dev_team_with_persistent_checkpointer():
    from src.local_dev_team.leader_agent import leader_v2
    thread_id = "4620f7d0-44d7-43d4-96bf-fbc9f4a67db7"

    run_config: RunnableConfig = {
        "tags": ["agent_based_dev_team", "Leader"],
        "run_name": "本地开发团队测试",  # 模型所见提示词包含：工具描述和工具入参schema、开发者指定提示词、中间件注入提示词。
        "configurable": {"thread_id": thread_id}
    }

    multi_turn_conversation(leader_v2, run_config)
    print(f"本次对话使用的thread_id为{thread_id}，后续可持续使用")


if __name__ == "__main__":
    # toy_game = """使用Python GUI开发一个简单的五子棋游戏。"""
    local_dev_team_with_persistent_checkpointer()
