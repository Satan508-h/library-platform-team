"""数据库初始化：创建集合（含固定集合）与全部索引。

用法：python app/init_db.py
"""
from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING

from db import get_db, ping

# 索引清单（与《数据模型设计》第 3.5 节一致）
INDEX_PLAN: dict[str, list[tuple[list[tuple[str, int]], str, bool]]] = {
    "books": [
        ([("isbn", ASCENDING)], "uk_isbn", True),
        ([("category", ASCENDING), ("price", ASCENDING)], "idx_category_price", False),
        ([("tags", ASCENDING)], "idx_tags", False),
        ([("rating", DESCENDING)], "idx_rating", False),
        ([("publish_date", ASCENDING)], "idx_publish_date", False),
        ([("title", ASCENDING)], "idx_title", False),
    ],
    "readers": [
        ([("card_no", ASCENDING)], "uk_card_no", True),
        ([("college", ASCENDING)], "idx_college", False),
        ([("level", ASCENDING)], "idx_level", False),
    ],
    "borrow_logs": [
        ([("reader_card", ASCENDING), ("borrow_date", DESCENDING)], "idx_reader_date", False),
        ([("book_isbn", ASCENDING), ("borrow_date", DESCENDING)], "idx_book_date", False),
        ([("borrow_date", DESCENDING)], "idx_borrow_date", False),
        ([("status", ASCENDING)], "idx_status", False),
    ],
    "category_stats": [
        ([("book_count", DESCENDING)], "idx_book_count", False),
        ([("category", ASCENDING)], "uk_stats_category", True),
    ],
}


def create_collections(db) -> None:
    existing = set(db.list_collection_names())
    # 固定集合：追加写、只读最近记录，容量与条数双上限
    if "audit_logs" not in existing:
        db.create_collection("audit_logs", capped=True, size=16 * 1024 * 1024, max=10000,
                             comment="平台关键操作日志（固定集合，超出后自动淘汰最早记录）")
    # 普通集合：业务数据，需更新与全量历史
    for name in ("books", "readers", "borrow_logs", "category_stats"):
        if name not in existing:
            db.create_collection(name)
    print("集合：", sorted(db.list_collection_names()))


def create_indexes(db) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    for coll_name, plan in INDEX_PLAN.items():
        coll = db[coll_name]
        for keys, name, unique in plan:
            kwargs: dict[str, Any] = {"name": name}
            if unique:
                kwargs["unique"] = True
            coll.create_index(keys, **kwargs)
            created.append({"collection": coll_name, "name": name,
                            "keys": dict(keys) or [(k, v) for k, v in keys], "unique": unique})
    # 全文索引单列（每集合只允许一个 text 索引）
    db.books.create_index([("title", "text"), ("author", "text")], name="idx_text_search",
                          default_language="none")
    created.append({"collection": "books", "name": "idx_text_search",
                    "keys": "title:text,author:text", "unique": False})
    return created


def show_indexes(db) -> None:
    for coll_name in INDEX_PLAN:
        print(f"\n[{coll_name}] 索引：")
        for idx in db[coll_name].list_indexes():
            print(f"  - {idx['name']:<20} {idx['key']}  unique={idx.get('unique', False)}")


def reset(db) -> None:
    """删除全部集合后重建（仅供初始化/重跑使用）。"""
    for name in db.list_collection_names():
        if name.startswith("system."):
            continue
        db.drop_collection(name)
    print("已清空全部业务集合")


def main(reset_first: bool = False) -> None:
    print("连接信息：", ping())
    db = get_db()
    if reset_first and "books" in db.list_collection_names():
        reset(db)
    create_collections(db)
    created = create_indexes(db)
    print(f"\n共建立 {len(created)} 个索引：")
    for c in created:
        print(f"  {c['collection']:<14}{c['name']:<20}{c['keys']}  unique={c['unique']}")
    show_indexes(db)


if __name__ == "__main__":
    import sys

    main(reset_first="--reset" in sys.argv)
