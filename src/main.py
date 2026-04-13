from src.deep_agent_based_dev_team import leader, run_config
from src.utils.deep_agents_utils import multi_turn_conversation

# toy_game = """使用Python GUI开发一个简单的五子棋游戏。"""

multi_turn_conversation(leader, run_config)
# 主派副智能体模式的缺点：
# 只有主智能体具备用户接口，用户无法干预副智能体。
# 虽然副智能体单独进行任务可以避免填充主智能体的上下文，但是主智能体也无法获知副智能体的真实发展状况，因而无法给予有效指导，尤其是当副智能体遇到复杂问题时。
