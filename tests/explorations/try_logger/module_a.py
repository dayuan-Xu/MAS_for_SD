"""
模块 A - 模拟业务模块

演示在多模块项目中如何使用 logger：
- 使用 __name__ 获取模块专属的 logger
- 不需要重复配置，自动继承根 logger 的配置
- 日志会自动带上模块名称，方便追踪来源
"""

import logging

# 关键：使用 __name__ 作为 logger 名称
# 这样会自动形成层级：try_logger.module_a
logger = logging.getLogger(__name__)


def process_data(data: list) -> list:
    """处理数据列表"""
    logger.info(f"开始处理数据，共 {len(data)} 条")
    
    if not data:
        logger.warning("接收到空数据列表")
        return []
    
    result = []
    for i, item in enumerate(data):
        try:
            # 模拟数据处理
            processed = item * 2
            result.append(processed)
            logger.debug(f"处理第 {i+1} 条数据: {item} -> {processed}")
        except Exception as e:
            logger.error(f"处理第 {i+1} 条数据时出错: {e}", exc_info=True)
    
    logger.info(f"数据处理完成，成功 {len(result)} 条")
    return result


def validate_user(username: str, age: int) -> bool:
    """验证用户信息"""
    logger.debug(f"验证用户: {username}, 年龄: {age}")
    
    if not username:
        logger.warning("用户名为空")
        return False
    
    if age < 0 or age > 150:
        logger.error(f"用户 {username} 年龄不合法: {age}")
        return False
    
    logger.info(f"用户 {username} 验证通过")
    return True


class DataService:
    """数据服务类 - 演示在类中使用 logger"""
    
    def __init__(self, name: str):
        self.name = name
        # 在类中也使用 __name__，会显示为 try_logger.module_a.DataService
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"DataService '{name}' 初始化")
    
    def fetch_data(self, source: str) -> list:
        """从数据源获取数据"""
        self.logger.info(f"从 {source} 获取数据")
        
        # 模拟数据获取
        if source == "database":
            self.logger.debug("连接数据库...")
            data = [1, 2, 3, 4, 5]
            self.logger.info(f"从数据库获取 {len(data)} 条数据")
        elif source == "api":
            self.logger.debug("调用 API...")
            data = [10, 20, 30]
            self.logger.info(f"从 API 获取 {len(data)} 条数据")
        else:
            self.logger.error(f"不支持的数据源: {source}")
            raise ValueError(f"未知数据源: {source}")
        
        return data
    
    def save_data(self, data: list, destination: str):
        """保存数据到目标位置"""
        self.logger.info(f"保存 {len(data)} 条数据到 {destination}")
        
        if not data:
            self.logger.warning("没有数据需要保存")
            return
        
        # 模拟保存操作
        self.logger.debug(f"正在写入 {destination}...")
        self.logger.info(f"数据已成功保存到 {destination}")


if __name__ == "__main__":
    # 单独运行此模块时的测试代码
    from config_logging import setup_logging
    setup_logging()
    
    print("\n测试模块 A:")
    print("-" * 60)
    
    # 测试函数
    data = [1, 2, 3, 4, 5]
    result = process_data(data)
    print(f"处理结果: {result}\n")
    
    # 测试验证
    validate_user("张三", 25)
    validate_user("", 25)
    validate_user("李四", -1)
    print()
    
    # 测试类
    service = DataService("TestService")
    fetched = service.fetch_data("database")
    service.save_data(fetched, "output.txt")
