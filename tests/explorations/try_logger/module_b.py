"""
模块 B - 模拟另一个业务模块

演示：
- 不同模块使用各自的 logger（通过 __name__）
- 日志会自动带上模块名称，方便区分来源
- 多个模块协同工作时的日志追踪
"""

import logging
import time

# 每个模块都使用自己的 __name__
logger = logging.getLogger(__name__)


def calculate_statistics(numbers: list) -> dict:
    """计算统计数据"""
    logger.info(f"开始计算 {len(numbers)} 个数字的统计信息")
    
    if not numbers:
        logger.warning("无法计算空列表的统计信息")
        return {}
    
    start_time = time.time()
    
    try:
        total = sum(numbers)
        average = total / len(numbers)
        minimum = min(numbers)
        maximum = max(numbers)
        
        elapsed = time.time() - start_time
        logger.debug(f"计算耗时: {elapsed:.4f} 秒")
        
        stats = {
            "total": total,
            "average": average,
            "min": minimum,
            "max": maximum,
            "count": len(numbers)
        }
        
        logger.info(f"统计计算完成: 平均值={average:.2f}, 总数={total}")
        return stats
        
    except Exception as e:
        logger.error(f"计算统计信息时出错: {e}", exc_info=True)
        return {}


def format_report(data: dict, title: str = "报告") -> str:
    """格式化报告"""
    logger.info(f"生成报告: {title}")
    
    if not data:
        logger.warning("报告数据为空")
        return f"{title}\n无数据"
    
    lines = [f"{'='*40}", f"{title}", f"{'='*40}"]
    
    for key, value in data.items():
        if isinstance(value, float):
            lines.append(f"{key}: {value:.2f}")
        else:
            lines.append(f"{key}: {value}")
    
    lines.append(f"{'='*40}")
    
    report = "\n".join(lines)
    logger.debug(f"报告生成完成，共 {len(lines)} 行")
    
    return report


class TaskExecutor:
    """任务执行器 - 演示在类中记录日志"""
    
    def __init__(self, task_name: str):
        self.task_name = task_name
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"任务执行器 '{task_name}' 已创建")
    
    def execute(self, steps: list) -> bool:
        """执行一系列步骤"""
        self.logger.info(f"开始执行任务 '{self.task_name}'，共 {len(steps)} 个步骤")
        
        success_count = 0
        for i, step in enumerate(steps, 1):
            try:
                self.logger.info(f"执行步骤 {i}/{len(steps)}: {step}")
                # 模拟步骤执行
                time.sleep(0.1)
                success_count += 1
                self.logger.debug(f"步骤 {i} 执行成功")
            except Exception as e:
                self.logger.error(f"步骤 {i} 执行失败: {e}", exc_info=True)
        
        success_rate = success_count / len(steps) * 100
        self.logger.info(
            f"任务 '{self.task_name}' 完成: "
            f"成功率 {success_rate:.1f}% ({success_count}/{len(steps)})"
        )
        
        return success_count == len(steps)


def integrate_with_module_a():
    """
    演示与其他模块集成
    
    在实际项目中，这里可能会导入 module_a 并调用其函数
    所有模块的日志都会统一记录，并带有各自的模块名
    """
    logger.info("开始与模块 A 集成")
    
    # 模拟调用其他模块的功能
    logger.debug("准备调用 module_a.process_data")
    logger.debug("准备调用 module_a.validate_user")
    
    logger.info("模块集成完成")


if __name__ == "__main__":
    # 单独运行此模块时的测试代码
    from config_logging import setup_logging
    setup_logging()
    
    print("\n测试模块 B:")
    print("-" * 60)
    
    # 测试统计计算
    numbers = [10, 20, 30, 40, 50]
    stats = calculate_statistics(numbers)
    print(f"\n统计结果: {stats}\n")
    
    # 测试报告生成
    report = format_report(stats, "数据统计报告")
    print(report)
    print()
    
    # 测试任务执行
    executor = TaskExecutor("数据处理任务")
    steps = ["加载数据", "清洗数据", "转换数据", "保存结果"]
    executor.execute(steps)
    print()
    
    # 测试集成
    integrate_with_module_a()
