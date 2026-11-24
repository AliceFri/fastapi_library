# FastAPI 图书馆项目

使用 Python 3.7、FastAPI 和 Python 内置 SQLite 构建的图书馆接口项目，兼容当前 `venv` 中的 Python 3.7.2。
数据库使用 SQLite `:memory:`，启动时自动初始化 **100 本不同的书籍**，包含 ID、名称、作者、简介和是否借出信息，初始均为未借出。

## 安装和启动

本项目使用 `venv` 虚拟环境。在项目根目录执行以下 PowerShell 命令：

```powershell
.\venv\Scripts\python.exe --version
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

若是首次部署且尚未创建 `venv`，先使用 Python 3.7 的解释器执行 `python -m venv venv`。
依赖已固定为兼容 Python 3.7 的版本：FastAPI 0.103.2、Pydantic 2.5.3、Uvicorn 0.22.0；
测试使用 Pytest 7.4.4 和 HTTPX 0.24.1，HTTPX 版本也与 Starlette 的 TestClient 兼容。
代码使用 `typing.List`、`typing.Tuple`、`typing.Optional` 和 `typing_extensions.Annotated`，
避免 Python 3.7 无法解析的运行时类型注解。启动与关闭数据库通过异步生命周期函数管理。

打开 <http://127.0.0.1:8000/docs>，可在 Swagger 页面直接查询和操作书籍。
根路径 <http://127.0.0.1:8000/> 也会跳转至接口文档。

macOS / Linux 对应命令：

```bash
python3.7 -m venv venv
venv/bin/python -m pip install -r requirements.txt
venv/bin/python -m uvicorn app.main:app --reload
```

## 已实现功能

| 功能 | 方法 | 路径 |
| --- | --- | --- |
| 查询书籍，支持筛选和分页 | GET | `/books` |
| 查阅指定书籍详细资料 | GET | `/books/{book_id}` |
| 借阅书籍 | POST | `/books/{book_id}/borrow` |
| 归还书籍 | POST | `/books/{book_id}/return` |
| 查看目前已借阅的书籍，支持分页 | GET | `/books/borrowed` |

### 查询参数

`GET /books` 支持以下可选参数。多个筛选条件同时传入时取交集；返回结果按书籍 ID 升序排列。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `q` | string | 无 | 书名、作者或简介包含关键词即可匹配 |
| `title` | string | 无 | 按书名模糊匹配 |
| `author` | string | 无 | 按作者模糊匹配 |
| `is_borrowed` | boolean | 无 | `true` 已借出；`false` 可借阅；不传则查询全部 |
| `page` | integer | 1 | 页码，最小为 1 |
| `page_size` | integer | 20 | 每页数量，范围 1–100 |

文本筛选会去除首尾空白；空白文本不参与筛选，`%`、`_` 作为普通字符处理。
`GET /books/borrowed` 支持相同的 `page`、`page_size` 分页参数。

示例请求：

```text
GET /books?page=1&page_size=10
GET /books?q=三体
GET /books?author=鲁迅&is_borrowed=false
GET /books?title=红楼梦
```

查询响应示例：

```json
{
  "items": [
    {
      "id": 1,
      "title": "红楼梦",
      "author": "曹雪芹",
      "description": "以贾宝玉、林黛玉的情感与贾府兴衰展现封建家族的生活。",
      "is_borrowed": false
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

`total` 为筛选后、分页前的书籍总数；没有匹配结果或页码超过最后一页时，`items` 为空数组。
详情接口以及借阅、归还成功时，直接返回上述 `items` 中的单个书籍对象。

### 完整借阅与归还示例

启动服务后，在 PowerShell 中执行：

```powershell
# 查看第一本书的详细资料
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/books/1'

# 借阅，无需请求体；成功响应中的 is_borrowed 为 true
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/books/1/borrow'

# 查看目前已借阅的书籍
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/books/borrowed'

# 归还，无需请求体；成功响应中的 is_borrowed 为 false
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/books/1/return'
```

### 错误处理

| HTTP 状态码 | 含义 |
| --- | --- |
| 404 | 指定 ID 对应的书籍不存在 |
| 409 | 书籍已借出，无法重复借阅；或书籍未借出，无法归还 |
| 422 | 参数格式或范围不合法，例如 `page=0`、`page_size=101`、非正整数 ID |

业务错误示例：

```json
{"detail": "该书已借出，请归还后再借阅"}
```

## 测试

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -m pytest -q
```

测试覆盖初始化的 100 本书、中文搜索、组合筛选、分页、详情、借还流程、
已借阅列表、重复操作、无效参数、不存在的书籍、并发借阅以及重启后数据重置。
每个测试独立初始化内存数据库。

## 项目结构

```text
app/
  __init__.py
  main.py          # 应用生命周期、接口、参数校验和错误处理
  models.py        # 书籍、分页及错误响应模型
  database.py      # SQLite 内存数据库、查询与借还操作
  seed_data.py     # 100 本初始书籍
tests/
  test_api.py      # 接口与并发测试
requirements.txt
requirements-dev.txt
README.md
```

## 内存存储说明

- 停止或重启服务会清空借阅状态，并重新初始化 100 本书；修改代码触发 `--reload` 也会重置数据。
- 请使用单个 worker 运行。多个 worker 属于不同进程，各自拥有独立的内存数据库。
- 借还操作通过锁及数据库事务保护，同一进程内并发借阅同一本书只能有一次成功。
- 当前按书籍记录是否借出，每条记录视为一本可借出的实体书；已借阅列表展示所有已借出的书籍。
- 当前需求不包含用户账号、借阅人、归还期限或借阅历史。
