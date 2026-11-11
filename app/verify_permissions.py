"""访问控制验证：三个账号的权限边界。

验证项：
1. 只读账号 lib_ro：读成功；insert / update / delete 被拒绝（Not authorized）；
2. 读写账号 lib_rw：读写成功；执行管理命令（listDatabases、createUser）被拒绝；
3. 管理账号 lib_admin：管理命令成功。
"""
from __future__ import annotations

import json
import sys
from urllib.parse import quote_plus

from pymongo import MongoClient
from pymongo.errors import OperationFailure

from config import BASE_DIR, get_config
from db import get_db

RECORDS_NAME = "permission_matrix"
PROBE_USER = "perm_probe_user"


def uri_for(cfg, user_key: str) -> str:
    """按 config 中的账号信息拼接 URI，密码统一做 URL 编码。"""
    info = cfg.users[user_key]
    base = cfg.uri.split("@", 1)[1] if "@" in cfg.uri.split("//", 1)[1] else cfg.uri.split("//", 1)[1]
    return f"mongodb://{info['user']}:{quote_plus(info['pwd'])}@{base}"


def attempt(label: str, fn) -> dict:
    try:
        result = fn()
        print(f"  [允许] {label}")
        return {"case": label, "allowed": True, "result": str(result)[:120]}
    except OperationFailure as exc:
        code = exc.code
        print(f"  [拒绝] {label} -> code={code} {str(exc)[:90]}")
        return {"case": label, "allowed": False, "code": code, "message": str(exc)[:160]}
    except Exception as exc:  # noqa: BLE001
        print(f"  [异常] {label} -> {type(exc).__name__}: {exc}")
        return {"case": label, "allowed": False, "error": f"{type(exc).__name__}: {exc}"}


def check(role: str, uri: str) -> dict:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    db = client[get_config().db_name]
    print(f"\n== {role} ==")
    rows = []

    # 读
    rows.append(attempt("查询 books 文档数", lambda: db.books.count_documents({})))
    rows.append(attempt("聚合查询分类统计", lambda: list(db.books.aggregate(
        [{"$group": {"_id": "$category", "n": {"$sum": 1}}}, {"$limit": 2}]))))

    # 写
    temp = {"isbn": "TEST-PERM-0001", "title": "权限验证临时文档", "category": "计算机",
            "price": 1.0, "rating": 1.0, "stock": 1}
    rows.append(attempt("插入 books 文档", lambda: db.books.insert_one(dict(temp)).inserted_id))
    rows.append(attempt("更新 books 文档", lambda: db.books.update_one(
        {"isbn": "TEST-PERM-0001"}, {"$set": {"stock": 2}}).modified_count))
    rows.append(attempt("删除 books 文档", lambda: db.books.delete_one({"isbn": "TEST-PERM-0001"}).deleted_count))
    rows.append(attempt("写 audit_logs 操作日志", lambda: db.audit_logs.insert_one(
        {"action": "perm_test", "target": "TEST-PERM-0001"}).inserted_id))

    # 管理命令（serverStatus 需要 clusterMonitor 权限，普通业务账号不应具备）
    rows.append(attempt("查看服务器状态 serverStatus", lambda: client.admin.command("serverStatus")["uptime"]))
    rows.append(attempt("创建用户 createUser", lambda: client[get_config().db_name].command(
        "createUser", PROBE_USER, pwd="Probe@2025", roles=["read"])))
    # 清理探测用户（只有管理账号删得掉）
    try:
        client[get_config().db_name].command("dropUser", PROBE_USER)
    except OperationFailure:
        pass
    client.close()
    return {"role": role, "checks": rows}


def main() -> None:
    cfg = get_config()
    print(f"数据库：{cfg.db_name}  部署形态：{cfg.profile_name}")
    print("说明：以下“拒绝”均为 MongoDB 服务端返回的授权错误（code 13 Not authorized）。")
    matrix = [check(role, uri_for(cfg, key))
              for role, key in (("只读 lib_ro", "read_only"), ("读写 lib_rw", "read_write"),
                                ("管理 lib_admin", "admin"))]

    out = BASE_DIR / "records" / "permission_matrix.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fp:
        json.dump(matrix, fp, ensure_ascii=False, indent=2)

    print("\n汇总：")
    for item in matrix:
        denied = [c["case"] for c in item["checks"] if not c["allowed"]]
        print(f"  {item['role']:<12} 被拒绝的操作：{denied if denied else '无'}")

    # 清理读写账号可能留下的临时文档
    db = get_db()
    db.books.delete_one({"isbn": "TEST-PERM-0001"})

    failed = [c for item in matrix for c in item["checks"]
              if (item["role"].startswith("只读") and c["allowed"]
                  and c["case"].startswith(("插入", "更新", "删除", "写", "创建用户", "查看服务器")))
              or (item["role"].startswith("读写") and c["allowed"]
                  and c["case"].startswith(("创建用户", "查看服务器")))
              or (item["role"].startswith("管理") and not c["allowed"]
                  and c["case"].startswith("查看服务器"))]
    print("\n权限边界验证：" + ("通过" if not failed else f"未通过 {failed}"))
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()

