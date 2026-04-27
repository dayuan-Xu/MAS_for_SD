import logging
import random
import sys
import time
from typing import Callable

import httpcore
import httpx
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from openai import InternalServerError, APIError


class MyRetryMiddleware(AgentMiddleware):
    """智能重试中间件，处理各类网络和服务端错误

    特性：
    - 针对 MiniMax 529 错误和标准 5xx 错误进行重试
    - 支持网络超时错误（ReadTimeout、ConnectTimeout 等）
    - 指数退避 + 随机抖动策略
    - 可配置的最大重试次数和等待时间
    - 智能识别可重试错误，避免无效重试
    """

    def __init__(
            self,
            max_retries: int = 5,
            initial_wait: float = 2.0,
            max_wait: float = 60.0,
            exponential_base: float = 2.0,
            jitter: bool = True,
            retryable_status_codes: set = None,
            enabled: bool = True
    ):
        """初始化重试中间件

        Args:
            max_retries: 最大重试次数（不包括首次尝试）
            initial_wait: 首次重试等待时间（秒）
            max_wait: 最大等待时间（秒）
            exponential_base: 指数退避基数
            jitter: 是否启用随机抖动
            retryable_status_codes: 可重试的 HTTP 状态码集合
            enabled: 是否启用重试功能
        """
        self.max_retries = max_retries
        self.initial_wait = initial_wait
        self.max_wait = max_wait
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.enabled = enabled

        # 默认重试的状态码：529 (MiniMax过载) + 标准5xx错误
        self.retryable_status_codes = retryable_status_codes or {529, 500, 502, 503, 504}

        self.logger = logging.getLogger(__name__)

    def _calculate_wait_time(self, attempt: int) -> float:
        """计算等待时间（指数退避 + 可选的随机抖动）

        Args:
            attempt: 当前重试次数（从0开始）

        Returns:
            等待时间（秒）
        """
        # 指数退避：initial_wait * (exponential_base ^ attempt)
        wait_time = self.initial_wait * (self.exponential_base ** attempt)

        # 限制最大等待时间
        wait_time = min(wait_time, self.max_wait)

        # 添加随机抖动（±25%）
        if self.jitter:
            jitter_range = wait_time * 0.25
            wait_time = wait_time + random.uniform(-jitter_range, jitter_range)
            wait_time = max(0.1, wait_time)  # 确保至少等待0.1秒

        return wait_time

    def _is_retryable_error(self, exception: Exception) -> tuple[bool, str]:
        """判断错误是否可重试

        Args:
            exception: 捕获的异常

        Returns:
            (是否可重试, 错误描述)
        """
        # ========== 1. 检查网络超时错误（最常见且应该重试）==========
        # httpx 层的超时异常（OpenAI SDK 使用 httpx 作为 HTTP 客户端）
        if isinstance(exception, httpx.ReadTimeout):
            return True, f"读取超时（httpx.ReadTimeout）: {exception}"

        if isinstance(exception, httpx.ConnectTimeout):
            return True, f"连接超时（httpx.ConnectTimeout）: {exception}"

        if isinstance(exception, httpx.WriteTimeout):
            return True, f"写入超时（httpx.WriteTimeout）: {exception}"

        if isinstance(exception, httpx.PoolTimeout):
            return True, f"连接池超时（httpx.PoolTimeout）: {exception}"

        # httpcore 层的超时异常（更底层的网络库）
        if isinstance(exception, httpcore.ReadTimeout):
            return True, f"底层读取超时（httpcore.ReadTimeout）: {exception}"

        if isinstance(exception, httpcore.ConnectTimeout):
            return True, f"底层连接超时（httpcore.ConnectTimeout）: {exception}"

        # ========== 2. 检查 OpenAI API 错误 ==========
        if isinstance(exception, (InternalServerError, APIError)):
            status_code = getattr(exception, 'status_code', None)

            if status_code in self.retryable_status_codes:
                error_msg = str(exception)
                if status_code == 529:
                    return True, f"MiniMax服务过载(HTTP 529): {error_msg}"
                else:
                    return True, f"服务器错误(HTTP {status_code}): {error_msg}"

        # ========== 3. 检查异常消息中的关键词 ==========
        error_str = str(exception).lower()

        # 服务过载相关关键词
        if any(keyword in error_str for keyword in [
            '529', 'overloaded', '负载较高', '服务繁忙'
        ]):
            return True, f"检测到服务过载错误: {exception}"

        # 超时相关关键词
        if any(keyword in error_str for keyword in [
            'timeout', 'timed out', '超时', 'read timeout', 'connect timeout'
        ]):
            return True, f"检测到超时错误: {exception}"

        # 网络连接相关关键词（临时性网络问题）
        if any(keyword in error_str for keyword in [
            'connection reset', 'connection refused', 'network error',
            'connection aborted', 'broken pipe'
        ]):
            return True, f"检测到网络连接错误: {exception}"

        # ========== 4. 其他不可重试的错误 ==========
        return False, ""

    def wrap_model_call(
            self,
            request: ModelRequest,
            handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """包装模型调用，添加智能重试逻辑"""

        # 如果未启用重试，直接调用 handler
        if not self.enabled:
            return handler(request)

        last_exception = None

        for attempt in range(self.max_retries + 1):  # +1 是因为首次尝试不算重试
            try:
                # 首次尝试或重试后调用 handler
                if attempt == 0:
                    self.logger.info("📡 [LLM调用] 开始第1次尝试...")
                    # ⭐ 强制刷新日志，确保立即输出

                    for h in self.logger.handlers:
                        h.flush()
                    sys.stdout.flush()
                    sys.stderr.flush()
                    return handler(request)
                else:
                    # 重试时打印日志
                    separator = "=" * 83
                    self.logger.warning(separator)
                    self.logger.warning(f"🔄 RetryMiddleware - 第 {attempt}/{self.max_retries} 次重试...")
                    self.logger.warning(separator)
                    # 强制刷新所有handler
                    for h in self.logger.handlers:
                        h.flush()
                    sys.stdout.flush()
                    sys.stderr.flush()
                    return handler(request)

            except Exception as e:
                last_exception = e

                # ⭐ 关键：记录所有捕获的异常，便于调试
                self.logger.error(f"⚠️ 捕获到异常类型: {type(e).__name__}")
                self.logger.error(f"⚠️ 异常信息: {e}")
                self.logger.error(f"⚠️ 异常模块: {type(e).__module__}")

                # 检查是否是可重试的错误
                is_retryable, error_desc = self._is_retryable_error(e)

                if not is_retryable:
                    # 不可重试的错误，直接抛出
                    separator = "=" * 83
                    self.logger.error(separator)
                    self.logger.error(f"❌ RetryMiddleware - 遇到不可重试的错误: {e}")
                    self.logger.error(f"   异常类型: {type(e).__name__}")
                    self.logger.error(separator)
                    raise

                # 如果是最后一次尝试，抛出异常
                if attempt >= self.max_retries:
                    separator = "=" * 83
                    self.logger.error(separator)
                    self.logger.error(f"❌ RetryMiddleware - 已达到最大重试次数({self.max_retries})，放弃重试")
                    self.logger.error(separator)
                    self.logger.error(f"最后错误: {error_desc}")
                    raise

                # 计算等待时间
                wait_time = self._calculate_wait_time(attempt)

                # 打印重试信息
                separator = "=" * 83
                self.logger.warning(separator)
                self.logger.warning(f"⚠️  RetryMiddleware - {error_desc}")
                self.logger.warning(f"⏱️  等待 {wait_time:.2f} 秒后重试... (第{attempt + 1}/{self.max_retries}次)")
                self.logger.warning(separator)

                # ⭐ 强制刷新日志
                for h in self.logger.handlers:
                    h.flush()
                sys.stdout.flush()
                sys.stderr.flush()

                # 等待后重试
                time.sleep(wait_time)

        # 理论上不会到达这里，但为了类型安全
        raise last_exception
