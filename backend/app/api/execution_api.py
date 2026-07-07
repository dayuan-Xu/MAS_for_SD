import logging

from agentbay import AsyncSession
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.app.core.database import get_db
from backend.app.schemas.task_execute import (
    StartTaskRequest,
    DestroySessionRequest,
    CancelSessionRequest,
)
from backend.app.services.execution_service import (
    start_task_execution as service_start_task_execution,
)
from backend.app.services.execution_service import (
    destroy_agent_team_session as service_destroy_agent_team_session,
)
from backend.app.services.execution_service import (
    cancel_agent_team_session as service_cancel_agent_team_session,
)
from backend.app.services.execution_service import (
    sse_event_generator as service_sse_event_generator,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent_team_sessions", tags=["agent team sessions"])


@router.post("/start/{task_id}")
async def start_task_execution(
    task_id: int, request: StartTaskRequest, db: AsyncSession = Depends(get_db)
):
    """启动智能体团队（或者说智能体Alice）完成一次执行（alice.ainvoke）"""
    return await service_start_task_execution(db, task_id, request)


@router.post("/start_sse/{task_id}")
async def stream_task_execution(
    task_id: int, request: StartTaskRequest, db: AsyncSession = Depends(get_db)
):
    """启动智能体团队完成一次执行（alice.astream），通过 SSE 实时推送消息到前端"""

    return StreamingResponse(
        service_sse_event_generator(db, task_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/cancel")
async def cancel_agent_team_session(
    request: CancelSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """请求中止正在运行的智能体团队执行

    设置中止标志后，智能体将在下次模型调用前检测到标志并抛出 TaskCancelledException，
    从而优雅地结束当前 ReAct 循环。

    Args:
        request: 中止请求，包含 thread_id
        db: 数据库异步会话

    Returns:
        dict: 操作结果，包含 success 和 msg 字段
    """
    return await service_cancel_agent_team_session(db, request)


@router.delete("")
async def destroy_agent_team_session(
    request: DestroySessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """销毁和某条thread相关的智能体团队会话（销毁沙盒）

    删除智能体团队在内存中的会话状态，释放相关资源。
    注意：前端发起该请求时，相应的智能体团队必须处于非运行状态！

    Args:
        request: 销毁会话请求，包含 thread_id
        db: 数据库异步会话

    Returns:
        dict: 操作结果，包含 success 和 msg 字段
    """
    return await service_destroy_agent_team_session(db, request)
