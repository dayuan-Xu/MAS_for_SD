import time
import uuid

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from src.config.config_logging import experiment_logger, setup_experiment_logging, setup_logging
from src.dev_team.auto_dev import auto_dev
from src.dev_team.my_backend import LinuxSandboxBackend
from src.dev_team.team import AgentTeam
from src.paths import SOFTWARE_DEV_7_PATH
from src.utils.common import get_time_str
from src.utils.datasets import load_dataset, Task
from src.utils.graph_running import async_multi_turn_conversation


async def talk_with_agent_team(*, task: Task | None = None):
    """测试专家智能体"""
    task_name = ""
    if task is None:
        task_name = "Agent test"
    elif task is not None:
        task_name = task.name
        enable_brown_choice = input(
            f"是否为当前任务:{task_name}启用棕地开发检测（y-yes，n-no），若检测到可以进行棕地开发则将进行棕地开发；若不检测，默认绿地开发！")
        enable_brown = True if enable_brown_choice.strip().lower() == 'y' else False

    setup_logging(task_name=task_name)

    # 创建与当前任务关联的沙盒实例
    with (LinuxSandboxBackend(task_name=task_name) as sandbox):
        # ✅ 使用异步工厂方法创建带 MCP 工具的 dev_team V2 实例

        dev_team = await AgentTeam.create_with_agentbay_mcp(sandbox)

        role_to_test = input(f"\n请输入要测试的专家角色 ({dev_team.role_to_agent.keys()}): ").strip()

        # 选择要测试的专家智能体
        agent: CompiledStateGraph = dev_team.role_to_agent[f'{role_to_test}']

        print(f"\n🎯 选择测试的专家: {agent.name}")

        if task_name == "Agent test":
            thread_id = str(uuid.uuid4())
        else:
            thread_id = dev_team.green_or_brown(task, force_using_new_thread=enable_brown)

        # 配置运行参数
        run_config: RunnableConfig = {
            "tags": ["agent_team"],
            "run_name": "与Planner对话",
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": dev_team.team_type
            }
        }

        # 启动多轮对话
        await async_multi_turn_conversation(agent, run_config, sandbox)


async def experiment():
    """串行执行软件开发任务实验"""
    # 设置实验日志
    log_file = setup_experiment_logging()
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
            f"\n是否继续进行下一个任务:{task.name}，还是跳过，还是直接退出（y-'yes and start'，s-'skip and proceed'，n-'no and exit'）：")
        if instruction.lower() == 'n':
            break
        elif instruction.lower() == 's':
            continue
        elif instruction.lower() == 'y':
            experiment_logger.info(f"🚀 开始进行任务{task.name}")
            enable_brown_choice = input(
                f"是否为当前任务:{task.name}启用棕地开发检测（y-yes，n-no），若检测到可以进行棕地开发则将进行棕地开发；若不检测，默认绿地开发！")
            enable_brown = True if enable_brown_choice.strip().lower() == 'y' else False

            # 异步运行软件开发任务（严格串行，等待上一个任务完全结束）
            result = await auto_dev(task, enable_brown=enable_brown)  # 强制绿地开发

            task_results.append(result)

            elapsed_time = result['elapsed_time']
            time_str = get_time_str(elapsed_time)

            if result['success']:
                experiment_logger.info(f"✅ 运行成功: {task.name} (耗时: {time_str})")
            else:
                experiment_logger.info(f"❌ 运行失败: {task.name} (耗时: {time_str})")
                if 'error' in result:
                    experiment_logger.info(f"❌ 错误信息: {result['error']}")

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
    experiment_logger.info(f"📝 实验统计日志文件: {log_file}")


if __name__ == "__main__":
    import asyncio
    import sys

    # Windows 平台需要切换到 SelectorEventLoop 以支持 psycopg 异步操作
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # 运行任务
    asyncio.run(talk_with_agent_team())
    # asyncio.run(experiment())

"""
实验思路：
- 实验项目最好由易到难，比如streamlit的两个实验再到五个难的游戏：2048 < 贪吃蛇 < 打砖块 ≈ 像素鸟 << 坦克大战。自己的方法先追求软件可用数超过基线（实现5=2+3个游戏即可），再追求全部可用！

- 已经启用postgres checkpointer，这样后续可以基于某个智能体的执行历史与其对话，获知他对工具的理解。目前好像无法实现，只能传入planner的thread_id，并提供planner转述对话要求。

- 最大限度地剔除不必要工具，工具越少越好！目前web模态应用ui交互操作验证工具最成熟，完全可以剔除已安装应用启动杀死工具、桌面窗口控制工具？

- 注入人格性格特征，让builder敢于尝试和与evaluator协作询问。

- 验收标准本质上是一种规格说明；可用阶段tasks列表->吸引力阶段tasks列表，创建多阶段软件功能点列表？

- （伪）代码表示智能体开发团队的工作流程以减少自然语言歧义？

下一步检验：
1. Builder是否正确认识到需要加载软件开发技能、软件功能验证技能？ 以获取创建虚拟环境和安装依赖包、利用浏览器工具感知UI的指导信息
结果：
Bob还是没有加载该技能！pip安装依赖包时还是遇到了超时问题！
提示词中要求Bob加载python-full-stack技能，Bob还是没有加载任何技能！
Bob加载了必要技能知道从国内镜像源安装pip包，可是还是不会（还是没有）创建项目虚拟环境！
优化措施：
在功能点实现步骤内要求Bob加载该技能！

2. 是否存在智能体行为不符合预期并且某部分提示词存在优化空间？：sys prompt、middleware prompt、tool description
不符合预期的行为：
Bob直接一口气和Eva协商好了7个功能点的验收标准提议！而不是逐个功能点地进行协商与实现！
并且Bob还私自更新了TASKS.md中软件功能点的状态！
Eva并没有真正像Bob自测那样逐一调用工具复现验收测试用例，而只是执行代码查看结果是否与Bob所述自测结果一致，
比如Eva并没有亲自执行一遍客户插入而仅仅是执行代码查看Bob所述自测时插入的“张三”是否真正的插入到数据库中了。
Bob在实现完毕“基础版”的软件功能点后，竟然分不清他面对的“用户”其实就是Planner Alice，反而还向Eva寻求下一步工作指示！
优化措施：
每个软件功能点的验收标准（提议）完全可以分为两部分：必要实现项与其测试用例。
严厉措辞，要求Bob必须一个功能点一个功能点地进行协商、开发与自测、评审与更改。
对Eva要求的“复现”的定义可能不够清晰，导致Eva“走捷径”。
在共享信息中明确定义各人职责，在各自提示词中交互对象！
"""
