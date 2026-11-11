"""索引优化对比：同一查询在建立索引前后的执行计划与耗时。

三项指标：
1. 执行计划阶段（COLLSCAN / IXSCAN / SORT）；
2. executionStats 中的 totalDocsExamined / totalKeysExamined（扫描量对比，比耗时更能说明问题）；
3. 重复 200 次的平均 / 中位数耗时。

另外在 20 万条的放大集合 bench_borrow 上做一次实验，让耗时差异从“亚毫秒噪声”变成可观测的倍数。
结果写入 records/index_benchmark.json 与 records/index_benchmark.md。
"""
from __future__ import annotations

import json
import random
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient

from config import BASE_DIR, get_config
from db import get_db

RECORDS = BASE_DIR / "records"
ITERATIONS = 200
BENCH_COLLECTION = "bench_borrow"
BENCH_DOCS = 200_000


def explain_stats(db, coll: str, query: dict, sort, limit: int | None = None) -> dict[str, Any]:
    """用 executionStats 拿到真实扫描量。"""
    cmd: dict[str, Any] = {"find": coll, "filter": query}
    if sort:
        cmd["sort"] = dict(sort)
    if limit:
        cmd["limit"] = limit
    raw = db.command({"explain": cmd, "verbosity": "executionStats"})
    stats = raw.get("executionStats", {})
    plan_text = json.dumps(raw.get("queryPlanner", {}).get("winningPlan", {}), default=str)
    stages = []
    for stage in ("COLLSCAN", "IXSCAN", "SORT", "FETCH", "TEXT_MATCH"):
        if f'"{stage}"' in plan_text or f"'{stage}'" in plan_text:
            stages.append(stage)
    index_name = None
    walk = json.loads(plan_text)
    stack = [walk]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if item.get("indexName") and index_name is None:
                index_name = item["indexName"]
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return {
        "stages": stages,
        "scan_type": "IXSCAN" if "IXSCAN" in stages else ("COLLSCAN" if "COLLSCAN" in stages else "?"),
        "index_used": index_name,
        "docs_examined": stats.get("totalDocsExamined"),
        "keys_examined": stats.get("totalKeysExamined"),
        "n_returned": stats.get("nReturned"),
        "execution_ms": stats.get("executionTimeMillis"),
    }


def timed(db, coll: str, query: dict, sort, iterations: int, limit: int | None = None) -> dict[str, Any]:
    durations = []
    cursor_sort = sort
    for _ in range(iterations):
        start = time.perf_counter()
        cur = db[coll].find(query)
        if cursor_sort:
            cur = cur.sort(cursor_sort)
        if limit:
            cur = cur.limit(limit)
        list(cur)
        durations.append((time.perf_counter() - start) * 1000)
    durations.sort()
    return {
        "avg_ms": round(statistics.mean(durations), 3),
        "median_ms": round(statistics.median(durations), 3),
        "p95_ms": round(durations[int(len(durations) * 0.95) - 1], 3),
        "min_ms": round(durations[0], 3),
        "iterations": iterations,
    }


def drop_indexes(db, collection: str, names: list[str]) -> None:
    existing = {i["name"] for i in db[collection].list_indexes()}
    for name in names:
        if name in existing:
            db[collection].drop_index(name)


def build_cases(db) -> list[dict[str, Any]]:
    readers = [r["card_no"] for r in db.readers.find({}, {"card_no": 1}).limit(3)]
    return [
        {
            "name": "books：类别 + 价格区间（50 条）",
            "collection": "books",
            "drop": ["idx_category_price"],
            "create": [([("category", ASCENDING), ("price", ASCENDING)], "idx_category_price")],
            "restore": [],
            "filter": {"category": "计算机", "price": {"$gte": 80, "$lte": 130}},
            "sort": None,
        },
        {
            "name": "borrow_logs：按读者取流水并倒序（3000 条）",
            "collection": "borrow_logs",
            "drop": ["idx_reader_date", "idx_borrow_date"],
            "create": [([("reader_card", ASCENDING), ("borrow_date", DESCENDING)], "idx_reader_date")],
            "restore": [([("borrow_date", DESCENDING)], "idx_borrow_date")],
            "filter": {"reader_card": {"$in": readers}},
            "sort": [("borrow_date", DESCENDING)],
        },
        {
            "name": "borrow_logs：时间范围 + 倒序（3000 条）",
            "collection": "borrow_logs",
            "drop": ["idx_borrow_date"],
            "create": [([("borrow_date", DESCENDING)], "idx_borrow_date")],
            "restore": [],
            "filter": {"borrow_date": {"$gte": datetime(2025, 1, 1, tzinfo=timezone.utc),
                                       "$lt": datetime(2025, 4, 1, tzinfo=timezone.utc)}},
            "sort": [("borrow_date", DESCENDING)],
        },
        {
            "name": f"bench_borrow：按读者 + 倒序（{BENCH_DOCS:,} 条放大实验）",
            "collection": BENCH_COLLECTION,
            "drop": ["idx_bench_reader_date"],
            "create": [([("reader_card", ASCENDING), ("borrow_date", DESCENDING)], "idx_bench_reader_date")],
            "restore": [],
            "filter": {"reader_card": "R000042"},
            "sort": [("borrow_date", DESCENDING)],
            "iterations": 20,
        },
    ]


