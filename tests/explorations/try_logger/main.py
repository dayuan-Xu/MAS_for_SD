"""
主程序入口 - 演示多模块项目的完整日志流程

这是实际项目中的典型用法：
1. 在程序启动时配置日志系统（只配置一次）
2. 导入各个业务模块
3. 各模块使用自己的 logger 记录日志
4. 所有日志统一输出到控制台和文件
"""

import logging
import sys
from pathlib import Path

# 添加父目录到路径，以便导入同级模块
sys.path.insert(0, str(Path(__file__).parent))

# 第一步：配置日志系统（只需配置一次）
from config_logging import setup_logging

# 第二步：导入业务模块
from module_a import process_data, validate_user, DataService
from module_b import calculate_statistics, format_report, TaskExecutor


def main():
    """主函数 - 演示完整的业务流程"""
    
    # 获取主模块的 logger
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("应用程序启动")
    logger.info("=" * 60)
    
    try:
        # 业务流程 1: 用户验证
        logger.info("\n[阶段 1] 用户验证")
        logger.info("-" * 40)
        
        if validate_user("张三", 25):
            logger.info("用户验证通过，继续处理")
        else:
            logger.error("用户验证失败，终止流程")
            return
        
        # 业务流程 2: 数据处理
        logger.info("\n[阶段 2] 数据处理")
        logger.info("-" * 40)
        
        raw_data = [1, 2, 3, 4, 5]
        logger.info(f"原始数据: {raw_data}")
        
        processed_data = process_data(raw_data)
        logger.info(f"处理后数据: {processed_data}")
        
        # 业务流程 3: 统计分析
        logger.info("\n[阶段 3] 统计分析")
        logger.info("-" * 40)
        
        stats = calculate_statistics(processed_data)
        if stats:
            report = format_report(stats, "数据处理统计报告")
            logger.info(f"\n{report}")
        
        # 业务流程 4: 使用服务类
        logger.info("\n[阶段 4] 数据服务")
        logger.info("-" * 40)
        
        service = DataService("MainService")
        fetched_data = service.fetch_data("database")
        processed = process_data(fetched_data)
        service.save_data(processed, "output.json")
        
        # 业务流程 5: 任务执行
        logger.info("\n[阶段 5] 任务执行")
        logger.info("-" * 40)
        
        executor = TaskExecutor("完整业务流程")
        steps = [
            "初始化系统",
            "加载配置",
            "验证用户",
            "处理数据",
            "生成报告",
            "保存结果"
        ]
        success = executor.execute(steps)
        
        if success:
            logger.info("✓ 所有任务执行成功")
        else:
            logger.warning("⚠ 部分任务执行失败，请检查日志")
        
        # 完成
        logger.info("\n" + "=" * 60)
        logger.info("应用程序运行完成")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.critical(f"应用程序发生严重错误: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # 配置日志系统
    setup_logging(
        log_level=logging.DEBUG,  # 开发环境使用 DEBUG
        log_dir="logs",
        log_file="app.log",
        console_output=True
    )
    
    # 运行主程序
    main()
    
    print("\n" + "=" * 60)
    print("✓ 程序执行完成！")
    print("=" * 60)
    print("\n提示:")
    print("1. 查看控制台输出的简洁日志")
    print("2. 查看 logs/app.log 获取详细日志（包含模块名、函数名、行号）")
    print("3. 查看 logs/error.log 获取所有错误日志")
    print("\n观察重点:")
    print("- 不同模块的日志带有不同的名称（main, module_a, module_b）")
    print("- 同一级别的日志在文件和控制台的格式可能不同")
    print("- ERROR 及以上级别的日志会同时写入 error.log")
