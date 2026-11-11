"""副本集运维与验证工具。

子命令：
    status     副本集状态（角色、健康、oplog 延迟）
    readpref   读取偏好验证（primary / secondaryPreferred / secondary）
    probe      故障转移探针：持续读写并记录主节点切换时间点（结果写入 records/ha_probe.log）
    addnode    增加一个新节点（lib-rs4:27104）
    removenode 移除新节点
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from pymongo.read_preferences import ReadPreference

from config import BASE_DIR
from db import get_admin_client, get_client, get_db

LOG = BASE_DIR / "records" / "ha_probe.log"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def status() -> None:
    client = get_admin_client()
    rs = client.admin.command("replSetGetStatus")
    snap = {
        "set": rs["set"],
        "term": rs.get("term"),
        "members": [
            {"name": m["name"], "state": m["stateStr"], "health": m["health"],
             "optimeDate": m.get("optimeDate"), "pingMs": m.get("pingMs")}
            for m in rs["members"]
        ],
    }
    print(json.dumps(snap, ensure_ascii=False, indent=2, default=str))
    primary = client.admin.command("hello").get("primary")
    print(f"\n当前写入主节点：{primary}")


def readpref() -> dict[str, Any]:
    """写一条心跳文档，再用不同读取偏好读回，并记录各自落在哪个节点。"""
    from config import get_config

    cfg = get_config()
    db = get_db()
    doc = {"reader_card": "RP-TEST", "book_isbn": "RP-TEST", "status": "借出",
           "duration_days": 0, "borrow_date": datetime.now(timezone.utc),
           "note": "读取偏好验证专用，验证后删除"}
    coll = db["read_pref_demo"]
    coll.delete_many({})
    from pymongo import WriteConcern
    coll.with_options(write_concern=WriteConcern(w="majority")).insert_one(dict(doc))  # majority 保证已同步到多数节点

    rows = []
    for pref, rp in (("primary", ReadPreference.PRIMARY),
                     ("primaryPreferred", ReadPreference.PRIMARY_PREFERRED),
                     ("secondary", ReadPreference.SECONDARY),
                     ("secondaryPreferred", ReadPreference.SECONDARY_PREFERRED),
                     ("nearest", ReadPreference.NEAREST)):
        client = get_client()
        # 用命令级读取偏好（read_preference=...）让驱动按偏好选节点，hello 的 me 即实际服务节点
        info = client[cfg.db_name].command({"hello": 1}, read_preference=rp)
        served = info.get("me")
        is_primary = info.get("isWritablePrimary")
        try:
            found = db["read_pref_demo"].with_options(read_preference=rp).find_one({}, {"_id": 0})
            ok = found is not None
            err = None
        except PyMongoError as exc:
            ok, err = False, f"{type(exc).__name__}: {exc}"
        rows.append({"preference": pref, "served_by": served, "is_primary_node": is_primary,
                     "read_ok": ok, "error": err})

    coll.delete_many({})
    print(f"\n{'读取偏好':<20}{'实际服务节点':<18}{'是否主节点':<10}{'读到数据'}")
    for r in rows:
        print(f"{r['preference']:<20}{str(r['served_by']):<18}{str(r['is_primary_node']):<10}{r['read_ok']}")
    return {"rows": rows}


def probe(seconds: int = 90, interval: float = 0.5) -> None:
    """故障转移探针：每 0.5 秒做一次写入 + 一次主库读 + 一次副库读。

    记录每条操作的成败、当前主节点、耗时；用于证明故障转移期间的业务影响。
    """
    from config import get_config

    uri = get_config().uri
    writer = MongoClient(uri, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000, w=1)
    reader_primary = MongoClient(uri, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000,
                                 read_preference=ReadPreference.PRIMARY)
    reader_secondary = MongoClient(uri, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000,
                                   read_preference=ReadPreference.SECONDARY_PREFERRED)
    db_name = get_config().db_name
    probe_coll = writer[db_name]["ha_probe"]
    probe_coll.delete_many({})

    LOG.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    last_primary = None
    with open(LOG, "w", encoding="utf-8") as fp:
        fp.write("时间,阶段,操作,结果,耗时ms,当前主节点,备注\n")
        while time.time() - start < seconds:
            try:
                primary = writer.admin.command("hello").get("primary")
            except PyMongoError as exc:
                primary = f"ERR:{type(exc).__name__}"
            if primary != last_primary:
                fp.write(f"{_now()},切换,主节点变化,,0,{primary},"
                         f"{'首次发现' if last_primary is None else '由 ' + str(last_primary) + ' 变更'}\n")
                fp.flush()
                last_primary = primary

            # 写入（每次写一条，便于观察写入中断与恢复）
            t0 = time.perf_counter()
            try:
                probe_coll.insert_one({"ts": datetime.now(timezone.utc), "seq": int(time.time() * 1000)})
                fp.write(f"{_now()},写入,insert_one,成功,{round((time.perf_counter()-t0)*1000,1)},{primary},\n")
            except PyMongoError as exc:
                fp.write(f"{_now()},写入,insert_one,失败,{round((time.perf_counter()-t0)*1000,1)},"
                         f"{primary},{type(exc).__name__}: {str(exc)[:60]}\n")

            # 主节点读
            t0 = time.perf_counter()
            try:
                n = reader_primary[db_name].books.count_documents({})
                fp.write(f"{_now()},读取,primary 读 books,成功,{round((time.perf_counter()-t0)*1000,1)},"
                         f"{primary},{n} 条\n")
            except PyMongoError as exc:
                fp.write(f"{_now()},读取,primary 读 books,失败,{round((time.perf_counter()-t0)*1000,1)},"
                         f"{primary},{type(exc).__name__}: {str(exc)[:60]}\n")

            # 副节点读（secondaryPreferred 会在无可读副节点时回落主节点）
            t0 = time.perf_counter()
            try:
                served = reader_secondary.admin.command("hello").get("me")
                doc = reader_secondary[db_name].books.find_one({}, {"_id": 0, "title": 1})
                fp.write(f"{_now()},读取,secondaryPreferred 读 books,成功,"
                         f"{round((time.perf_counter()-t0)*1000,1)},{primary},{served} 返回 {doc}\n")
            except PyMongoError as exc:
                fp.write(f"{_now()},读取,secondaryPreferred 读 books,失败,"
                         f"{round((time.perf_counter()-t0)*1000,1)},{primary},{type(exc).__name__}\n")
            fp.flush()
            time.sleep(interval)
    writer.close()
    reader_primary.close()
    reader_secondary.close()
    print(f"探测结束，结果写入 {LOG}")


def _rs_config() -> dict[str, Any]:
    client = get_client()
    return client.admin.command("replSetGetConfig")["config"]


def addnode(name: str = "lib-rs4:27104") -> None:
    client = get_admin_client()
    cfg = client.admin.command("replSetGetConfig")["config"]
    if any(m["host"] == name for m in cfg["members"]):
        print(f"节点 {name} 已存在")
        return
    cfg["version"] += 1
    cfg["members"].append({"_id": max(m["_id"] for m in cfg["members"]) + 1, "host": name,
                           "priority": 0, "votes": 1})
    client.admin.command("replSetReconfig", cfg)
    print(f"已添加节点 {name}")


def removenode(name: str = "lib-rs4:27104") -> None:
    client = get_admin_client()
    cfg = client.admin.command("replSetGetConfig")["config"]
    if not any(m["host"] == name for m in cfg["members"]):
        print(f"节点 {name} 不存在")
        return
    cfg["version"] += 1
    cfg["members"] = [m for m in cfg["members"] if m["host"] != name]
    client.admin.command("replSetReconfig", cfg, force=True)
    print(f"已移除节点 {name}")


def watch(duration: int = 0, interval: float = 2.0) -> None:
    """单行输出副本集角色变化，便于外部脚本按时间点记录故障转移过程。"""
    client = get_admin_client()
    start = time.time()
    first = True
    while True:
        try:
            rs = client.admin.command("replSetGetStatus")
            members = ", ".join(f"{m['name']}={m['stateStr']}" for m in rs["members"])
            primary = next((m["name"] for m in rs["members"] if m["stateStr"] == "PRIMARY"), "无主")
            print(f"{_now()}  term={rs.get('term')} primary={primary} | {members}", flush=True)
        except PyMongoError as exc:
            print(f"{_now()}  状态查询失败 {type(exc).__name__}: {str(exc)[:60]}", flush=True)
        first = False
        # interval<=0 或 duration<=0：只输出一次快照
        if interval <= 0 or duration <= 0 or time.time() - start >= duration:
            break
        time.sleep(interval)


COMMANDS = {"status": status, "readpref": readpref, "probe": probe, "watch": watch,
            "addnode": addnode, "removenode": removenode}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "probe":
        probe(int(sys.argv[2]) if len(sys.argv) > 2 else 90)
    elif cmd == "watch":
        watch(int(sys.argv[2]) if len(sys.argv) > 2 else 0,
              float(sys.argv[3]) if len(sys.argv) > 3 else 2.0)
    elif cmd in ("addnode", "removenode"):
        COMMANDS[cmd](sys.argv[2] if len(sys.argv) > 2 else "lib-rs4:27104")
    else:
        COMMANDS[cmd]()