def prepare_bench_collection(db) -> None:
    """生成 20 万条放大数据（仅用于索引实验，实验结束后删除）。"""
    if db[BENCH_COLLECTION].estimated_document_count() >= BENCH_DOCS:
        print(f"{BENCH_COLLECTION} 已存在，跳过生成")
        return
    db[BENCH_COLLECTION].drop()
    random.seed(20251111)
    base = datetime(2023, 1, 1, tzinfo=timezone.utc)
    batch = []
    for i in range(BENCH_DOCS):
        batch.append({
            "reader_card": f"R{random.randint(0, 999):06d}",
            "book_isbn": f"978{random.randint(100000000, 999999999)}",
            "borrow_date": base + timedelta(minutes=random.randint(0, 525600 * 2)),
            "status": random.choice(["已归还", "借出", "逾期"]),
        })
        if len(batch) >= 10000:
            db[BENCH_COLLECTION].insert_many(batch)
            batch = []
    if batch:
        db[BENCH_COLLECTION].insert_many(batch)
    print(f"已生成 {BENCH_COLLECTION}：{db[BENCH_COLLECTION].estimated_document_count():,} 条")


def run_case(db, case: dict[str, Any]) -> dict[str, Any]:
    coll = db[case["collection"]]
    iterations = case.get("iterations", ITERATIONS)

    drop_indexes(db, case["collection"], case["drop"])
    before_plan = explain_stats(db, case["collection"], case["filter"], case["sort"], limit=10)
    before_time = timed(db, case["collection"], case["filter"], case["sort"], iterations, limit=10)

    for keys, name in case["create"]:
        coll.create_index(keys, name=name)
    after_plan = explain_stats(db, case["collection"], case["filter"], case["sort"], limit=10)
    after_time = timed(db, case["collection"], case["filter"], case["sort"], iterations, limit=10)

    # 恢复被临时删掉的、属于最终索引方案的索引
    for keys, name in case["restore"]:
        coll.create_index(keys, name=name)

    docs_before = before_plan["docs_examined"] or 1
    docs_after = after_plan["docs_examined"] or 1
    return {
        "case": case["name"],
        "collection": case["collection"],
        "index": case["create"][0][1],
        "n_returned": after_plan["n_returned"],
        "before": {**before_plan, **before_time},
        "after": {**after_plan, **after_time},
        "speedup_x": round(before_time["avg_ms"] / after_time["avg_ms"], 2) if after_time["avg_ms"] else None,
        "docs_examined_ratio": round(docs_before / docs_after, 1),
        "consistent": before_plan["n_returned"] == after_plan["n_returned"],
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }


def write_markdown(results: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "# 索引优化前后对比（benchmark_index.py 自动生成）",
        "",
        f"- 生成时间：{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 每项查询重复执行：{ITERATIONS} 次（放大实验 20 次），取平均 / 中位数 / P95",
        "- 扫描量取自 explain(executionStats) 的 totalDocsExamined / totalKeysExamined",
        "",
        "| 查询场景 | 索引 | 前：扫描方式 | 前：扫描文档 | 前：平均耗时(ms) | 后：扫描方式 | 后：扫描文档 | 后：平均耗时(ms) | 耗时提速 | 扫描量下降 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['case']} | {r['index']} | {r['before']['scan_type']} | {r['before']['docs_examined']} | "
            f"{r['before']['avg_ms']:.3f} | {r['after']['scan_type']} | {r['after']['docs_examined']} | "
            f"{r['after']['avg_ms']:.3f} | {r['speedup_x']}x | {r['docs_examined_ratio']}x |"
        )
    lines += [
        "",
        "结论：",
        "1. 建立索引后扫描方式由 COLLSCAN 变为 IXSCAN，扫描文档数下降到与命中结果同量级；",
        "2. 50 条与 3000 条的集合规模太小，绝对耗时为亚毫秒级，耗时差异受缓存与噪声影响；",
        f"3. 因此在 {BENCH_DOCS:,} 条的 bench_borrow 上放大验证，索引带来的耗时差异才稳定可观测；",
        "4. 排序场景（borrow_date 倒序）在无索引时会额外出现 SORT 阶段，属于内存排序，数据量增长后最先出问题。",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    RECORDS.mkdir(parents=True, exist_ok=True)
    db = get_db()
    prepare_bench_collection(db)
    results = []
    for case in build_cases(db):
        print(f"正在测试：{case['name']} ...")
        results.append(run_case(db, case))

    out_json = RECORDS / "index_benchmark.json"
    out_md = RECORDS / "index_benchmark.md"
    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_markdown(results, out_md)

    for r in results:
        print(f"\n{r['case']}")
        print(f"  索引前：{r['before']['scan_type']:<8} 扫描文档 {r['before']['docs_examined']:>7} "
              f"平均 {r['before']['avg_ms']:>8.3f} ms")
        print(f"  索引后：{r['after']['scan_type']:<8} 扫描文档 {r['after']['docs_examined']:>7} "
              f"平均 {r['after']['avg_ms']:>8.3f} ms")
        print(f"  提速 {r['speedup_x']}x，扫描量下降 {r['docs_examined_ratio']}x，结果一致={r['consistent']}")

    # 实验集合清理，避免影响“各集合文档数量与源文件一致”的验收
    db[BENCH_COLLECTION].drop()
    print(f"\n已删除实验集合 {BENCH_COLLECTION}")
    print(f"结果已写入：{out_json.name} / {out_md.name}")


if __name__ == "__main__":
    main()
