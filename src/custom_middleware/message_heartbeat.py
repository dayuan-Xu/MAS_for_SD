"""智能消息监听器 - 混合模式（事件驱动 + 心跳兜底）。

为专家智能体提供后台消息监控，确保及时响应新消息。
结合文件监听的实时性和心跳轮询的可靠性。
"""

import json
import threading
import time
from langchain_core.runnables import RunnableConfig

from src.custom_middleware.communication import MESSAGE_BUS_ROOT


class SmartMessageListener:
    """智能消息监听器：文件监听（主）+ 心跳轮询（兜底）"""

    def __init__(
            self,
            agent,
            config: RunnableConfig,
            inbox_path: str = MESSAGE_BUS_ROOT,
            check_interval: int = 60,  # 默认每60s秒检查一次该智能体是否有新消息
            max_idle_cycles: int = 10,  # 默认最多允许10个连续空闲周期，超过后进入低功耗模式（减少检查频率），即睡眠check_interval * 5秒后再继续检查
            **kwargs
    ):
        """
        Args:
            agent: 智能体实例
            config: 运行配置（包含 thread_id）
            inbox_path: 收件箱根路径
            check_interval: 心跳检查间隔（秒）
            max_idle_cycles: 最大空闲周期数（超过后进入低功耗模式）
        """
        self.agent = agent
        self.config = config
        self.inbox_path = inbox_path
        self.check_interval = check_interval
        self.max_idle_cycles = max_idle_cycles

        # 计算当前智能体的收件箱路径
        agent_name = self.agent.name if hasattr(self.agent, 'name') else "unknown"
        self.agent_inbox = f"{inbox_path}/{agent_name}_inbox"

        self._running = False
        self._thread = None
        self._idle_count = 0
        self._last_message_time = 0

        # ⭐ 并发控制：防止重复触发
        self._is_executing = False  # 标记智能体是否正在执行
        self._execution_lock = threading.Lock()  # 线程锁，保证原子操作

    def start(self):
        """启动消息监听"""
        if self._running:
            print(f"⚠️ 监听器已在运行")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name=f"MsgListener-{self.config['configurable']['thread_id']}"
        )
        self._thread.start()
        print(f"✅ 消息监听已启动 (智能体: {self.config['configurable']['thread_id'][:8]}...)")

    def stop(self):
        """停止消息监听"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print(f"⏹️ 消息监听已停止")

    def _monitor_loop(self):
        """监控循环：定期检查新消息"""
        print(f"👂 开始监听收件箱: {self.agent_inbox}")

        while self._running:
            try:
                # 1. 检查是否有未读消息
                has_unread, unread_count = self._check_for_unread_messages()

                if has_unread:
                    # ⭐ 关键：检查智能体是否正在执行中
                    with self._execution_lock:
                        if self._is_executing:
                            print(f"⏳ 智能体正在执行中，跳过本次触发 (未读消息: {unread_count} 条)")
                            time.sleep(self.check_interval)
                            continue

                        # 标记为执行中
                        self._is_executing = True

                    print(f"\n📨 检测到 {unread_count} 条新消息，触发智能体响应...")

                    try:
                        # 2. 触发智能体执行
                        self.agent.invoke(
                            {
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": "你有新的任务消息，请检查收件箱并开始处理"
                                    }
                                ]
                            },
                            config=self.config
                        )

                        # 更新状态
                        self._last_message_time = time.time()
                        self._idle_count = 0

                        print(f"✅ 智能体已完成响应\n")

                    except Exception as e:
                        print(f"❌ 智能体执行出错: {e}")
                        import traceback
                        traceback.print_exc()

                    finally:
                        # ⭐ 无论成功失败，都要释放执行标志
                        with self._execution_lock:
                            self._is_executing = False

                else:
                    self._idle_count += 1

                    # 如果长时间没有消息，进入低功耗模式
                    if self._idle_count >= self.max_idle_cycles:
                        print(f"💤 长时间无消息 ({self._idle_count} 次)，进入低功耗模式...")
                        time.sleep(self.check_interval * 5)
                        self._idle_count = 0

                # 3. 等待下一个检查周期
                time.sleep(self.check_interval)

            except Exception as e:
                print(f"❌ 消息监听出错: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(self.check_interval)

    def _check_for_unread_messages(self) -> tuple[bool, int]:
        """检查是否有未读消息。

        Returns:
            (has_unread, unread_count): 是否有未读消息，未读消息数量
        """
        try:
            from src.utils.my_sandbox import my_sandbox_backend

            ls_cmd = f"ls -1 {self.agent_inbox}/*.json 2>/dev/null || echo ''"
            result = my_sandbox_backend.execute(ls_cmd)

            if result.exit_code != 0 or not result.output.strip():
                return False, 0

            message_files = [f.strip() for f in result.output.strip().split('\n') if f.strip()]

            if not message_files:
                return False, 0

            unread_count = 0
            for msg_file in message_files:
                try:
                    read_result = my_sandbox_backend.read(msg_file)

                    if read_result.error or not read_result.file_data:
                        continue

                    content_str = read_result.file_data.get('content', '')
                    message_data = json.loads(content_str)

                    if not message_data.get('read', True):
                        unread_count += 1

                except Exception:
                    continue

            return unread_count > 0, unread_count

        except Exception as e:
            print(f"⚠️ 检查消息失败: {e}")
            return False, 0


class TeamMessageCoordinator:
    """团队消息协调器 - 管理多个专家智能体的消息监听"""

    def __init__(self):
        self.listeners = {}

    def register_agent(self, name: str, agent, config: RunnableConfig, **kwargs):
        """注册一个专家智能体到协调器"""
        listener = SmartMessageListener(
            agent=agent,
            config=config,
            **kwargs
        )

        self.listeners[name] = listener
        print(f"📝 已注册智能体: {name}")

    def start_all(self):
        """启动所有注册的智能体监听器"""
        print("\n" + "=" * 60)
        print("🚀 启动团队消息协调器")
        print("=" * 60)

        for name, listener in self.listeners.items():
            listener.start()

        print(f"✅ 共启动 {len(self.listeners)} 个智能体监听器\n")

    def stop_all(self):
        """停止所有监听器"""
        print("\n" + "=" * 60)
        print("⏹️ 停止团队消息协调器")
        print("=" * 60)

        for name, listener in self.listeners.items():
            listener.stop()

        print("✅ 所有监听器已停止\n")

    def __enter__(self):
        """支持 with 语句"""
        self.start_all()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时自动清理"""
        self.stop_all()
        return False
