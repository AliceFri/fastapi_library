from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_seed_contains_100_complete_distinct_books(client):
    response = client.get("/books", params={"page_size": 100})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == len(data["items"]) == 100
    assert len({book["title"] for book in data["items"]}) == 100
    assert [book["id"] for book in data["items"]] == list(range(1, 101))
    for book in data["items"]:
        assert book["title"] and book["author"] and book["description"]
        assert book["is_borrowed"] is False


def test_pagination(client):
    first = client.get("/books", params={"page": 1, "page_size": 7}).json()
    second = client.get("/books", params={"page": 2, "page_size": 7}).json()
    assert first["total"] == second["total"] == 100
    assert [book["id"] for book in first["items"]] == list(range(1, 8))
    assert [book["id"] for book in second["items"]] == list(range(8, 15))
    assert second["page"] == 2 and second["page_size"] == 7
    assert client.get("/books", params={"page": 6}).json()["items"] == []


@pytest.mark.parametrize(
    ("params", "expected_ids"),
    [
        ({"q": " 红楼梦 "}, [1]),
        ({"q": "曹雪芹"}, [1]),
        ({"q": "贾宝玉"}, [1]),
        ({"title": "三体"}, [41, 42, 43]),
        ({"author": "鲁迅"}, [7, 8, 9]),
        ({"q": "回忆", "author": "鲁迅"}, [9]),
        ({"title": "红楼梦", "author": "鲁迅"}, []),
        ({"q": "不存在的书籍"}, []),
        ({"q": "%"}, []),
        ({"q": "_"}, []),
        ({"q": "' OR 1=1 --"}, []),
    ],
)
def test_search_and_combined_filters(client, params, expected_ids):
    response = client.get("/books", params=params)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == len(expected_ids)
    assert [book["id"] for book in data["items"]] == expected_ids


def test_detail(client):
    response = client.get("/books/1")
    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "title": "红楼梦",
        "author": "曹雪芹",
        "description": "以贾宝玉、林黛玉的情感与贾府兴衰展现封建家族的生活。",
        "is_borrowed": False,
    }


def test_borrow_return_and_borrowed_list(client):
    assert client.get("/books/borrowed").json()["total"] == 0
    response = client.post("/books/1/borrow")
    assert response.status_code == 200
    assert response.json()["is_borrowed"] is True
    assert client.get("/books/1").json()["is_borrowed"] is True
    borrowed = client.get("/books/borrowed").json()
    assert borrowed["total"] == 1
    assert [book["id"] for book in borrowed["items"]] == [1]
    assert client.get("/books", params={"is_borrowed": True}).json() == borrowed
    assert client.get("/books", params={"is_borrowed": False}).json()["total"] == 99
    assert client.get("/books", params={"title": "红楼梦", "is_borrowed": True}).json()["total"] == 1
    response = client.post("/books/1/return")
    assert response.status_code == 200
    assert response.json()["is_borrowed"] is False
    assert client.get("/books/1").json()["is_borrowed"] is False
    assert client.get("/books/borrowed").json()["total"] == 0
    assert client.get("/books", params={"is_borrowed": False}).json()["total"] == 100


def test_invalid_borrow_state(client):
    response = client.post("/books/1/return")
    assert response.status_code == 409
    assert response.json()["detail"] == "该书尚未借出，无法归还"
    assert client.post("/books/1/borrow").status_code == 200
    response = client.post("/books/1/borrow")
    assert response.status_code == 409
    assert response.json()["detail"] == "该书已借出，请归还后再借阅"
    assert client.get("/books/borrowed").json()["total"] == 1


@pytest.mark.parametrize(
    ("method", "url"),
    [("get", "/books/999"), ("post", "/books/999/borrow"), ("post", "/books/999/return")],
)
def test_missing_book(client, method, url):
    response = getattr(client, method)(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "书籍不存在"}


@pytest.mark.parametrize(
    "url",
    [
        "/books?page=0", "/books?page_size=0", "/books?page_size=101",
        "/books?is_borrowed=invalid", "/books/0", "/books/-1", "/books/abc",
        "/books/borrowed?page=0", "/books/borrowed?page_size=101",
    ],
)
def test_invalid_parameters(client, url):
    assert client.get(url).status_code == 422


def test_borrowed_list_pagination(client):
    for book_id in (1, 2, 3):
        assert client.post(f"/books/{book_id}/borrow").status_code == 200
    response = client.get("/books/borrowed", params={"page": 2, "page_size": 2})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert [book["id"] for book in data["items"]] == [3]


def test_concurrent_borrow_only_succeeds_once(client):
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: client.post("/books/1/borrow"), range(8)))
    statuses = [response.status_code for response in responses]
    assert statuses.count(200) == 1
    assert statuses.count(409) == 7
    assert client.get("/books/borrowed").json()["total"] == 1


def test_database_is_reset_on_restart():
    with TestClient(app) as first:
        assert first.post("/books/1/borrow").status_code == 200
    with TestClient(app) as second:
        assert second.get("/books").json()["total"] == 100
        assert second.get("/books/borrowed").json()["total"] == 0


def test_api_documentation(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert "/books/{book_id}/borrow" in schema.json()["paths"]
