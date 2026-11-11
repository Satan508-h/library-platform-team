"""统一的 MongoDB 连接模块。

所有程序文件均通过本模块获取连接，禁止在业务模块里自行 MongoClient，
这样切换单机 / 副本集 / 分片集群时只需修改 config.json 或环境变量。
"""
from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.read_preferences import ReadPreference

from config import get_config

# 字符串 -> 读取偏好对象，供副本集读取偏好实验使用
READ_PREFERENCES = {
    "primary": ReadPreference.PRIMARY,
    "primarypreferred": ReadPreference.PRIMARY_PREFERRED,
    "secondary": ReadPreference.SECONDARY,
    "secondarypreferred": ReadPreference.SECONDARY_PREFERRED,
    "nearest": ReadPreference.NEAREST,
}

_clients: dict[str, MongoClient] = {}


def get_client(read_preference: str | None = None, profile: str | None = None) -> MongoClient:
    """按读取偏好缓存客户端（同一偏好复用连接池）。"""
    cfg = get_config()
    pref_name = (read_preference or cfg.read_preference).lower()
    key = f"{profile or cfg.profile_name}:{pref_name}"
    if key in _clients:
        return _clients[key]
    pref = READ_PREFERENCES.get(pref_name)
    if pref is None:
        raise ValueError(f"不支持的读取偏好：{read_preference}")

    kwargs: dict[str, Any] = {
        "serverSelectionTimeoutMS": 5000,
        "appname": f"wiselib-{cfg.profile_name}",
        "read_preference": pref,
        "w": "majority" if pref_name != "primary" else 1,
        # 统一返回带 UTC 时区的 datetime，避免与 datetime.now(timezone.utc) 相减时报错
        "tz_aware": True,
    }
    client = MongoClient(cfg.uri, **kwargs)
    _clients[key] = client
    return client


def get_db(read_preference: str | None = None) -> Database:
    cfg = get_config()
    return get_client(read_preference).get_database(cfg.db_name)


def get_session(read_preference: str | None = None) -> ClientSession:
    return get_client(read_preference).start_session()


def ping(read_preference: str | None = None) -> dict[str, Any]:
    """连通性与节点角色检查，副本集下可看到主从信息。"""
    cfg = get_config()
    client = get_client(read_preference)
    info = client.admin.command("hello") if cfg.profile_name != "single" else client.admin.command("ping")
    keep = ("ismaster", "isWritablePrimary", "setName", "primary", "hosts", "me", "maxWireVersion")
    summary = {k: info[k] for k in keep if k in info}
    summary["profile"] = cfg.profile_name
    summary["read_preference"] = cfg.read_preference
    summary["uri_masked"] = cfg.uri.split("@")[0] + "@***" if "@" in cfg.uri else cfg.uri
    return summary


def uri_for(user_key: str) -> str:
    """按 config.json 中的账号信息生成 URI（运维类命令需要 admin 账号）。"""
    from urllib.parse import quote_plus

    cfg = get_config()
    info = cfg.users[user_key]
    rest = cfg.uri.split("//", 1)[1]
    rest = rest.split("@", 1)[1] if "@" in rest else rest
    return f"mongodb://{info['user']}:{quote_plus(info['pwd'])}@{rest}"


def get_admin_client() -> MongoClient:
    """管理账号客户端：副本集状态、节点增删等运维命令需要 clusterMonitor / clusterManager 权限。"""
    key = "admin-client"
    if key not in _clients:
        _clients[key] = MongoClient(uri_for("admin"), serverSelectionTimeoutMS=5000, tz_aware=True)
    return _clients[key]


def close_all() -> None:
    for c in _clients.values():
        c.close()
    _clients.clear()


if __name__ == "__main__":
    import json

    print(json.dumps(ping(), ensure_ascii=False, indent=2, default=str))
