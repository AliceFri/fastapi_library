"""SQLite 内存数据库及书籍查询、借还操作。"""
import sqlite3
from threading import Lock
from typing import List, Optional, Union

from app.models import Book, BookPage
from app.seed_data import BOOKS


class BookNotFoundError(Exception):
    """书籍不存在。"""


class BorrowStateError(Exception):
    """当前借阅状态不允许执行该操作。"""


class LibraryDatabase:
    def __init__(self) -> None:
        # FastAPI 同步路由在线程池执行，因此允许跨线程访问，并用锁保护连接。
        self._lock = Lock()
        self._connection = sqlite3.connect(":memory:", check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE books (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    description TEXT NOT NULL,
                    is_borrowed INTEGER NOT NULL DEFAULT 0
                        CHECK (is_borrowed IN (0, 1))
                )
                """
            )
            self._connection.executemany(
                "INSERT INTO books (title, author, description) VALUES (?, ?, ?)",
                BOOKS,
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @staticmethod
    def _like_pattern(value: str) -> str:
        # 将用户输入中的 LIKE 通配符视为普通文本。
        escaped = value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    def list_books(
        self,
        *,
        q: Optional[str] = None,
        title: Optional[str] = None,
        author: Optional[str] = None,
        is_borrowed: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> BookPage:
        conditions: List[str] = []
        parameters: List[Union[str, int]] = []
        if q and q.strip():
            conditions.append(
                "(title LIKE ? ESCAPE '\\' OR author LIKE ? ESCAPE '\\' "
                "OR description LIKE ? ESCAPE '\\')"
            )
            parameters.extend([self._like_pattern(q)] * 3)
        for column, value in (("title", title), ("author", author)):
            if value and value.strip():
                conditions.append(f"{column} LIKE ? ESCAPE '\\'")
                parameters.append(self._like_pattern(value))
        if is_borrowed is not None:
            conditions.append("is_borrowed = ?")
            parameters.append(int(is_borrowed))
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with self._lock:
            total = self._connection.execute(
                "SELECT COUNT(*) FROM books" + where, parameters
            ).fetchone()[0]
            rows = self._connection.execute(
                "SELECT * FROM books" + where + " ORDER BY id LIMIT ? OFFSET ?",
                [*parameters, page_size, (page - 1) * page_size],
            ).fetchall()
        return BookPage(
            items=[Book(**dict(row)) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_book(self, book_id: int) -> Book:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM books WHERE id = ?", (book_id,)
            ).fetchone()
        if row is None:
            raise BookNotFoundError("书籍不存在")
        return Book(**dict(row))

    def set_borrowed(self, book_id: int, *, is_borrowed: bool) -> Book:
        # 状态检查与更新处于同一个锁和事务中，避免并发重复借阅。
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT * FROM books WHERE id = ?", (book_id,)
            ).fetchone()
            if row is None:
                raise BookNotFoundError("书籍不存在")
            if bool(row["is_borrowed"]) == is_borrowed:
                message = "该书已借出，请归还后再借阅" if is_borrowed else "该书尚未借出，无法归还"
                raise BorrowStateError(message)
            self._connection.execute(
                "UPDATE books SET is_borrowed = ? WHERE id = ?",
                (int(is_borrowed), book_id),
            )
            book = dict(row)
            book["is_borrowed"] = is_borrowed
        return Book(**book)
