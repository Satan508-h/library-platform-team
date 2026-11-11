"""分片集群验证：分片/块分布、定向查询与跨分片查询对比（任务六）。"""
import time
from collections import Counter

from pymongo import ASCENDING

from config import get_config
from db import get_client, get_db, get_admin_client
from ha_tools import _now


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> None:
    cfg = get_config()
    print(f"连接：{cfg.profile_name} / {cfg.uri.split('@')[-1]}")
    client = get_client()
    db = get_db()
    admin = get_admin_client()

    section("1. 集群拓扑")
    shards = list(admin.get_database("config")["shards"].find({}, {"_id": 1, "host": 1}))
    for s in shards:
        print(f"  分片 {s['_id']}: {s['host']}")
    colls = list(admin.get_database("config")["collections"].find(
        {"_id": "library.borrow_logs"}, {"key": 1, "unique": 1}))
    print(f"  分片集合 library.borrow_logs 分片键：{colls[0]['key'] if colls else '未分片'}")

    section("2. 文档在分片上的分布")
    stats = db.command("collStats", "borrow_logs")
    total = stats.get("count", 0)
    for name, info in (stats.get("shards") or {}).items():
        cnt = info.get("count", 0)
        pct = (cnt / total * 100) if total else 0
        print(f"  {name}: {cnt} 条（{pct:.1f}%），存储 {info.get('storageSize', 0)} 字节")
    meta = admin.get_database("config")["collections"].find_one({"_id": "library.borrow_logs"})
    chunks = list(admin.get_database("config")["chunks"].find({"uuid": meta["uuid"]})) if meta else []
    by_shard = Counter(c["shard"] for c in chunks)
    print(f"  块数量：{len(chunks)}，按分片统计：{dict(by_shard)}")

    section("3. 定向查询（命中分片键 reader_card）")
    reader = db["borrow_logs"].find_one({}, {"reader_card": 1})["reader_card"]
    print(f"  取样本读者卡号：{reader}")
    exp = db.command("explain", {"find": "borrow_logs", "filter": {"reader_card": reader}},
                     verbosity="executionStats")
    stages = _stage_names(exp)
    print(f"  执行阶段：{stages}")
    print(f"  扫描文档数：{_docs_examined(exp)}，返回 {exp.get('executionStats', {}).get('nReturned')} 条")

    t0 = time.perf_counter()
    n = 0
    for _ in range(200):
        n += db["borrow_logs"].count_documents({"reader_card": reader})
    t_target = (time.perf_counter() - t0) / 200 * 1000
    print(f"  200 次 count 平均耗时：{t_target:.2f} ms（命中 {n // 200} 条）")

    section("4. 跨分片查询（不命中分片键，按借阅状态）")
    exp2 = db.command("explain", {"find": "borrow_logs", "filter": {"status": "逾期"}},
                      verbosity="executionStats")
    print(f"  执行阶段：{_stage_names(exp2)}")
    print(f"  扫描文档数：{_docs_examined(exp2)}，返回 {exp2.get('executionStats', {}).get('nReturned')} 条")
    t0 = time.perf_counter()
    for _ in range(200):
        db["borrow_logs"].count_documents({"status": "逾期"})
    t_scatter = (time.perf_counter() - t0) / 200 * 1000
    print(f"  200 次 count 平均耗时：{t_scatter:.2f} ms")

    section("5. 聚合统计（跨分片合并）")
    pipeline = [{"$group": {"_id": "$status", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}]
    for row in db["borrow_logs"].aggregate(pipeline):
        print(f"  status={row['_id']}: {row['n']} 条")

    section("6. 结论")
    print(f"  定向查询 {t_target:.2f} ms vs 跨分片查询 {t_scatter:.2f} ms"
          f"（跨分片为定向的 {t_scatter / t_target:.1f} 倍）")
    client.close()


def _stage_names(exp) -> str:
    """从 explain 结果中收集出现的阶段名，判断是否单分片执行。"""
    names = []

    def walk(node):
        if isinstance(node, dict):
            st = node.get("stage")
            if st and st not in names:
                names.append(st)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(exp)
    return " → ".join(names[:6])


def _docs_examined(exp) -> int:
    stats = exp.get("executionStats") or {}
    if "totalDocsExamined" in stats:
        return stats["totalDocsExamined"]
    shards = exp.get("shards") or {}
    return sum((s.get("executionStats") or {}).get("totalDocsExamined", 0) for s in shards.values())


if __name__ == "__main__":
    main()
