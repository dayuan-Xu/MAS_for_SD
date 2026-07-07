from sqlalchemy.ext.asyncio import AsyncSession

from ..dao.task_dao import TaskDAO
from ..dao.thread_dao import ThreadDAO
from ..models.task import TaskStatus
from ..schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskExecutionStatusResponse,
    ThreadStatusInfo,
    ThreadInfo,
)
from .agent_team_session_manager import session_manager


async def create_task(db: AsyncSession, task_data: TaskCreate) -> TaskResponse:
    """创建任务"""
    task = await TaskDAO.create(db, task_data.model_dump())
    return TaskResponse.model_validate(task)


async def get_task(db: AsyncSession, task_id: int) -> TaskResponse | None:
    """根据ID获取任务"""
    task = await TaskDAO.get_by_id(db, task_id)
    if task:
        return TaskResponse.model_validate(task)
    return None


async def get_task_by_name(db: AsyncSession, name: str) -> TaskResponse | None:
    """根据名称获取任务"""
    task = await TaskDAO.get_by_name(db, name)
    if task:
        return TaskResponse.model_validate(task)
    return None


async def list_tasks(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 10,
    search: str = "",
    status: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> dict:
    """分页查询任务列表"""
    result = await TaskDAO.list(
        db, page, page_size, search, status, sort_by, sort_order
    )
    return {
        "total": result["total"],
        "items": [TaskResponse.model_validate(task) for task in result["items"]],
    }


async def update_task(
    db: AsyncSession, task_id: int, task_data: TaskUpdate
) -> TaskResponse | None:
    """更新任务"""
    update_dict = {}
    if task_data.name is not None:
        update_dict["name"] = task_data.name
    if task_data.description is not None:
        update_dict["description"] = task_data.description
    if task_data.status is not None:
        update_dict["status"] = task_data.status

    task = await TaskDAO.update(db, task_id, update_dict)
    if task:
        return TaskResponse.model_validate(task)
    return None


async def delete_task(db: AsyncSession, task_id: int) -> dict:
    """删除任务和所有线程

    删除前会检查该任务下是否有智能体团队会话正在运行，如果正在运行则拒绝删除。
    如果会话存在但不处于运行状态，则先摧毁所有会话，再删除数据库中的任务和线程记录。

    Returns:
        {
            "success": bool,
            "message": str,
            "is_running": bool,  # 是否有会话正在运行
        }
    """
    task = await TaskDAO.get_by_id(db, task_id)
    if not task:
        return {"success": False, "message": "任务不存在", "is_running": False}

    threads = await ThreadDAO.get_by_task_id(db, task_id)
    thread_ids = [t.thread_id for t in threads if t.thread_id]

    for thread_id_str in thread_ids:
        is_running = await session_manager.is_session_running(thread_id_str)
        if is_running:
            return {
                "success": False,
                "message": "该任务下存在正在运行的会话，无法删除。请 等待智能体团队本轮运行完毕 或者 手动中止当前智能体团队运行。",
                "is_running": True,
            }

    for thread_id_str in thread_ids:
        await session_manager.destroy(thread_id_str)

    res = await TaskDAO.delete(db, task_id)
    res2 = await ThreadDAO.delete_by_task_id(db, task_id)

    if res and res2:
        return {"success": True, "message": "任务删除成功", "is_running": False}
    else:
        return {"success": False, "message": "任务删除失败", "is_running": False}


async def update_task_status(
    db: AsyncSession, task_id: int, status: str
) -> TaskResponse | None:
    """更新任务状态"""
    task_status = TaskStatus(status)
    task = await TaskDAO.update_status(db, task_id, task_status)
    if task:
        return TaskResponse.model_validate(task)
    return None


async def get_task_threads(db: AsyncSession, task_id: int) -> list[ThreadInfo]:
    """获取某个任务的所有线程列表"""
    threads = await ThreadDAO.get_by_task_id(db, task_id)
    return [
        ThreadInfo(
            id=t.id,
            thread_id=t.thread_id,
            context_box_name=t.context_box_name,
            context_box_id=t.context_box_id,
            created_at=t.created_at,
        )
        for t in threads
    ]


async def delete_task_thread(db: AsyncSession, thread_id: int) -> dict:
    """删除任务的某个线程

    Args:
        thread_id: ThreadModel.id（数据库主键，数字类型）

    Returns:
        {
            "success": bool,
            "message": str,
            "is_running": bool,  # 是否正在运行
        }
    """
    thread = await ThreadDAO.get_by_id(db, thread_id)
    if not thread:
        return {"success": False, "message": "线程不存在", "is_running": False}

    thread_id_str = thread.thread_id
    if thread_id_str:
        is_running = await session_manager.is_session_running(thread_id_str)
        if is_running:
            return {
                "success": False,
                "message": "该会话正在运行中，无法删除。请 等待智能体团队本轮运行完毕 或者 手动中止当前智能体团队运行。",
                "is_running": True,
            }

        await session_manager.destroy(thread_id_str)

    res = await ThreadDAO.delete(db, thread_id)
    if res:
        return {"success": True, "message": "线程删除成功", "is_running": False}
    else:
        return {"success": False, "message": "线程删除失败", "is_running": False}


async def get_task_execution_status(db: AsyncSession, task_id: int) -> dict:
    """获取任务的实时执行状态（基于 AgentTeamSession 内存状态判断）

    Returns:
        {
            "status": "idle" | "pending" | "running",
            "threads": [...],  # 该任务的所有线程
            "running_thread_ids": [...],  # 运行中的 ThreadModel.thread_id（LangGraph线程ID，字符串类型）
        }
    """
    threads = await ThreadDAO.get_by_task_id(db, task_id)
    thread_ids = [t.thread_id for t in threads if t.thread_id]

    session_status = await session_manager.get_task_session_status(thread_ids)

    if session_status["has_running_session"]:
        status = "running"
    elif session_status["has_alive_session"]:
        status = "pending"
    else:
        status = "idle"

    return TaskExecutionStatusResponse(
        status=status,
        threads=[
            ThreadStatusInfo(
                id=t.id,
                thread_id=t.thread_id,
                context_box_name=t.context_box_name,
                context_box_id=t.context_box_id,
                created_at=t.created_at,
                is_alive=session_status["session_details"]
                .get(t.thread_id, {})
                .get("is_alive", False),
                is_running=session_status["session_details"]
                .get(t.thread_id, {})
                .get("is_running", False),
                last_access_time=session_status["session_details"]
                .get(t.thread_id, {})
                .get("last_access_time"),
            )
            for t in threads
        ],
        running_thread_ids=session_status["running_thread_ids"],
    )
