from pydantic import BaseModel, Field
from typing import Literal, Optional, Union, Dict, Any
from langchain_core.messages import BaseMessage


class StartTaskRequest(BaseModel):
    user_input: str = ""
    thread_id: str = (
        ""  # ThreadModel.thread_id（LangGraph线程ID，字符串类型），用于棕地开发恢复会话；为空时创建新会话
    )


class DestroySessionRequest(BaseModel):
    """销毁智能体团队会话请求模型"""

    thread_id: str = Field(
        ...,
        description="ThreadModel.thread_id（LangGraph线程ID，字符串类型），要销毁的会话ID",
    )


class CancelSessionRequest(BaseModel):
    """中止智能体团队执行请求模型"""

    thread_id: str = Field(
        ...,
        description="ThreadModel.thread_id（LangGraph线程ID，字符串类型），要中止执行的会话ID",
    )


class SSEAgentMessage(BaseModel):
    type: Literal["agent_message"] = Field("agent_message")
    thread_id: str
    agent_name: str  # message（LangChain HumanMessage、AIMessage、ToolMessage的model dump）的归属者
    message: Dict[str, Any]


class SSESystemMessage(BaseModel):
    type: Literal["system_message"] = Field("system_message")
    thread_id: Optional[str] = None
    message: str


class SSEErrorMessage(BaseModel):
    type: Literal["error_message"] = Field("error_message")
    thread_id: Optional[str] = None
    message: str


SSEMessage = Union[SSEAgentMessage, SSESystemMessage, SSEErrorMessage]


class ExecutionResult(BaseModel):
    success: bool
    msg: str
