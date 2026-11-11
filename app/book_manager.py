"""图书管理模块：books 集合的增删改查、条件检索与分页排序。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from pymongo import ASCENDING, DESCENDING

import audit
from db import get_db

COLLECTION = "books"
CATEGORIES = ["计算机", "文学", "经济管理", "数学", "外语", "历史"]


# ------------------------------------------------------------------ 写操作
def add_book(doc: dict[str, Any], operator: str = "lib_rw") -> dict[str, Any]:
    """新增图书，缺省补全 stock/borrow_count/publish_date 等字段。"""
    db = get_db()
    book = dict(doc)
    book.setdefault("stock", 0)
    book.setdefault("borrow_count", 0)
    book.setdefault("tags", [])
    if isinstance(book.get("publish_date"), str):
        book["publish_date"] = datetime.fromisoformat(book["publish_date"])
    book.setdefault("location", {})
    result = db.books.insert_one(book)
    audit.log("create_book", book.get("isbn", ""), {"inserted_id": str(result.inserted_id),
                                                    "title": book.get("title")}, operator=operator)
    return book


def update_book(isbn: str, fields: dict[str, Any], operator: str = "lib_rw") -> int:
    db = get_db()
    before = db.books.find_one({"isbn": isbn}, {"_id": 0})
    res = db.books.update_one({"isbn": isbn}, {"$set": fields})
    audit.log("update_book", isbn, {"modified": res.modified_count, "before": _safe(before),
                                    "after": _safe(fields)}, operator=operator)
    return res.modified_count


def delete_book(isbn: str, operator: str = "lib_rw") -> int:
    db = get_db()
    removed = db.books.find_one_and_delete({"isbn": isbn})
    if removed:
        audit.log("delete_book", isbn, {"title": removed.get("title")}, operator=operator)
    return 1 if removed else 0


def _safe(doc: Any) -> Any:
    if isinstance(doc, dict):
        return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in doc.items()}
    return doc


# ------------------------------------------------------------------ 读操作
def find_by_isbn(isbn: str) -> dict[str, Any] | None:
    return get_db().books.find_one({"isbn": isbn}, {"_id": 0})


def search(category: str | None = None, price_min: float | None = None,
           price_max: float | None = None, page: int = 1, size: int = 10,
           sort_by: str = "rating", only_available: bool = False) -> dict[str, Any]:
    """按类别 + 价格区间筛选，支持分页与排序。"""
    cond: dict[str, Any] = {}
    if category:
        cond["category"] = category
    if price_min is not None or price_max is not None:
        cond["price"] = {}
        if price_min is not None:
            cond["price"]["$gte"] = float(price_min)
        if price_max is not None:
            cond["price"]["$lte"] = float(price_max)
        if not cond["price"]:
            cond.pop("price")
    if only_available:
        cond["stock"] = {"$gt": 0}

    db = get_db()
    total = db.books.count_documents(cond)
    direction = DESCENDING if sort_by in ("rating", "price", "borrow_count", "publish_date") else ASCENDING
    page = max(1, page)
    cur = (db.books.find(cond, {"_id": 0, "tags": 0})
           .sort(sort_by, direction)
           .skip((page - 1) * size)
           .limit(size))
    return {"total": total, "page": page, "size": size, "items": list(cur), "condition": _jsonable(cond)}


def by_tags(tags: Iterable[str], mode: str = "all") -> list[dict[str, Any]]:
    """标签多选匹配：all = 同时包含全部标签；any = 包含任一标签。"""
    tags = list(tags)
    cond = {"tags": {"$all": tags}} if mode == "all" else {"tags": {"$in": tags}}
    return list(get_db().books.find(cond, {"_id": 0, "title": 1, "tags": 1, "category": 1, "rating": 1}))


def by_title_fuzzy(keyword: str, limit: int = 20) -> list[dict[str, Any]]:
    """书名模糊检索（正则）。"""
    import re

    pattern = re.escape(keyword)
    return list(get_db().books.find({"title": {"$regex": pattern, "$options": "i"}},
                                   {"_id": 0, "title": 1, "author": 1, "category": 1, "rating": 1})
                .limit(limit))


def by_publish_year(start: int | None = None, end: int | None = None) -> list[dict[str, Any]]:
    """出版年份区间检索（日期类型直接比较，索引可命中）。"""
    cond: dict[str, Any] = {}
    if start is not None or end is not None:
        cond["publish_date"] = {}
        if start is not None:
            cond["publish_date"]["$gte"] = datetime(start, 1, 1, tzinfo=timezone.utc)
        if end is not None:
            cond["publish_date"]["$lt"] = datetime(end + 1, 1, 1, tzinfo=timezone.utc)
    return list(get_db().books.find(cond, {"_id": 0, "title": 1, "publish_date": 1, "category": 1}))


def missing_tags() -> list[dict[str, Any]]:
    """缺少 tags 字段的图书，用于数据质量核查。"""
    return list(get_db().books.find({"tags": {"$exists": False}},
                                    {"_id": 0, "title": 1, "isbn": 1, "category": 1}))


def top_rated(limit: int = 10) -> list[dict[str, Any]]:
    """按评分排序取前 N，仅返回书名、作者、评分。"""
    return list(get_db().books.find({}, {"_id": 0, "title": 1, "author": 1, "rating": 1})
                .sort("rating", DESCENDING).limit(limit))


def _jsonable(doc: Any) -> Any:
    if isinstance(doc, dict):
        return {k: _jsonable(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [_jsonable(v) for v in doc]
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc
