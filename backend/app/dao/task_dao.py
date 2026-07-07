from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError

from ..models.task import TaskModel, TaskStatus


class TaskDAO:
    """任务表数据访问对象"""

    @staticmethod
    async def create(db: AsyncSession, task_data: dict) -> TaskModel:
        """创建任务"""
        existing_task = await db.execute(
            select(TaskModel).where(TaskModel.name == task_data["name"])
        )
        if existing_task.scalar_one_or_none():
            raise ValueError(f"任务名称 '{task_data['name']}' 已存在")

        task = TaskModel(
            name=task_data["name"],
            description=task_data.get("description", ""),
        )

        db.add(task)
        await db.commit()
        await db.refresh(task)

        return task

    @staticmethod
    async def get_by_id(db: AsyncSession, task_id: int) -> TaskModel | None:
        """根据ID获取任务"""
        result = await db.execute(select(TaskModel).where(TaskModel.id == task_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(db: AsyncSession, name: str) -> TaskModel | None:
        """根据名称获取任务"""
        result = await db.execute(select(TaskModel).where(TaskModel.name == name))
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        search: str = "",
        status: str = "",
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> dict:
        """分页查询任务列表"""
        query = select(TaskModel)

        if search:
            query = query.where(
                (TaskModel.name.contains(search))
                | (TaskModel.description.contains(search))
            )

        if status:
            query = query.where(TaskModel.status == status)

        if sort_by in [
            "name",
            "status",
            "created_at",
            "updated_at",
        ]:
            sort_column = getattr(TaskModel, sort_by)
            if sort_order == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())

        total_result = await db.execute(select(TaskModel).from_statement(query))
        total = len(total_result.scalars().all())

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await db.execute(query)
        tasks = result.scalars().all()

        return {"total": total, "items": tasks}

    @staticmethod
    async def update(
        db: AsyncSession, task_id: int, update_data: dict
    ) -> TaskModel | None:
        """更新任务"""
        result = await db.execute(select(TaskModel).where(TaskModel.id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            return None

        if update_data:
            await db.execute(
                update(TaskModel).where(TaskModel.id == task_id).values(**update_data)
            )
            await db.commit()
            await db.refresh(task)

        return task

    @staticmethod
    async def delete(db: AsyncSession, task_id: int) -> bool:
        """删除任务"""
        result = await db.execute(select(TaskModel).where(TaskModel.id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            return False

        await db.execute(delete(TaskModel).where(TaskModel.id == task_id))
        await db.commit()

        return True

    @staticmethod
    async def update_status(
        db: AsyncSession, task_id: int, status: TaskStatus
    ) -> TaskModel | None:
        """更新任务状态"""
        return await TaskDAO.update(db, task_id, {"status": status})
