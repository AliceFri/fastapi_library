"""接口请求及响应模型。"""
from typing import List

from pydantic import BaseModel, Field


class Book(BaseModel):
    id: int = Field(description="书籍 ID", examples=[1])
    title: str = Field(description="书籍名称", examples=["红楼梦"])
    author: str = Field(description="作者", examples=["曹雪芹"])
    description: str = Field(description="书籍简介")
    is_borrowed: bool = Field(description="是否已借出")


class BookPage(BaseModel):
    items: List[Book]
    total: int = Field(description="符合筛选条件的书籍总数")
    page: int = Field(description="当前页码，从 1 开始")
    page_size: int = Field(description="每页数量")


class ErrorResponse(BaseModel):
    detail: str
