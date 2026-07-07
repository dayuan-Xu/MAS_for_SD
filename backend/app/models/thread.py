from sqlalchemy import Column, Integer, String, ForeignKey
from datetime import datetime

from ..core.database import Base


class ThreadModel(Base):
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    thread_id = Column(String(255), nullable=True, index=True, comment="LangGraph线程ID，用于恢复智能体状态")
    context_box_name = Column(String(255), nullable=True, comment="AgentBay上下文盒子名称")
    context_box_id = Column(String(255), nullable=True, comment="AgentBay上下文盒子ID")
    created_at = Column(String(255), default=lambda: datetime.now().isoformat())

    def __repr__(self):
        return f"<Thread(id={self.id}, task_id={self.task_id}, thread_id={self.thread_id})>"
