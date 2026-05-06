from src.config.config_logging import setup_logging

# 配置日志系统
setup_logging()
import uuid
import time

from langchain_core.runnables import RunnableConfig

from src.remote_dev_team.agentbay_based_team import DevTeamWithLinuxSandboxAndMCP
from src.remote_dev_team.my_sandbox_backend import AgentBayBasedLinuxSandboxBackend
from src.utils.graph_running import async_multi_turn_conversation

from src.config.config_logging import experiment_logger, setup_experiment_logging
from src.paths import SOFTWARE_DEV_7_PATH
from src.remote_dev_team.automatic_development import async_automatic_dev
from src.utils.common import get_time_str
from src.utils.datasets import load_dataset


async def talk_with_dev_team():
    """
    测试带 MCP 工具的专家智能体

    功能说明：
    1. 使用异步工厂方法创建带 MCP 工具的开发团队
    2. 选择 QA 工程师作为测试对象
    3. 对 2048 游戏进行功能性测试
    4. QA 工程师可以使用 MCP 工具 + run_browser_use_agent 工具
    """
    print("\n请选择要运行的测试:")
    print("1. 测试带 MCP 工具的专家智能体（工程师、QA 工程师、Leader）")
    print("2. 退出")

    choice = input("\n请输入选项 (1/2): ").strip()

    if choice == "2":
        print("退出测试")
        return
    elif choice != "1":
        print("无效选项，默认运行测试 1")

    role_to_test = input("\n请输入要测试的专家角色 (QA Engineer): ").strip()

    print("\n" + "=" * 80)
    print("开始测试带 MCP 工具的专家智能体")
    print("=" * 80 + "\n")

    # 创建与当前任务关联的沙盒实例
    with AgentBayBasedLinuxSandboxBackend(task_name="2048 game") as sandbox:
        # ✅ 使用异步工厂方法创建带 MCP 工具的 dev_team V2 实例

        print("\n" + "=" * 80)
        print("正在初始化开发团队（加载 MCP 工具）...")
        print("=" * 80 + "\n")

        dev_team = await DevTeamWithLinuxSandboxAndMCP.create_with_mcp_tools(sandbox)

        print(f"\n✅ 开发团队初始化完成")
        print(f"   - MCP 工具数量: {len(dev_team.mcp_tools)}")

        # 选择要测试的专家智能体
        agent = dev_team.role_to_agent[f'{role_to_test}']

        print(f"\n🎯 选择测试的专家: {agent.name}")

        # 配置运行参数
        run_config: RunnableConfig = {
            "tags": ["agentbay_based_dev_team_v2", "QA Engineer", "with_mcp_tools"],
            "run_name": "带MCP工具的专家智能体测试",
            "configurable": {"thread_id": str(uuid.uuid4())}
        }

        print(f"\n📝 测试场景: 对 2048 game 软件成果物进行功能性测试")
        print(f"💡 提示: QA 工程师现在可以使用 MCP 工具和 run_browser_use_agent 工具\n")

        # 测试说明
        test_instruction = """已知当前各种工具执行的环境是sandbox id="XXXXXXX"(所以之后调用那些需要sandbox id的时候就用该sandbox id)，目前有一个该软件成果物（保存地址为'/tmp/persistent/agent_workspace/warehouse/2048_game/'）需要进行功能性测试。现在请你合理利用已有的各种工具对其完成功能性测试（调用已有工具对其进行功能性测试前，你可以先了解该软件成果物），并在一次功能性测试尝试结束后向我报告结果。"""
        # 启动多轮对话
        await async_multi_turn_conversation(agent, run_config, sandbox)


async def serial_experiment():
    """
    异步串行执行软件开发任务实验
    
    内部串行调用async_automatic_dev，每个任务使用带MCP工具的DevTeamWithLinuxSandboxAndMCP实例
    确保严格串行执行：后一个任务必须在上一个完全结束后才能继续
    """
    # 设置实验日志
    log_file = setup_experiment_logging('async_serial')
    experiment_logger.info(f"📝 实验统计日志文件: {log_file}")

    software_dev_7 = load_dataset(SOFTWARE_DEV_7_PATH)

    tasks = software_dev_7.tasks
    experiment_logger.info(f"\n{'=' * 60}\n🚀 开始异步串行执行 {len(tasks)} 个软件开发任务\n{'=' * 60}\n")
    task_results = []
    total_start_time = time.time()

    for task in tasks:
        # ⭐ 异步运行软件开发任务（严格串行，等待上一个任务完全结束）
        result = await async_automatic_dev(task)

        task_results.append(result)

        elapsed_time = result['elapsed_time']
        time_str = get_time_str(elapsed_time)

        if result['success']:
            experiment_logger.info(f"  ✅ 运行成功: {task.name} (耗时: {time_str})")
        else:
            experiment_logger.info(f"  ❌ 运行失败: {task.name} (耗时: {time_str})")
            if 'error' in result:
                experiment_logger.info(f"     ❌ 错误信息: {result['error']}")

        # 询问是否继续下一个任务
        instruction = input("\n是否继续进行下一个任务还是直接退出（y-yes and continue，n-no and exit）：")
        if instruction.lower() == 'n':
            break
        elif instruction.lower() == 'y':
            continue

    total_time = time.time() - total_start_time
    total_time_str = get_time_str(total_time)

    experiment_logger.info(f"\n{'=' * 60}\n📊 执行完成统计:")
    total_count = len(task_results)
    success_count = sum(result['success'] for result in task_results)
    failed_count = sum(not result['success'] for result in task_results)
    experiment_logger.info(f"总共运行: {total_count} 个任务")
    experiment_logger.info(f"  ✅ 成功: {success_count} 个")
    experiment_logger.info(f"  ❌ 失败: {failed_count} 个")
    experiment_logger.info(f"  ⏱️  总耗时: {total_time_str}")

    # 对失败的结果记录详细错误信息
    for i, result in enumerate(task_results):
        if not result['success']:
            experiment_logger.info(f"\n❌ 运行失败: {result['task_name']}")
            if 'error' in result:
                experiment_logger.info(f"   ❌ 错误信息: {result['error']}")


if __name__ == "__main__":
    import asyncio

    # serial_experiment()
    # concurrent_experiment()
    asyncio.run(serial_experiment())
