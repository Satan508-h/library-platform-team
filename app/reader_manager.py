"""读者管理模块：readers 集合的增删改查与条件检索。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import audit
from db import get_db

COLLECTION = "readers"
LEVELS = ["普通", "高级", "教师"]


def add_reader(doc: dict[str, Any], operator: str = "lib_rw") -> dict[str, Any]:
    reader = dict(doc)
    reader.setdefault("register_date", datetime.now(timezone.utc))
    if isinstance(reader.get("register_date"), str):
        reader["register_date"] = datetime.fromisoformat(reader["register_date"])
    reader.setdefault("level", "普通")
    get_db().readers.insert_one(reader)
    audit.log("create_reader", reader.get("card_no", ""), {"name": reader.get("name")}, operator=operator)
    return reader


def update_reader(card_no: str, fields: dict[str, Any], operator: str = "lib_rw") -> int:
    res = get_db().readers.update_one({"card_no": card_no}, {"$set": fields})
    audit.log("update_reader", card_no, {"modified": res.modified_count, "fields": list(fields)},
              operator=operator)
    return res.modified_count


def delete_reader(card_no: str, operator: str = "lib_rw") -> int:
    removed = get_db().readers.find_one_and_delete({"card_no": card_no})
    if removed:
        audit.log("delete_reader", card_no, {"name": removed.get("name")}, operator=operator)
    return 1 if removed else 0


def find_by_card(card_no: str) -> dict[str, Any] | None:
    return get_db().readers.find_one({"card_no": card_no}, {"_id": 0})


def search(keyword: str | None = None, college: str | None = None, level: str | None = None,
           page: int = 1, size: int = 10) -> dict[str, Any]:
    cond: dict[str, Any] = {}
    if keyword:
        cond["$or"] = [{"name": {"$regex": keyword}}, {"card_no": {"$regex": keyword}},
                       {"phone": {"$regex": keyword}}]
    if college:
        cond["college"] = college
    if level:
        cond["level"] = level
    db = get_db()
    total = db.readers.count_documents(cond)
    cur = db.readers.find(cond, {"_id": 0}).sort("register_date", 1).skip((page - 1) * size).limit(size)
    return {"total": total, "page": page, "items": list(cur)}


def list_colleges() -> list[str]:
    return get_db().readers.distinct("college")


def summary() -> dict[str, Any]:
    db = get_db()
    return {
        "total": db.readers.estimated_document_count(),
        "by_level": list(db.readers.aggregate([{"$group": {"_id": "$level", "n": {"$sum": 1}}},
                                               {"$sort": {"n": -1}}])),
        "by_college": list(db.readers.aggregate([{"$group": {"_id": "$college", "n": {"$sum": 1}}},
                                                 {"$sort": {"n": -1}}])),
        "no_email": db.readers.count_documents({"$or": [{"email": None}, {"email": ""}]}),
        "no_fav": db.readers.count_documents({"fav_categories": {"$exists": False}}),
    }
