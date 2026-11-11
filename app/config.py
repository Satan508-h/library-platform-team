"""配置加载模块。

设计要点：
1. 不硬编码任何连接串与绝对路径：连接串来自 config/config.json，路径由本文件位置推导，
   并允许通过环境变量 WISELIB_CONFIG / WISELIB_PROFILE / WISELIB_DATA 覆盖。
2. 支持三种部署形态（单机 / 副本集 / 分片集群）的切换，程序其余模块无需改动。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# 项目根目录：app/ 的上一级
BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_CONFIG = BASE_DIR / "config" / "config.json"


class ConfigError(RuntimeError):
    """配置缺失或非法时抛出。"""


class Config:
    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path else Path(os.environ.get("WISELIB_CONFIG", DEFAULT_CONFIG))
        if not self.path.exists():
            raise ConfigError(f"配置文件不存在：{self.path}")
        with open(self.path, encoding="utf-8") as fp:
            self._raw: dict[str, Any] = json.load(fp)

        # 允许用环境变量临时切换部署形态，避免改文件
        self.profile_name = os.environ.get("WISELIB_PROFILE") or self._raw.get("active", "single")
        if self.profile_name not in self._raw["profiles"]:
            raise ConfigError(f"未定义的部署形态：{self.profile_name}")

    # ---------------- 连接相关 ----------------
    @property
    def profile(self) -> dict[str, Any]:
        return self._raw["profiles"][self.profile_name]

    @property
    def uri(self) -> str:
        return os.environ.get("WISELIB_URI") or self.profile["uri"]

    @property
    def db_name(self) -> str:
        return self.profile.get("db", "library")

    @property
    def read_preference(self) -> str:
        return os.environ.get("WISELIB_READ_PREF") or self.profile.get("read_preference", "primary")

    @property
    def profile_desc(self) -> str:
        return self.profile.get("desc", self.profile_name)

    # ---------------- 路径相关 ----------------
    @property
    def data_dir(self) -> Path:
        """配套数据目录（只读，禁止修改原始数据）。"""
        env = os.environ.get("WISELIB_DATA")
        p = Path(env) if env else (BASE_DIR / self._raw["data_dir"])
        return p.expanduser().resolve()

    @property
    def gridfs_download_dir(self) -> Path:
        p = BASE_DIR / self._raw.get("gridfs", {}).get("download_dir", "exports/downloaded")
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def gridfs_bucket(self) -> str:
        return self._raw.get("gridfs", {}).get("bucket", "fs")

    @property
    def users(self) -> dict[str, Any]:
        return self._raw.get("users", {})


_config_cache: Config | None = None


def get_config(reload: bool = False) -> Config:
    """进程内单例，避免重复读盘。"""
    global _config_cache
    if _config_cache is None or reload:
        _config_cache = Config()
    return _config_cache
