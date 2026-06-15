from src.dev_team.team_config import TeamType
from src.utils.datasets import Task


async def talk_with_agent_team(*, task: Task | None = None, team_type: TeamType | str = TeamType.SIMPLE):
    """测试专家智能体"""
    task_name = ""

    if task is None:
        task_name = "Agent test"
    elif task is not None:
        task_name = task.name

    user_input = input(
        f"是否为当前任务:{task_name}\n"
        f"启用棕地开发检测?\n"
        f"若启用检测，检测到可以进行棕地开发时，则将进行棕地开发；若不开启检测，默认绿地开发！\n"
        f"输入y启用，输入n不启用：\n"
    )

    enable_brown = True if user_input.strip().lower() == 'y' else False
    from src.config.config_logging import setup_logging

    setup_logging(task_name=task_name, team_type=team_type)
    from langchain_core.runnables import RunnableConfig
    from langgraph.graph.state import CompiledStateGraph

    from src.dev_team.team import AgentTeam
    from src.utils.graph_running import async_multi_turn_conversation

    async with await AgentTeam.create_with_agentbay_mcp(
            task_name=task_name,
            team_type=team_type,
            enable_brown=enable_brown
    ) as dev_team:
        role_to_test = input(f"\n请输入要测试的专家角色 ({list(dev_team.role_to_agent.keys())}): ").strip()

        # 选择要测试的专家智能体
        agent: CompiledStateGraph = dev_team.role_to_agent[f'{role_to_test}']

        print(f"\n🎯 选择测试的专家: {agent.name}")

        # 配置运行参数
        run_config: RunnableConfig = {
            "tags": ["agent_team"],
            "run_name": "Agent Test",
            "configurable": {
                "thread_id": dev_team.thread_id,
                "checkpoint_ns": dev_team.team_type
            }
        }

        # 启动多轮对话
        await async_multi_turn_conversation(agent, run_config, dev_team.sandbox)


async def experiment(*, team_type: TeamType | str = TeamType.SIMPLE):
    import time

    from src.config.config_logging import experiment_logger, setup_experiment_logging
    from src.dev_team.auto_dev import auto_dev
    from src.paths import SOFTWARE_DEV_7_PATH
    from src.utils.common import get_time_str
    from src.utils.datasets import load_dataset
    """串行执行软件开发任务实验"""
    # 设置实验日志
    log_file = setup_experiment_logging(team_type=team_type)
    experiment_logger.info(f"📝 实验统计日志文件: {log_file}")

    software_dev_7 = load_dataset(SOFTWARE_DEV_7_PATH)

    tasks = software_dev_7.tasks
    experiment_logger.info('=' * 600)
    experiment_logger.info(f"🚀 开始异步串行执行 {len(tasks)} 个软件开发任务")
    experiment_logger.info('=' * 60)
    task_results = []
    total_start_time = time.time()

    for task in reversed(tasks):
        # 询问是否继续下一个任务
        instruction = input(
            f"\n是否继续进行下一个任务:{task.name}，还是跳过，还是直接退出?"
            f"\n（y-'yes and start'，s-'skip and proceed'，n-'no and exit'）：")
        if instruction.lower() == 'n':
            break
        elif instruction.lower() == 's':
            continue
        elif instruction.lower() == 'y':
            experiment_logger.info(f"🚀 开始进行任务{task.name}")
            enable_brown_choice = input(
                f"是否为当前任务:{task.name}启用棕地开发检测？\n"
                f"若检测到可以进行棕地开发，则将进行棕地开发，复用已有的thread_id和task context box)。\n"
                f"若不启用棕地开发检测，默认绿地开发！\n"
                f"（y-yes，n-no）")
            enable_brown = True if enable_brown_choice.strip().lower() == 'y' else False

            # 异步运行软件开发任务（严格串行，等待上一个任务完全结束）
            result = await auto_dev(task, team_type=team_type, enable_brown=enable_brown)  # 强制绿地开发

            task_results.append(result)

            elapsed_time = result['elapsed_time']
            time_str = get_time_str(elapsed_time)

            if result['success']:
                experiment_logger.info(f"✅ 任务成功: {task.name}，耗时: {time_str}")
            else:
                experiment_logger.info(f"❌ 任务失败: {task.name}，耗时: {time_str}")
                if 'error' in result:
                    experiment_logger.info(f"❌ 错误信息: {result['error']}")
        else:
            experiment_logger.error(f"输入错误，退出程序")
            break

    total_time = time.time() - total_start_time
    total_time_str = get_time_str(total_time)

    experiment_logger.info(f"\n{'=' * 60}\n📊 执行完成统计:")
    total_count = len(task_results)
    success_count = sum(result['success'] for result in task_results)
    failed_count = sum(not result['success'] for result in task_results)
    experiment_logger.info(f"总共运行: {total_count} 个任务")
    experiment_logger.info(f"✅ 成功: {success_count} 个")
    experiment_logger.info(f"❌ 失败: {failed_count} 个")
    experiment_logger.info(f"⏱️ 总耗时: {total_time_str}")

    # 对失败的结果记录详细错误信息
    for i, result in enumerate(task_results):
        if not result['success']:
            experiment_logger.info(f"❌ 运行失败: {result['task_name']}")
            if 'error' in result:
                experiment_logger.info(f"❌ 错误信息: {result['error']}")


