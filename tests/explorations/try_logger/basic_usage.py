"""
基础用法示例 - 演示 logging 的基本操作

适合初学者快速上手，展示最常用的日志记录方式。
"""

import logging


def basic_example():
    """最基础的日志使用"""
    print("=" * 60)
    print("示例 1: 基础日志使用")
    print("=" * 60)
    
    # 获取 logger（使用 __name__ 作为名称）
    logger = logging.getLogger(__name__)
    
    # 配置基本的控制台输出
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    
    # 记录不同级别的日志
    logger.debug("这是 DEBUG 级别 - 详细的调试信息")
    logger.info("这是 INFO 级别 - 一般的信息")
    logger.warning("这是 WARNING 级别 - 警告信息")
    logger.error("这是 ERROR 级别 - 错误信息")
    logger.critical("这是 CRITICAL 级别 - 严重错误")
    
    print()


def variable_logging():
    """记录包含变量的日志"""
    print("=" * 60)
    print("示例 2: 记录变量")
    print("=" * 60)
    
    logger = logging.getLogger(__name__)
    
    username = "张三"
    age = 25
    score = 95.5
    
    # 方式 1: 使用 f-string（推荐）
    logger.info(f"用户 {username} 年龄 {age} 岁，得分 {score}")
    
    # 方式 2: 使用 % 格式化（传统方式）
    logger.info("用户 %s 年龄 %d 岁，得分 %.2f", username, age, score)
    
    # 方式 3: 使用 .format()
    logger.info("用户 {} 年龄 {} 岁，得分 {}".format(username, age, score))
    
    print()


def exception_logging():
    """记录异常信息"""
    print("=" * 60)
    print("示例 3: 记录异常")
    print("=" * 60)
    
    logger = logging.getLogger(__name__)
    
    try:
        result = 10 / 0
    except ZeroDivisionError as e:
        # 方式 1: 使用 exc_info=True（推荐，会记录完整堆栈）
        logger.error(f"发生除零错误: {e}", exc_info=True)
    
    print()
    
    try:
        data = {"key": "value"}
        value = data["nonexistent"]
    except KeyError as e:
        # 方式 2: 使用 logger.exception()（等价于 error + exc_info=True）
        logger.exception(f"键不存在: {e}")
    
    print()


def conditional_logging():
    """条件日志记录"""
    print("=" * 60)
    print("示例 4: 条件日志")
    print("=" * 60)
    
    logger = logging.getLogger(__name__)
    
    items = [1, 2, 3, 4, 5]
    
    # 只在满足条件时记录
    if len(items) > 10:
        logger.warning(f"列表长度超过限制: {len(items)}")
    else:
        logger.info(f"列表长度正常: {len(items)}")
    
    # 使用 isEnabledFor 避免不必要的字符串拼接
    if logger.isEnabledFor(logging.DEBUG):
        debug_info = f"详细数据: {items}"  # 只有在 DEBUG 级别时才执行
        logger.debug(debug_info)
    
    print()


if __name__ == "__main__":
    basic_example()
    variable_logging()
    exception_logging()
    conditional_logging()
    
    print("\n✓ 基础示例运行完成！")
    print("提示: 查看 config_logging.py 了解多模块项目的最佳实践")
