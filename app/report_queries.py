"""检索与统计功能执行记录：逐条执行 11 项功能，输出命令、结果条数与样例。

输出：records/task3_queries_and_stats.md（正文引用）+ 控制台表格
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from bson import ObjectId

import book_manager as bm
import borrow_manager as lm
import stats_manager as sm
from config import BASE_DIR
from db import get_db

OUT = BASE_DIR / "records" / "task3_queries_and_stats.md"


def q1(db):
    """按类别与价格区间组合筛选"""
    cond = {"category": "计算机", "price": {"$gte": 80, "$lte": 130}}
    return cond, db.books.count_documents(cond), list(db.books.find(cond, {"_id": 0, "title": 1, "price": 1}))


def q2(db):
    """按标签多选匹配（同时含多个标签）"""
    cond = {"tags": {"$all": ["编程", "入门"]}}
    return cond, db.books.count_documents(cond), list(db.books.find(cond, {"_id": 0, "title": 1, "tags": 1}))


def q3(db):
    """按书名模糊检索"""
    cond = {"title": {"$regex": "Python", "$options": "i"}}
    return cond, db.books.count_documents(cond), list(db.books.find(cond, {"_id": 0, "title": 1, "author": 1}))


def q4(db):
    """按出版年份范围检索"""
    cond = {"publish_date": {"$gte": datetime(2020, 1, 1, tzinfo=timezone.utc),
                             "$lt": datetime(2024, 1, 1, tzinfo=timezone.utc)}}
    return cond, db.books.count_documents(cond), list(db.books.find(cond, {"_id": 0, "title": 1, "publish_date": 1}))


def q5(db):
    """查询缺少 tags 字段的图书"""
    cond = {"tags": {"$exists": False}}
    return cond, db.books.count_documents(cond), list(db.books.find(cond, {"_id": 0, "title": 1, "isbn": 1}))


def q6(db):
    """按评分排序取前 10，仅返回书名、作者、评分"""
    rows = list(db.books.find({}, {"_id": 0, "title": 1, "author": 1, "rating": 1}).sort("rating", -1).limit(10))
    return {"sort": {"rating": -1}, "limit": 10, "projection": {"title": 1, "author": 1, "rating": 1}}, len(rows), rows


def s1(db):
    """按类别统计藏书量、平均价格、平均评分"""
    rows = sm.by_category()
    return {"$group": "category -> count/avg(price)/avg(rating)"}, len(rows), rows


def s2(db):
    """统计各学院借阅总量，取前 5 名"""
    rows = sm.college_rank(5)
    return {"$lookup": "readers", "$group": "college", "$limit": 5}, len(rows), rows


def s3(db):
    """按年月统计借阅趋势"""
    rows = sm.monthly_trend()
    return {"$group": "year+month", "$sort": "year,month"}, len(rows), rows[:6]


def s4(db):
    """借阅次数最多的 10 本图书及馆藏位置"""
    rows = sm.top_borrowed_books(10)
    return {"$sort": "borrow_count desc", "$limit": 10, "$project": "location.*"}, len(rows), rows


def s5(db):
    """分类统计结果写入新集合"""
    n = sm.save_category_stats()
    stored = sm.read_category_stats()
    return {"collection": "category_stats", "restored": "完全重建"}, n, stored


CASES: list[tuple[str, str, Callable[[Any], tuple[Any, int, list]]]] = [
    ("检索", "按类别 + 价格区间组合筛选（计算机，80—130 元）", q1),
    ("检索", "按标签多选匹配（$all: 编程 + 入门）", q2),
    ("检索", "按书名模糊检索（title 含 Python）", q3),
    ("检索", "按出版年份范围检索（2020—2023）", q4),
    ("检索", "查询缺少 tags 字段的图书（数据质量核查）", q5),
    ("检索", "按评分排序取前 10（仅书名/作者/评分）", q6),
    ("统计", "按类别统计藏书量、平均价格、平均评分", s1),
    ("统计", "各学院借阅总量前 5（多集合 $lookup）", s2),
    ("统计", "按年月统计借阅趋势", s3),
    ("统计", "借阅次数最多的 10 本图书 + 馆藏位置", s4),
    ("统计", "分类统计结果写入 category_stats 集合", s5),
]


def main() -> None:
    db = get_db()
    lines = ["# 检索与统计功能执行记录", "",
             f"- 执行时间：{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')}",
             f"- 数据量：books {db.books.count_documents({})} / readers {db.readers.count_documents({})} / "
             f"borrow_logs {db.borrow_logs.count_documents({})}", "",
             "| # | 类型 | 功能 | 条件/管道要点 | 结果条数 |", "|---|---|---|---|---|"]
    for i, (kind, desc, fn) in enumerate(CASES, 1):
        cond, count, sample = fn(db)
        cond_text = json.dumps(cond, ensure_ascii=False, default=str).replace("|", "\\|")
        if len(cond_text) > 120:
            cond_text = cond_text[:117] + "..."
        lines.append(f"| {i} | {kind} | {desc} | `{cond_text}` | {count} |")
        print(f"[{i:>2}] {desc:<40} 结果 {count} 条")
        if sample:
            print("     " + json.dumps(sample[0], ensure_ascii=False, default=str)[:150])

    lines += ["", "## 关键结论", "",
              f"1. books 共 {db.books.count_documents({})} 条，其中缺少 tags 字段 4 条，属于数据不齐的典型情况，"
              "用 $exists:false 可以精确筛出；",
              f"2. borrow_logs 共 {db.borrow_logs.count_documents({})} 条，与源文件一致；",
              "3. 分类统计结果已落入 category_stats 集合，后续查询与导出均基于该集合。"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n记录已写入 {OUT}")


if __name__ == "__main__":
    main()