async def get_messages():
    from src.config.config_logging import setup_logging

    setup_logging(task_name="Agent test")
    from langchain_core.runnables import RunnableConfig
    from rich.pretty import pprint

    from src.config.database import reset_async_connection_pool
    from src.dev_team.team import AgentTeam

    import logging
    logger = logging.getLogger(__name__)

    # ✅ 使用 async with 自动管理资源（推荐方式）
    async with await AgentTeam.create_with_agentbay_mcp(
            task_name="Agent test",
            enable_brown=True
    ) as dev_team:
        try:
            # 从检查点中获取顶层图（比如Alice）的消息列表or某个子图（比如Bob、Eva）的消息列表
            logger.info(f"✅ AgentTeam 创建成功, thread_id={dev_team.thread_id}")

            # 选择要测试的专家智能体
            alice, bob, eva = dev_team.agents

            alice_config: RunnableConfig = {
                "configurable": {
                    "thread_id": dev_team.thread_id,
                    # 如果要获取作为节点执行的子图的状态，才需要设置 checkpoint_ns
                }
            }

            logger.info(f"正在获取Alice检查点状态 (thread_id={dev_team.thread_id})...")
            alice_checkpoint = await alice.aget_state(alice_config)

            pprint(alice_checkpoint)

            messages = alice_checkpoint.values['messages']
            logger.info(f"✅ 成功获取Alice {len(messages)} 条消息")
            print(f"\n📋 消息历史 (共 {len(messages)} 条):")
            for msg in messages:
                msg.pretty_print()

            # 无法获取Bob和Eva的状态，按理说应该是能够通过thread id获取其最近的检查点的
            # 同时也无法根据Bob 的thread_id获取其对应的trace，LangSmith对此并不支持
            # 只能从LangSmith下载对应的run的记录
            dict_1: dict = alice_checkpoint.values['expert_thread_ids']
            bob_thread_id = dict_1.get('Bob', None)
            if bob_thread_id:
                bob_config = {
                    "configurable": {
                        "thread_id": bob_thread_id,
                        "checkpoint_ns": ""
                    }
                }
                logger.info(f"正在获取Bob检查点状态 (thread_id={bob_thread_id})...")
                bob_checkpoint = await bob.aget_state(bob_config)
                pprint(bob_checkpoint)
                pprint(bob_checkpoint.values)
                bob_messages = bob_checkpoint.values['messages']
                logger.info(f"✅ 获取Bob {len(bob_messages)} 条消息")
                print(f"\n📋 Bob 消息历史 (共 {len(bob_messages)} 条):")
                for msg in bob_messages:
                    msg.pretty_print()

            dict_2 = bob_checkpoint.values['expert_thread_ids']
            eva_thread_id = dict_2.get('Eva', None)
            if eva_thread_id:
                eva_config = {
                    "configurable": {
                        "thread_id": eva_thread_id,
                        "checkpoint_ns": ""
                    }
                }
                logger.info(f"正在获取Eva检查点状态 (thread_id={eva_thread_id})...")
                eva_checkpoint = await eva.aget_state(eva_config)
                eva_messages = eva_checkpoint.values['messages']
                logger.info(f"✅ 获取Eva {len(eva_messages)} 条消息")
                print(f"\n📋 Eva 消息历史 (共 {len(eva_messages)} 条):")
                for msg in eva_messages:
                    msg.pretty_print()

        except Exception as e:
            logger.error(f"❌ 获取检查点失败: {type(e).__name__}: {e}", exc_info=True)
            print(f"\n❌ 错误: {type(e).__name__}")
            print(f"错误信息: {str(e)}")

            # 尝试重置连接池并重试
            if "pool" in str(e).lower() or "connection" in str(e).lower():
                print("\n🔄 检测到连接池错误，尝试重置连接池...")
                try:
                    await reset_async_connection_pool()
                    print("✅ 连接池已重置，请重新运行程序")
                except Exception as reset_error:
                    print(f"❌ 重置连接池失败: {reset_error}")

            print("\n建议:")
            print("1. 检查 PostgreSQL 是否正常运行: docker ps | grep postgres")
            print("2. 检查数据库连接配置是否正确")
            print("3. 查看详细日志文件")
            raise
        # ✅ 退出 async with 块时，会自动：
        # 1. 下载成果物到本地
        # 2. 删除沙盒会话
        # 无需手动调用 dev_team.sandbox.delete_session()


if __name__ == "__main__":
    import asyncio
    import sys

    # Windows 平台需要切换到 SelectorEventLoop 以支持 psycopg 异步操作
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # 运行任务
    # asyncio.run(talk_with_agent_team(team_type="dual"))
    asyncio.run(experiment(team_type="simple"))

    # 重播消息
    # asyncio.run(get_messages())

"""
实验思路：
- （伪）代码表示智能体开发团队的工作流程以减少自然语言歧义？

- 基于技能的进化机制？开发结束后，要求开发者Bob依据本次开发经历完善or扩充其相关技能，比如完善流程，添加对某些工具使用的理解，添加实用性Python脚本等等。

- 目前的多智能体间的消息交互是封装在 HumanMessage，那么 LLM 在底层是否能够正确理解那些不是自己而是其他LLM产出的AIMessage？并给出合理响应？A2A协议？

"""
