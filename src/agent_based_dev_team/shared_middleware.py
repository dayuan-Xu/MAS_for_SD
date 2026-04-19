"""
共享的中间件实例模块

提供团队中所有专家智能体共享使用的中间件实例，确保一致的行为和配置。
"""

from src.agent_based_dev_team.my_middleware import MyRetryMiddleware

# 创建全局共享的重试中间件实例
# 配置说明：
# - max_retries=5: 最多重试5次（应对临时服务过载）
# - initial_wait=2.0: 首次等待2秒（给服务器恢复时间）
# - max_wait=60.0: 最长等待60秒（避免无限等待）
# - exponential_base=2.0: 指数退避基数（2s → 4s → 8s → 16s → 32s）
# - jitter=True: 启用随机抖动（±25%，避免惊群效应）
# - enabled=True: 默认启用重试功能
shared_retry_middleware = MyRetryMiddleware(
    max_retries=5,
    initial_wait=2.0,
    max_wait=60.0,
    exponential_base=2.0,
    jitter=True,
    enabled=True
)
