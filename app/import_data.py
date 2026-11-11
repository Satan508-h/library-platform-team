"""数据导入模块：把 03-数据 下的三份 JSON 数组导入 MongoDB。

要点：
1. ISO 8601 字符串日期按 BSON Date 存储（不是字符串），便于索引与聚合；
2. 源文件只读，不做任何修改；
3. 导入后与源文件条目数核对（50 / 30 / 3000）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from config import get_config
from db import get_db

DATE_FIELDS = {
    "books": ["publish_date"],
    "readers": ["register_date"],
    "borrow_logs": ["borrow_date", "return_date"],
}


def _load(name: str) -> list[dict[str, Any]]:
    path = get_config().data_dir / name
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def _to_date(doc: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    """把指定字段的 ISO 字符串转换成 datetime；缺失字段跳过（借阅流水 return_date 可能不存在）。"""
    out = dict(doc)
    for field in fields:
        value = out.get(field)
        if isinstance(value, str) and value:
            try:
                out[field] = datetime.fromisoformat(value)
            except ValueError:
                pass
    return out


def import_collection(name: str, docs: list[dict[str, Any]], drop: bool = True) -> int:
    db = get_db()
    coll = db[name]
    if drop:
        coll.delete_many({})
    prepared = [_to_date(d, DATE_FIELDS.get(name, [])) for d in docs]
    if prepared:
        coll.insert_many(prepared, ordered=False)
    return coll.count_documents({})


def verify(expected: dict[str, int]) -> bool:
    db = get_db()
    ok = True
    print(f"\n{'集合':<14}{'源文件条目':>10}{'库中文档':>10}{'结果'}")
    for name, count in expected.items():
        actual = db[name].count_documents({})
        flag = "一致" if actual == count else "不一致"
        ok = ok and actual == count
        print(f"{name:<14}{count:>10}{actual:>10}{flag:>8}")
    return ok


def main() -> int:
    cfg = get_config()
    print(f"数据目录：{cfg.data_dir}")
    expected: dict[str, int] = {}
    for name in ("books", "readers", "borrow_logs"):
        docs = _load(f"{name}.txt")
        n = import_collection(name, docs)
        expected[name] = len(docs)
        print(f"导入 {name}：源 {len(docs)} 条，库中 {n} 条")

    ok = verify(expected)
    db = get_db()
    sample = db.books.find_one({}, {"_id": 0, "title": 1, "publish_date": 1})
    print(f"\n类型抽检：publish_date = {sample['publish_date']!r} -> {type(sample['publish_date']).__name__}")
    print("\n数据核对：" + ("通过" if ok else "失败"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
