# ⭐ 关键：必须在所有其他导入之前配置日志系统
from src.config.config_logging import setup_logging

setup_logging()

import logging
from src.remote_dev_team.automatic_development import automatic_dev
from src.utils.datasets import software_dev_7

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("启动 AgentBay 自动化软件开发系统")
    logger.info("=" * 60)

    # 获取任务
    task1 = software_dev_7.tasks[0]
    logger.info(f"选择任务: {task1.name} - {task1.name_CN}")

    # 基于agentbay_based_dev_team的自动化软件开发
    automatic_dev(task1)

    logger.info("=" * 60)
    logger.info("自动化开发流程结束")
    logger.info("=" * 60)
