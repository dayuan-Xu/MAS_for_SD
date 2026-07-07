from pydantic import BaseModel, Field
from datetime import datetime
from enum import StrEnum


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="任务名称")
    description: str = Field(default="", description="任务描述")


class TaskUpdate(BaseModel):
    name: str | None = Field(
        default=None, min_length=1, max_length=255, description="任务名称"
    )
    description: str | None = Field(default=None, description="任务描述")
    status: TaskStatus | None = Field(default=None, description="任务状态")


class TaskResponse(BaseModel):
    id: int
    name: str
    description: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    total: int
    items: list[TaskResponse]


class ThreadInfo(BaseModel):
    id: int
    thread_id: str | None
    context_box_name: str | None
    context_box_id: str | None
    created_at: str


class TaskThreadListResponse(BaseModel):
    threads: list[ThreadInfo]


class ThreadStatusInfo(BaseModel):
    id: int
    thread_id: str | None
    context_box_name: str | None
    context_box_id: str | None
    created_at: str
    is_alive: bool
    is_running: bool
    last_access_time: str | None


class TaskExecutionStatusResponse(BaseModel):
    status: str
    threads: list[ThreadStatusInfo]
    running_thread_ids: list[str]


class TaskStatusBatchResponse(BaseModel):
    statuses: dict[int, TaskExecutionStatusResponse]


class OperationResult(BaseModel):
    success: bool
    message: str


class DeleteThreadResult(BaseModel):
    success: bool
    message: str
    is_running: bool
