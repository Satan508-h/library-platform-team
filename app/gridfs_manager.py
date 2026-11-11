"""GridFS 文件存储模块：电子书 PDF 与封面图的上传、检索、下载与字节校验。

存储结构：fs.files（文件元数据）+ fs.chunks（数据块，默认 255KB/块）；
业务侧通过 books.ebook_name 关联到 fs.files.filename。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gridfs import GridFSBucket
from pymongo import ASCENDING

import audit
from config import get_config
from db import get_db

BUCKET = "fs"


def _bucket() -> GridFSBucket:
    return GridFSBucket(get_db(), bucket_name=get_config().gridfs_bucket)


def ensure_indexes() -> None:
    db = get_db()
    db["fs.files"].create_index([("filename", ASCENDING)], name="idx_filename")
    db["fs.files"].create_index([("metadata.isbn", ASCENDING)], name="idx_meta_isbn")


def upload_file(path: str | Path, isbn: str, kind: str, original_name: str | None = None,
                operator: str = "lib_rw") -> dict[str, Any]:
    """上传单个文件，写入元数据（关联 ISBN、文件类型、原始文件名、业务归属）。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{path}")
    raw = path.read_bytes()
    bucket = _bucket()
    # 同名字节流若已存在则先删除，保证可重复执行
    if get_db()["fs.files"].find_one({"filename": path.name}):
        for f in get_db()["fs.files"].find({"filename": path.name}):
            bucket.delete(f["_id"])
    file_id = bucket.upload_from_stream(
        path.name,
        raw,
        metadata={
            "isbn": isbn,
            "file_type": kind,                 # ebook / cover
            "original_name": original_name or path.name,
            "content_type": "application/pdf" if kind == "ebook" else "image/png",
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "upload_time": datetime.now(timezone.utc),
            "uploader": operator,
        },
    )
    audit.log("upload_file", path.name, {"isbn": isbn, "kind": kind, "bytes": len(raw)}, operator=operator)
    return {"file_id": str(file_id), "filename": path.name, "bytes": len(raw), "kind": kind, "isbn": isbn}


def upload_seed_files(operator: str = "lib_rw") -> list[dict[str, Any]]:
    """按 files_manifest.txt 批量上传 3 个 PDF 与 3 张封面，并回写 books.ebook_name。"""
    cfg = get_config()
    manifest = json.loads((cfg.data_dir / "gridfs_files" / "files_manifest.txt").read_text(encoding="utf-8"))
    results = []
    for item in manifest["ebooks"]:
        results.append(upload_file(cfg.data_dir / "gridfs_files" / item["filename"],
                                   item["related_isbn"], "ebook", item["filename"], operator))
    for item in manifest["covers"]:
        results.append(upload_file(cfg.data_dir / "gridfs_files" / item["filename"],
                                   item["related_isbn"], "cover", item["filename"], operator))
    # 封面文件名与电子书同名替换，便于业务按 ISBN 关联
    db = get_db()
    for item in manifest["ebooks"]:
        db.books.update_one({"isbn": item["related_isbn"]},
                            {"$set": {"ebook_name": item["filename"],
                                      "cover_name": item["filename"].replace("ebook_", "cover_").replace(".pdf", ".png")}})
    return results


def list_files(kind: str | None = None) -> list[dict[str, Any]]:
    """列出 GridFS 中所有文件，含大小与上传时间。"""
    cond = {"metadata.file_type": kind} if kind else {}
    db = get_db()
    rows = []
    for f in db["fs.files"].find(cond, {"filename": 1, "length": 1, "uploadDate": 1, "metadata": 1}) \
                        .sort("uploadDate", 1):
        chunks = db["fs.chunks"].count_documents({"files_id": f["_id"]})
        rows.append({
            "filename": f["filename"],
            "bytes": f.get("length") or f.get("metadata", {}).get("bytes"),
            "chunks": chunks,
            "upload_time": f.get("uploadDate"),
            "isbn": f.get("metadata", {}).get("isbn"),
            "file_type": f.get("metadata", {}).get("file_type"),
            "sha256": f.get("metadata", {}).get("sha256", "")[:16],
        })
    return rows


def find_by_book_title(title_keyword: str) -> list[dict[str, Any]]:
    """按书名查询其电子书：books.title 模糊匹配 -> ISBN -> fs.files.metadata.isbn。"""
    db = get_db()
    books = list(db.books.find({"title": {"$regex": title_keyword}}, {"isbn": 1, "title": 1, "ebook_name": 1}))
    if not books:
        return []
    isbns = [b["isbn"] for b in books]
    files = list(db["fs.files"].find({"metadata.isbn": {"$in": isbns}},
                                     {"filename": 1, "length": 1, "metadata": 1}))
    mapping = {b["isbn"]: b["title"] for b in books}
    return [{"filename": f["filename"], "bytes": f["length"], "isbn": f["metadata"]["isbn"],
             "title": mapping.get(f["metadata"]["isbn"], ""), "file_type": f["metadata"]["file_type"]}
            for f in files]


def download(filename: str, dest_dir: Path | None = None, operator: str = "lib_rw") -> dict[str, Any]:
    """按文件名下载到本地，返回字节数与源文件/元数据字节数用于校验。"""
    cfg = get_config()
    dest_dir = Path(dest_dir) if dest_dir else cfg.gridfs_download_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    db = get_db()
    meta = db["fs.files"].find_one({"filename": filename})
    if not meta:
        raise FileNotFoundError(f"GridFS 中不存在文件：{filename}")
    dest = dest_dir / filename
    _bucket().download_to_stream(meta["_id"], dest.open("wb"))

    downloaded = dest.stat().st_size
    source_path = cfg.data_dir / "gridfs_files" / filename
    source_bytes = source_path.stat().st_size if source_path.exists() else None
    ok = (downloaded == meta.get("length")) and (source_bytes is None or downloaded == source_bytes)
    audit.log("download_file", filename,
              {"bytes": downloaded, "meta_bytes": meta.get("length"), "source_bytes": source_bytes,
               "match": ok}, operator=operator)
    return {"filename": filename, "dest": str(dest), "downloaded_bytes": downloaded,
            "gridfs_length": meta.get("length"), "source_bytes": source_bytes, "match": ok}


def delete_file(filename: str, operator: str = "lib_rw") -> bool:
    db = get_db()
    meta = db["fs.files"].find_one({"filename": filename})
    if not meta:
        return False
    _bucket().delete(meta["_id"])
    audit.log("delete_file", filename, {"bytes": meta.get("length")}, operator=operator)
    return True


def print_files(kind: str | None = None) -> None:
    rows = list_files(kind)
    print(f"\nGridFS 文件清单（共 {len(rows)} 个）：")
    print(f"{'文件名':<16}{'字节':>8}{'块数':>6}  {'上传时间':<21}{'ISBN':<16}{'类型'}")
    for r in rows:
        ts = r["upload_time"].astimezone().strftime("%Y-%m-%d %H:%M:%S") if r["upload_time"] else "-"
        print(f"{r['filename']:<16}{r['bytes']:>8}{r['chunks']:>6}  {ts:<21}{r['isbn']:<16}{r['file_type']}")


if __name__ == "__main__":
    print_files()
