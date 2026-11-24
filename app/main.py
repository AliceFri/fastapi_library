"""FastAPI 应用与图书馆接口。"""
from contextlib import asynccontextmanager
from typing import Optional

from typing_extensions import Annotated

from fastapi import Depends, FastAPI, Path, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.database import BookNotFoundError, BorrowStateError, LibraryDatabase
from app.models import Book, BookPage, ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    database = LibraryDatabase()
    app.state.database = database
    try:
        yield
    finally:
        database.close()


def get_database(request: Request) -> LibraryDatabase:
    return request.app.state.database


Database = Annotated[LibraryDatabase, Depends(get_database)]
Page = Annotated[int, Query(ge=1, description="页码，从 1 开始")]
PageSize = Annotated[int, Query(ge=1, le=100, description="每页数量，最大 100")]
BookId = Annotated[int, Path(gt=0, description="书籍 ID")]

app = FastAPI(
    title="图书馆管理系统",
    description="基于 SQLite 内存数据库，启动时初始化 100 本书，支持查询、详情、借阅和归还。",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(BookNotFoundError)
def book_not_found_handler(request: Request, exc: BookNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(BorrowStateError)
def borrow_state_handler(request: Request, exc: BorrowStateError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse(url="/docs")


@app.get("/books", response_model=BookPage, tags=["书籍"], summary="查询书籍")
def list_books(
    database: Database,
    q: Annotated[Optional[str], Query(max_length=200, description="书名作者或简介关键词")] = None,
    title: Annotated[Optional[str], Query(max_length=200, description="书名支持模糊查询")] = None,
    author: Annotated[Optional[str], Query(max_length=200, description="作者支持模糊查询")] = None,
    is_borrowed: Annotated[Optional[bool], Query(description="true 为已借出，false 为可借阅")] = None,
    page: Page = 1,
    page_size: PageSize = 20,
):
    return database.list_books(
        q=q, title=title, author=author, is_borrowed=is_borrowed,
        page=page, page_size=page_size,
    )


# 固定路径须在 /books/{book_id} 之前注册。
@app.get("/books/borrowed", response_model=BookPage, tags=["借阅"], summary="查看目前已借阅的书籍")
def list_borrowed_books(database: Database, page: Page = 1, page_size: PageSize = 20):
    return database.list_books(is_borrowed=True, page=page, page_size=page_size)


@app.get(
    "/books/{book_id}", response_model=Book, tags=["书籍"], summary="查阅指定书籍详细资料",
    responses={404: {"model": ErrorResponse, "description": "书籍不存在"}},
)
def get_book(book_id: BookId, database: Database):
    return database.get_book(book_id)


@app.post(
    "/books/{book_id}/borrow", response_model=Book, tags=["借阅"], summary="借阅书籍",
    responses={
        404: {"model": ErrorResponse, "description": "书籍不存在"},
        409: {"model": ErrorResponse, "description": "书籍已借出"},
    },
)
def borrow_book(book_id: BookId, database: Database):
    return database.set_borrowed(book_id, is_borrowed=True)


@app.post(
    "/books/{book_id}/return", response_model=Book, tags=["借阅"], summary="归还书籍",
    responses={
        404: {"model": ErrorResponse, "description": "书籍不存在"},
        409: {"model": ErrorResponse, "description": "书籍尚未借出"},
    },
)
def return_book(book_id: BookId, database: Database):
    return database.set_borrowed(book_id, is_borrowed=False)
