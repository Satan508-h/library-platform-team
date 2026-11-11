"""借阅管理模块：borrow_logs 借书 / 还书与流水查询。

borrow_logs 为普通集合（非固定集合）：归还时需要 $set return_date/status/duration_days，
文档体积会变化，capped 集合不允许增长型更新；且需要保留 2023—2025 全部历史做趋势统计。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import audit
from db import get_db

COLLECTION = "borrow_logs"


def borrow(card_no: str, isbn: str, days: int = 30, operator: str = "lib_rw") -> dict[str, Any]:
    """借书：校验读者与库存，写入流水并扣减库存。"""
    db = get_db()
    reader = db.readers.find_one({"card_no": card_no})
    if not reader:
        raise ValueError(f"借阅证号不存在：{card_no}")
    book = db.books.find_one({"isbn": isbn})
    if not book:
        raise ValueError(f"ISBN 不存在：{isbn}")
    if book.get("stock", 0) <= 0:
        raise ValueError(f"图书无在架库存：{book.get('title')}")

    now = datetime.now(timezone.utc)
    log = {
        "borrow_date": now,
        "reader_card": card_no,
        "book_isbn": isbn,
        "status": "借出",
        "duration_days": days,
    }
    db.borrow_logs.insert_one(log)
    db.books.update_one({"isbn": isbn}, {"$inc": {"stock": -1, "borrow_count": 1}})
    audit.log("borrow_book", f"{card_no}/{isbn}", {"days": days, "title": book.get("title")},
              operator=operator)
    return log


def give_back(card_no: str, isbn: str, operator: str = "lib_rw") -> dict[str, Any]:
    """还书：找到该读者该图书最近一条未归还流水，回填归还信息并恢复库存。"""
    db = get_db()
    log = db.borrow_logs.find_one({"reader_card": card_no, "book_isbn": isbn, "status": {"$ne": "已归还"}},
                                  sort=[("borrow_date", -1)])
    if not log:
        raise ValueError("未找到未归还的借阅记录")
    now = datetime.now(timezone.utc)
    duration = (now - log["borrow_date"]).days
    status = "逾期" if duration > log.get("duration_days", 30) else "已归还"
    db.borrow_logs.update_one({"_id": log["_id"]},
                              {"$set": {"return_date": now, "status": status, "duration_days": duration}})
    db.books.update_one({"isbn": isbn}, {"$inc": {"stock": 1}})
    audit.log("return_book", f"{card_no}/{isbn}", {"duration_days": duration, "status": status},
              operator=operator)
    return {"duration_days": duration, "status": status}


def list_logs(card_no: str | None = None, isbn: str | None = None, status: str | None = None,
              start: str | None = None, end: str | None = None, page: int = 1, size: int = 20) -> dict[str, Any]:
    cond: dict[str, Any] = {}
    if card_no:
        cond["reader_card"] = card_no
    if isbn:
        cond["book_isbn"] = isbn
    if status:
        cond["status"] = status
    if start or end:
        cond["borrow_date"] = {}
        if start:
            cond["borrow_date"]["$gte"] = datetime.fromisoformat(start)
        if end:
            cond["borrow_date"]["$lte"] = datetime.fromisoformat(end)

    db = get_db()
    total = db.borrow_logs.count_documents(cond)
    cur = (db.borrow_logs.find(cond, {"_id": 0})
           .sort("borrow_date", -1)
           .skip((page - 1) * size)
           .limit(size))
    return {"total": total, "page": page, "items": list(cur)}


def overdue(days: int = 30) -> list[dict[str, Any]]:
    """逾期未还：借出超过 N 天且无归还时间。"""
    deadline = datetime.now(timezone.utc) - timedelta(days=days)
    return list(get_db().borrow_logs.find(
        {"return_date": {"$exists": False}, "borrow_date": {"$lt": deadline}},
        {"_id": 0}).sort("borrow_date", 1).limit(50))


def active_borrows(card_no: str) -> list[dict[str, Any]]:
    return list(get_db().borrow_logs.find(
        {"reader_card": card_no, "return_date": {"$exists": False}}, {"_id": 0}).sort("borrow_date", -1))
