"""统计分析模块：分类统计、学院排行榜、年月趋势、借阅排行、多集合联合分析。"""
from __future__ import annotations

from typing import Any

from db import get_db

STATS_COLLECTION = "category_stats"


def by_category(limit: int = 0) -> list[dict[str, Any]]:
    """按类别统计藏书量、平均价格、平均评分。"""
    pipeline = [
        {"$group": {
            "_id": "$category",
            "book_count": {"$sum": 1},
            "avg_price": {"$avg": "$price"},
            "avg_rating": {"$avg": "$rating"},
            "total_stock": {"$sum": "$stock"},
            "max_price": {"$max": "$price"},
        }},
        {"$project": {
            "_id": 0,
            "category": "$_id",
            "book_count": 1,
            "avg_price": {"$round": ["$avg_price", 2]},
            "avg_rating": {"$round": ["$avg_rating", 2]},
            "total_stock": 1,
            "max_price": 1,
        }},
        {"$sort": {"book_count": -1, "category": 1}},
    ]
    if limit:
        pipeline.append({"$limit": limit})
    return list(get_db().books.aggregate(pipeline))


def college_rank(top: int = 5) -> list[dict[str, Any]]:
    """各学院借阅总量前 N：borrow_logs $lookup readers 实现多集合联合。"""
    pipeline = [
        {"$lookup": {
            "from": "readers",
            "localField": "reader_card",
            "foreignField": "card_no",
            "as": "reader",
        }},
        {"$unwind": {"path": "$reader", "preserveNullAndEmptyArrays": True}},
        {"$group": {
            "_id": {"college": {"$ifNull": ["$reader.college", "未知学院"]},
                    "level": {"$ifNull": ["$reader.level", "未知"]}},
            "borrow_total": {"$sum": 1},
        }},
        {"$group": {
            "_id": "$_id.college",
            "borrow_total": {"$sum": "$borrow_total"},
            "detail": {"$push": {"level": "$_id.level", "n": "$borrow_total"}},
        }},
        {"$project": {"_id": 0, "college": "$_id", "borrow_total": 1, "detail": 1}},
        {"$sort": {"borrow_total": -1}},
        {"$limit": top},
    ]
    return list(get_db().borrow_logs.aggregate(pipeline))


def monthly_trend(year: int | None = None) -> list[dict[str, Any]]:
    """按年月统计借阅趋势，输出可读的年份/月份标签。"""
    match = {}
    if year:
        from datetime import datetime, timezone

        match = {"borrow_date": {"$gte": datetime(year, 1, 1, tzinfo=timezone.utc),
                                 "$lt": datetime(year + 1, 1, 1, tzinfo=timezone.utc)}}
    pipeline = [
        {"$match": match} if match else {"$match": {}},
        {"$group": {
            "_id": {"y": {"$year": "$borrow_date"}, "m": {"$month": "$borrow_date"}},
            "borrow_count": {"$sum": 1},
            "unique_readers": {"$addToSet": "$reader_card"},
        }},
        {"$project": {
            "_id": 0,
            "year": "$_id.y",
            "month": "$_id.m",
            "label": {"$concat": [{"$toString": "$_id.y"}, "年", {"$toString": "$_id.m"}, "月"]},
            "borrow_count": 1,
            "unique_readers": {"$size": "$unique_readers"},
        }},
        {"$sort": {"year": 1, "month": 1}},
    ]
    return list(get_db().borrow_logs.aggregate(pipeline))


def top_borrowed_books(top: int = 10) -> list[dict[str, Any]]:
    """借阅次数最多的 N 本图书，并带出馆藏位置（location 嵌套文档直接投影）。"""
    pipeline = [
        {"$sort": {"borrow_count": -1}},
        {"$limit": top},
        {"$project": {
            "_id": 0,
            "isbn": 1, "title": 1, "author": 1, "category": 1,
            "borrow_count": 1, "stock": 1,
            "location": 1,
            # 位置字段拍平为便于阅读的列
            "floor": "$location.floor",
            "shelf": "$location.shelf",
            "copies": "$location.copies",
        }},
    ]
    return list(get_db().books.aggregate(pipeline))


def top_borrowed_from_logs(top: int = 10) -> list[dict[str, Any]]:
    """以流水实数统计借阅排行，与 books.borrow_count 交叉校验。"""
    pipeline = [
        {"$group": {"_id": "$book_isbn", "log_count": {"$sum": 1}}},
        {"$sort": {"log_count": -1, "_id": 1}},
        {"$limit": top},
        {"$lookup": {"from": "books", "localField": "_id", "foreignField": "isbn", "as": "book"}},
        {"$unwind": "$book"},
        {"$project": {"_id": 0, "isbn": "$_id", "title": "$book.title", "log_count": 1,
                      "borrow_count_field": "$book.borrow_count",
                      "floor": "$book.location.floor", "shelf": "$book.location.shelf"}},
    ]
    return list(get_db().borrow_logs.aggregate(pipeline))


def save_category_stats(operator: str = "lib_rw") -> int:
    """把分类统计结果写入 category_stats 集合，供后续查询与导出。"""
    db = get_db()
    rows = by_category()
    db[STATS_COLLECTION].delete_many({})
    if rows:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        for r in rows:
            r["generated_at"] = now
            r["source"] = "books.aggregate(by_category)"
        db[STATS_COLLECTION].insert_many(rows)
        db[STATS_COLLECTION].create_index([("book_count", -1)], name="idx_book_count")
    import audit

    audit.log("save_category_stats", STATS_COLLECTION, {"rows": len(rows)}, operator=operator)
    return len(rows)


def read_category_stats() -> list[dict[str, Any]]:
    return list(get_db()[STATS_COLLECTION].find({}, {"_id": 0}).sort("book_count", -1))


def overview() -> dict[str, Any]:
    """平台总览：四个集合的文档量与关键指标。"""
    db = get_db()
    return {
        "books": db.books.estimated_document_count(),
        "readers": db.readers.estimated_document_count(),
        "borrow_logs": db.borrow_logs.estimated_document_count(),
        "audit_logs": db.audit_logs.estimated_document_count(),
        "category_stats": db[STATS_COLLECTION].estimated_document_count(),
        "gridfs_files": db["fs.files"].estimated_document_count(),
        "total_inventory": sum(b.get("stock", 0) for b in db.books.find({}, {"stock": 1})),
        "categories": len(db.books.distinct("category")),
    }
