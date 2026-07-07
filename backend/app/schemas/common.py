from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = Field(..., description="操作是否成功")
    msg: str = Field(..., description="提示信息")
    data: Optional[T] = Field(default=None, description="业务数据")

    class Config:
        from_attributes = True


class ApiSuccessResponse(ApiResponse[T], Generic[T]):
    success: bool = True


class ApiErrorResponse(ApiResponse[T], Generic[T]):
    success: bool = False