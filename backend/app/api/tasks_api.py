from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskListResponse,
    TaskThreadListResponse,
    TaskExecutionStatusResponse,
    TaskStatusBatchResponse,
    DeleteThreadResult,
)
from backend.app.schemas.common import ApiResponse, ApiSuccessResponse, ApiErrorResponse
from backend.app.services.task_service import (
    create_task as service_create_task,
    get_task as service_get_task,
    list_tasks as service_list_tasks,
    update_task as service_update_task,
    delete_task as service_delete_task,
    get_task_threads as service_get_task_threads,
    delete_task_thread as service_delete_task_thread,
    get_task_execution_status as service_get_task_execution_status,
)
from backend.app.core.database import get_db

router = APIRouter(prefix="/tasks", tags=["软件开发任务管理"])


@router.post("", response_model=ApiResponse[TaskResponse], status_code=201)
async def create_new_task(task_data: TaskCreate, db: AsyncSession = Depends(get_db)):
    """创建新任务

    Args:
        task_data: 任务创建请求体，包含任务名称和描述
        db: 数据库异步会话

    Returns:
        ApiResponse[TaskResponse]: 创建结果，包含成功标志、提示信息和任务数据

    Raises:
        HTTPException: 当参数验证失败时，返回400状态码
    """
    try:
        task = await service_create_task(db, task_data)
        return ApiSuccessResponse(data=task, msg="任务创建成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=ApiResponse[TaskListResponse])
async def get_tasks_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量，范围1-100"),
    search: str = Query("", description="搜索关键词，按任务名称搜索"),
    status: str = Query("", description="任务状态筛选"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向，asc升序/desc降序"),
    db: AsyncSession = Depends(get_db),
):
    """分页获取任务列表

    Args:
        page: 页码，从1开始
        page_size: 每页数量，范围1-100
        search: 搜索关键词，按任务名称搜索
        status: 任务状态筛选
        sort_by: 排序字段
        sort_order: 排序方向，asc升序/desc降序
        db: 数据库异步会话

    Returns:
        ApiResponse[TaskListResponse]: 任务列表，包含总数和任务项列表
    """
    result = await service_list_tasks(
        db,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiSuccessResponse(data=TaskListResponse(**result), msg="获取任务列表成功")


@router.get("/status/batch", response_model=ApiResponse[TaskStatusBatchResponse])
async def get_tasks_status_batch(task_ids: str, db: AsyncSession = Depends(get_db)):
    """批量获取多个任务的执行状态

    Args:
        task_ids: 逗号分隔的 task_id 列表，如 "1,2,3"
        db: 数据库异步会话

    Returns:
        ApiResponse[TaskStatusBatchResponse]: 任务状态字典，key为task_id，value为任务执行状态信息
    """
    ids = [int(x) for x in task_ids.split(",") if x.strip()]
    result: dict[int, TaskExecutionStatusResponse] = {}
    for task_id in ids:
        result[task_id] = await service_get_task_execution_status(db, task_id)
    return ApiSuccessResponse(
        data=TaskStatusBatchResponse(statuses=result), msg="获取任务状态成功"
    )


@router.get("/threads/{task_id}", response_model=ApiResponse[TaskThreadListResponse])
async def get_task_threads(task_id: int, db: AsyncSession = Depends(get_db)):
    """获取某个任务的所有线程列表

    供前端用于判断任务的启动/参与模式

    Args:
        task_id: 任务ID
        db: 数据库异步会话

    Returns:
        ApiResponse[TaskThreadListResponse]: 线程列表
    """
    threads = await service_get_task_threads(db, task_id)
    return ApiSuccessResponse(
        data=TaskThreadListResponse(threads=threads), msg="获取线程列表成功"
    )


@router.delete("/threads/{thread_id}", response_model=ApiResponse[DeleteThreadResult])
async def delete_task_thread(thread_id: int, db: AsyncSession = Depends(get_db)):
    """删除任务的某个线程

    删除前会检查该线程是否有智能体团队会话正在运行，如果正在运行则拒绝删除。
    如果会话存在但不处于运行状态，则先摧毁该会话，再删除数据库中的线程记录。

    Args:
        thread_id: 线程ID（数据库中的记录ID）
        db: 数据库异步会话

    Returns:
        ApiResponse[DeleteThreadResult]: 删除操作结果

    Raises:
        HTTPException: 当线程正在运行时返回400状态码；当线程不存在时返回404状态码
    """
    result = await service_delete_task_thread(db, thread_id)
    if not result["success"]:
        if result["is_running"]:
            raise HTTPException(status_code=400, detail=result["message"])
        else:
            raise HTTPException(status_code=404, detail=result["message"])
    return ApiSuccessResponse(
        data=DeleteThreadResult(
            success=True, message=result["message"], is_running=False
        ),
        msg=result["message"],
    )


@router.get("/{task_id}", response_model=ApiResponse[TaskResponse])
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """根据ID获取任务详情

    Args:
        task_id: 任务ID
        db: 数据库异步会话

    Returns:
        ApiResponse[TaskResponse]: 任务详情信息

    Raises:
        HTTPException: 当任务不存在时返回404状态码
    """
    task = await service_get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiSuccessResponse(data=task, msg="获取任务详情成功")


@router.get(
    "/{task_id}/status", response_model=ApiResponse[TaskExecutionStatusResponse]
)
async def get_task_status(task_id: int, db: AsyncSession = Depends(get_db)):
    """获取任务的实时执行状态

    基于 AgentTeamSession 内存状态判断任务当前的执行状态（idle/pending/running）

    Args:
        task_id: 任务ID
        db: 数据库异步会话

    Returns:
        ApiResponse[TaskExecutionStatusResponse]: 任务执行状态信息，包含状态、线程列表和运行中的线程ID
    """
    status = await service_get_task_execution_status(db, task_id)
    return ApiSuccessResponse(data=status, msg="获取任务状态成功")


@router.put("/{task_id}", response_model=ApiResponse[TaskResponse])
async def update_task(
    task_id: int, task_data: TaskUpdate, db: AsyncSession = Depends(get_db)
):
    """更新任务信息

    Args:
        task_id: 任务ID
        task_data: 任务更新请求体，包含任务名称、描述和状态
        db: 数据库异步会话

    Returns:
        ApiResponse[TaskResponse]: 更新后的任务信息

    Raises:
        HTTPException: 当任务不存在时返回404状态码
    """
    task = await service_update_task(db, task_id, task_data)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiSuccessResponse(data=task, msg="任务更新成功")


@router.delete("/{task_id}", response_model=ApiResponse[dict])
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """删除任务及其所有关联线程

    删除前会检查该任务下是否有智能体团队会话正在运行，如果正在运行则拒绝删除。
    如果会话存在但不处于运行状态，则先摧毁所有会话，再删除数据库中的任务和线程记录。

    Args:
        task_id: 任务ID
        db: 数据库异步会话

    Returns:
        ApiResponse[dict]: 删除操作结果

    Raises:
        HTTPException: 当任务下存在正在运行的会话时返回400状态码；当任务不存在时返回404状态码
    """
    result = await service_delete_task(db, task_id)
    if not result["success"]:
        if result["is_running"]:
            raise HTTPException(status_code=400, detail=result["message"])
        else:
            raise HTTPException(status_code=404, detail=result["message"])
    return ApiSuccessResponse(data={}, msg=result["message"])
