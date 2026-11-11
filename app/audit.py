"""操作日志模块：写入 / 查询 audit_logs（固定集合）。

audit_logs 采用固定集合（capped），理由见《数据模型设计》：
追加写、不修改、不删除，只按插入顺序倒序读最近 N 条，天然适合 capped。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from db import get_db

COLLECTION = "audit_logs"


def log(action: str, target: str, detail: dict[str, Any] | None = None,
        operator: str = "lib_rw", result: str = "success") -> dict[str, Any]:
    """记录一次关键操作。

    action  : 操作类型，如 create_book / delete_reader / export_stats
    target  : 操作对象标识，如 ISBN、借阅证号、集合名
    detail  : 附加信息（变更前后值、影响行数等）
    """
    doc = {
        "ts": datetime.now(timezone.utc),
        "action": action,
        "target": target,
        "operator": operator,
        "result": result,
        "detail": detail or {},
        "client": "wiselib-python-app",
    }
    get_db().audit_logs.insert_one(doc)
    return doc


def recent(limit: int = 100) -> list[dict[str, Any]]:
    """按时间倒序取最近 N 条。

    capped 集合用 $natural 倒序即可，代价与 limit 成正比，无需全表排序。
    """
    limit = max(1, min(int(limit), 1000))
    cur = get_db().audit_logs.find({}, {"_id": 0}).sort([("$natural", -1)]).limit(limit)
    return list(cur)


def stats() -> dict[str, Any]:
    db = get_db()
    coll = db.audit_logs
    return {
        "capped": coll.options().get("capped", False),
        "size_limit_bytes": coll.options().get("size"),
        "max_limit": coll.options().get("max"),
        "count": coll.estimated_document_count(),
        "actions": list(coll.aggregate([{"$group": {"_id": "$action", "n": {"$sum": 1}}},
                                        {"$sort": {"n": -1}}])),
    }


def print_recent(limit: int = 20) -> None:
    rows = recent(limit)
    print(f"\n最近 {len(rows)} 条操作日志：")
    print(f"{'时间':<26}{'操作':<20}{'对象':<26}{'结果'}")
    for r in rows:
        ts = r["ts"].astimezone().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{ts:<26}{r['action']:<20}{str(r['target']):<26}{r['result']}")


if __name__ == "__main__":
    print_recent()
