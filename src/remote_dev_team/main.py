# ⭐ 关键：必须在所有其他导入之前配置日志系统
from src.config.config_logging import setup_logging

setup_logging()
from src.utils.my_sandbox import MySandbox
from src.remote_dev_team.agentbay_based_dev_team import AgentBayBasedDevTeam
from langchain_core.runnables import RunnableConfig
import uuid
from src.utils.graph_running_utils import multi_turn_conversation
from src.remote_dev_team.automatic_development import automatic_dev
from src.utils.datasets import software_dev_7


def main():
    # 获取任务
    task1 = software_dev_7.tasks[0]

    # 基于agentbay_based_dev_team的自动化软件开发
    automatic_dev(task1)


def test_assign_middleware():
    # 创建与当前任务关联的沙盒实例
    sandbox = MySandbox(task_name="Dev team test")

    # 创建dev_team实例
    dev_team = AgentBayBasedDevTeam(sandbox)

    run_config: RunnableConfig = {
        "tags": ["agentbay_based_dev_team", "Leader"],
        "run_name": "assign中间件测试",
        "configurable": {"thread_id": str(uuid.uuid4())}
    }

    multi_turn_conversation(dev_team, run_config)


if __name__ == "__main__":
    # test_assign_middleware()
    main()
