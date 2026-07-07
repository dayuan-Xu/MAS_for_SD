from collections.abc import Sequence
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.thread import ThreadModel


class ThreadDAO:
    @staticmethod
    async def create(db: AsyncSession, thread_data: dict) -> ThreadModel:
        thread = ThreadModel(
            task_id=thread_data["task_id"],
            thread_id=thread_data.get("thread_id"),
            context_box_name=thread_data.get("context_box_name"),
            context_box_id=thread_data.get("context_box_id"),
        )
        db.add(thread)
        await db.commit()
        await db.refresh(thread)
        return thread

    @staticmethod
    async def get_by_id(db: AsyncSession, thread_id: int) -> ThreadModel | None:
        """根据 ThreadModel.id（数据库主键，数字类型）获取线程记录"""
        result = await db.execute(
            select(ThreadModel).where(ThreadModel.id == thread_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_task_id(db: AsyncSession, task_id: int) -> Sequence[ThreadModel]:
        result = await db.execute(
            select(ThreadModel).where(ThreadModel.task_id == task_id)
        )
        return result.scalars().all()

    @staticmethod
    async def get_by_thread_id(db: AsyncSession, thread_id: str) -> ThreadModel | None:
        """根据 ThreadModel.thread_id（LangGraph线程ID，字符串类型）获取线程记录"""
        result = await db.execute(
            select(ThreadModel).where(ThreadModel.thread_id == thread_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_thread_info(db: AsyncSession, thread_id: int, thread_info: dict):
        """更新线程记录信息

        Args:
            thread_id: ThreadModel.id（数据库主键，数字类型）
            thread_info: 更新的字段，其中 "thread_id" 对应 ThreadModel.thread_id（LangGraph线程ID，字符串类型）
        """
        thread = await ThreadDAO.get_by_id(db, thread_id)
        if thread:
            if "thread_id" in thread_info:
                thread.thread_id = thread_info["thread_id"]
            if "context_box_name" in thread_info:
                thread.context_box_name = thread_info["context_box_name"]
            if "context_box_id" in thread_info:
                thread.context_box_id = thread_info["context_box_id"]
            await db.commit()
            await db.refresh(thread)
        return thread

    @staticmethod
    async def delete(db: AsyncSession, thread_id: int) -> bool:
        """根据 ThreadModel.id（数据库主键，数字类型）删除线程记录"""
        result = await db.execute(
            select(ThreadModel).where(ThreadModel.id == thread_id)
        )
        thread = result.scalar_one_or_none()
        if not thread:
            return False
        await db.execute(delete(ThreadModel).where(ThreadModel.id == thread_id))
        await db.commit()
        return True

    @staticmethod
    async def delete_by_task_id(db: AsyncSession, task_id: int) -> bool:
        result = await db.execute(
            select(ThreadModel).where(ThreadModel.task_id == task_id)
        )
        threads = result.scalars().all()
        if not threads:
            return False
        await db.execute(delete(ThreadModel).where(ThreadModel.task_id == task_id))
        await db.commit()
        return True
