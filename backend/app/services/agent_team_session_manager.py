import asyncio
import datetime
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.agent_team import AgentTeam

logger = logging.getLogger(__name__)


class AgentTeamSession:
    """单个AgentTeam会话的封装"""

    def __init__(self, agent_team: AgentTeam, db: AsyncSession):
        self.agent_team = agent_team
        self.db = db
        self.last_access_time = datetime.datetime.now()
        self.last_release_time = datetime.datetime.now()
        self.lock = asyncio.Lock()
        self.msg_ids_sent_to_frontend: set[str] = set()
        self.cancel_event = asyncio.Event()


class AgentTeamSessionManager:
    """AgentTeam会话管理器（单例）"""

    def __init__(self):
        self.sessions: dict[str, AgentTeamSession] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def get_agent_team(self, thread_id: str | None = None) -> AgentTeam | None:
        """尝试获取AgentTeam实例

        Args:
            thread_id: ThreadModel.thread_id（LangGraph线程ID，字符串类型），用于查找已存在的会话

        Returns:
            AgentTeam: 表示存在相应的AgentTeamSession实例
            None: None表示不存在存在相应的AgentTeamSession实例
        """
        async with self._lock:
            if thread_id and thread_id in self.sessions:
                session = self.sessions[thread_id]
                session.last_access_time = datetime.datetime.now()
                return session.agent_team
            else:
                return None

    async def create_agent_team(
        self,
        task_name: str,
        thread_id: str | None = None,
        db: AsyncSession = None,
    ) -> AgentTeam:
        """创建AgentTeam实例和相应的AgentTeamSession

        Args:
            thread_id: ThreadModel.thread_id（LangGraph线程ID，字符串类型），用于棕地开发恢复会话；为空时创建新会话

        Returns:
            agent_team: 新创建的AgentTeam实例
        """
        async with self._lock:
            temp_session = AgentTeamSession(
                agent_team=None,  # type: ignore
                db=db,
            )

            agent_team = await AgentTeam.create_with_agentbay_mcp(
                task_name=task_name,
                thread_id=thread_id,
                db=db,
                cancel_event=temp_session.cancel_event,
            )

            temp_session.agent_team = agent_team
            self.sessions[agent_team.thread_id] = temp_session

            if self._cleanup_task is None:
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            return agent_team

    async def try_acquire_session(
        self,
        thread_id: str,
    ) -> tuple[AgentTeamSession | None, bool]:
        """尝试获取session并获取锁（非阻塞）

        Args:
            thread_id: ThreadModel.thread_id（LangGraph线程ID，字符串类型），用于查找会话

        Returns:
            (session, acquired): acquired表示是否成功获取锁
        """
        async with self._lock:
            if thread_id not in self.sessions:
                return None, False

            session = self.sessions[thread_id]
            session.last_access_time = datetime.datetime.now()

            # 非阻塞检查：锁已被占用则立即返回 False
            if session.lock.locked():
                return session, False

        # 锁当前空闲，立即获取
        await session.lock.acquire()
        return session, True

    async def release_session(self, thread_id: str):
        """释放session的锁

        Args:
            thread_id: ThreadModel.thread_id（LangGraph线程ID，字符串类型），用于查找会话
        """
        async with self._lock:
            if thread_id in self.sessions:
                session = self.sessions[thread_id]

                sandbox_expired = False
                if (
                    hasattr(session.agent_team, "sandbox")
                    and session.agent_team.sandbox
                ):
                    sandbox_expired = getattr(
                        session.agent_team.sandbox, "sandbox_expired", False
                    )

                try:
                    session.lock.release()
                except RuntimeError:
                    pass

                if sandbox_expired:
                    logger.warning(
                        f"释放AgentTeamSession时发现沙盒已过期，自动销毁AgentTeamSession: {thread_id}"
                    )
                    await self._cleanup_session(session)
                    del self.sessions[thread_id]
                else:
                    session.last_release_time = datetime.datetime.now()

    async def is_session_running(self, thread_id: str) -> bool:
        """检查session是否正在运行（锁是否被占用）

        Args:
            thread_id: ThreadModel.thread_id（LangGraph线程ID，字符串类型），用于查找会话
        """
        async with self._lock:
            if thread_id not in self.sessions:
                return False

            session = self.sessions[thread_id]
            return session.lock.locked()

    async def request_cancel(self, thread_id: str) -> bool:
        """请求中止指定 thread 的智能体团队执行

        Args:
            thread_id: ThreadModel.thread_id（LangGraph线程ID，字符串类型），用于查找会话

        Returns:
            True 如果成功设置中止标志，False 如果会话不存在或未运行
        """
        async with self._lock:
            if thread_id not in self.sessions:
                logger.warning(f"请求中止失败：会话不存在，thread_id={thread_id}")
                return False

            session = self.sessions[thread_id]
            if not session.lock.locked():
                logger.warning(f"请求中止失败：会话未在运行，thread_id={thread_id}")
                return False

            session.cancel_event.set()
            logger.info(f"🛑 已设置中止标志，thread_id={thread_id}")
            return True

    def is_cancelled(self, thread_id: str) -> bool:
        """检查指定 thread 是否已被请求中止

        Args:
            thread_id: ThreadModel.thread_id（LangGraph线程ID，字符串类型），用于查找会话

        Returns:
            True 如果已请求中止，False 否则
        """
        if thread_id not in self.sessions:
            return False
        return self.sessions[thread_id].cancel_event.is_set()

    async def get_task_session_status(self, thread_ids: list[str]) -> dict:
        """根据一组 thread_id 聚合判断任务级别的运行状态

        Args:
            thread_ids: 某个任务对应的所有 ThreadModel.thread_id（LangGraph线程ID，字符串类型）列表

        Returns:
            {
                "has_alive_session": bool,  # 是否存在未销毁的 session
                "has_running_session": bool,  # 是否存在运行中的 session
                "running_thread_ids": list[str],  # 正在运行的 ThreadModel.thread_id（字符串类型）列表
                "session_details": dict[str, dict],  # 每个 session 的详细信息
            }
        """
        async with self._lock:
            has_alive = False
            has_running = False
            running_thread_ids = []
            session_details = {}
            for thread_id in thread_ids:
                if thread_id in self.sessions:
                    has_alive = True
                    session = self.sessions[thread_id]
                    is_running = session.lock.locked()
                    if is_running:
                        has_running = True
                        running_thread_ids.append(thread_id)
                    session_details[thread_id] = {
                        "is_alive": True,
                        "is_running": is_running,
                        "last_access_time": session.last_access_time.isoformat(),
                    }
            return {
                "has_alive_session": has_alive,
                "has_running_session": has_running,
                "running_thread_ids": running_thread_ids,
                "session_details": session_details,
            }

    async def destroy(self, thread_id: str):
        """显式销毁指定thread_id的会话

        Args:
            thread_id: ThreadModel.thread_id（LangGraph线程ID，字符串类型），用于查找会话
        """
        async with self._lock:
            if thread_id in self.sessions:
                session = self.sessions.pop(thread_id)
                try:
                    session.lock.release()
                except RuntimeError:
                    pass
                await self._cleanup_session(session)

    async def _cleanup_loop(self):
        """后台清理循环：定期检查并清理超时会话"""
        while True:
            await asyncio.sleep(60)
            await self._cleanup_expired_sessions()

    async def _cleanup_expired_sessions(self):
        """清理过期会话（空闲超过30分钟或沙盒会话过期）"""
        now = datetime.datetime.now()
        expired_thread_ids = []

        async with self._lock:
            for thread_id, session in self.sessions.items():
                sandbox_expired = False
                if (
                    hasattr(session.agent_team, "sandbox")
                    and session.agent_team.sandbox
                ):
                    sandbox_expired = getattr(
                        session.agent_team.sandbox, "sandbox_expired", False
                    )

                if sandbox_expired:
                    logger.warning(f"沙盒会话已过期，强制清理: {thread_id}")
                    expired_thread_ids.append(thread_id)
                    continue

                if session.lock.locked():
                    continue
                if (now - session.last_release_time).total_seconds() > 30 * 60:
                    expired_thread_ids.append(thread_id)

            for thread_id in expired_thread_ids:
                session = self.sessions.pop(thread_id)
                try:
                    session.lock.release()
                except RuntimeError:
                    pass
                asyncio.create_task(self._cleanup_session(session))

    async def _cleanup_session(self, session: AgentTeamSession):
        """清理单个会话资源"""
        try:
            session.agent_team.download_and_cleanup()
        except Exception as e:
            logger.error(f"清理会话资源失败: {e}", exc_info=True)


session_manager = AgentTeamSessionManager()
