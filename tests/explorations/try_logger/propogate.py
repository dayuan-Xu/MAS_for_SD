from pathlib import Path

import logging
from logging.handlers import RotatingFileHandler

# 配置
log_path = Path("logs")
log_path.mkdir(exist_ok=True)

# 根 logger
root = logging.getLogger()
root.setLevel(logging.DEBUG)
console = logging.StreamHandler()
console.setFormatter(logging.Formatter('CONSOLE: %(name)s - %(message)s'))
root.addHandler(console)

# 第三方 logger
third_party = logging.getLogger("agentbay")
third_party.setLevel(logging.DEBUG)

# 添加文件 Handler
file_handler = RotatingFileHandler(log_path / "agentbay.log")
file_handler.setFormatter(logging.Formatter('FILE: %(name)s - %(message)s'))
third_party.addHandler(file_handler)

# 测试 1: propagate = True（默认）
print("\n=== 测试 1: propagate = True ===")
third_party.propagate = True
third_party.info("测试消息 1")
# 输出：
# CONSOLE: agentbay - 测试消息 1  ← 控制台有
# FILE: agentbay - 测试消息 1    ← 文件也有

# 测试 2: propagate = False
print("\n=== 测试 2: propagate = False ===")
third_party.propagate = False
third_party.info("测试消息 2")
# 输出：
# （控制台没有输出）← 被阻止了
# FILE: agentbay - 测试消息 2    ← 文件仍有
