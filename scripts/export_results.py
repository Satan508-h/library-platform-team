"""导出统计结果文件（CSV + JSON），供验收核对（任务七）。"""
import csv
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from db import get_client, get_db, close_all  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "exports"
OUT.mkdir(parents=True, exist_ok=True)


def write_csv(name: str, fields: list[str], rows: list[dict]) -> Path:
    path = OUT / name
    with open(path, "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _flat(r.get(k)) for k in fields})
    print(f"  写出 {name}（{len(rows)} 行）")
    return path


def _flat(v):
    if isinstance(v, dict):
        return "; ".join(f"{k}={v2}" for k, v2 in v.items())
    if isinstance(v, list):
        return "/".join(str(x) for x in v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def main() -> None:
    db = get_db()
    print(f"导出目标：{OUT}")

    write_csv("books.csv",
              ["isbn", "title", "author", "publisher", "publish_date", "category",
               "price", "stock", "rating", "tags", "location", "borrow_count", "ebook_name"],
              list(db["books"].find({}, {"_id": 0}).sort("isbn", 1)))

    write_csv("readers.csv",
              ["card_no", "name", "gender", "college", "level", "register_date",
               "fav_categories", "email", "phone"],
              list(db["readers"].find({}, {"_id": 0}).sort("card_no", 1)))

    write_csv("borrow_logs.csv",
              ["reader_card", "book_isbn", "borrow_date", "return_date", "status", "duration_days"],
              list(db["borrow_logs"].find({}, {"_id": 0}).sort("borrow_date", 1)))

    write_csv("category_stats.csv",
              ["category", "book_count", "avg_price", "avg_rating", "total_stock"],
              list(db["category_stats"].find({}, {"_id": 0}).sort("book_count", -1)))

    # 学院借阅排行（多集合 $lookup）
    college = list(db["borrow_logs"].aggregate([
        {"$lookup": {"from": "readers", "localField": "reader_card",
                     "foreignField": "card_no", "as": "r"}},
        {"$unwind": "$r"},
        {"$group": {"_id": "$r.college", "total": {"$sum": 1},
                    "readers": {"$addToSet": "$reader_card"}}},
        {"$project": {"college": "$_id", "total": 1, "reader_count": {"$size": "$readers"},
                      "_id": 0}},
        {"$sort": {"total": -1}},
    ]))
    write_csv("college_borrow_rank.csv", ["college", "total", "reader_count"], college)

    # 借阅趋势（按年月）
    trend = list(db["borrow_logs"].aggregate([
        {"$group": {"_id": {"y": {"$year": "$borrow_date"}, "m": {"$month": "$borrow_date"}},
                    "total": {"$sum": 1}}},
        {"$sort": {"_id.y": 1, "_id.m": 1}},
    ]))
    trend_rows = [{"period": f"{t['_id']['y']}-{t['_id']['m']:02d}", "total": t["total"]}
                  for t in trend]
    write_csv("monthly_trend.csv", ["period", "total"], trend_rows)

    # 借阅次数 Top10（按字段 borrow_count）
    top = list(db["books"].find({}, {"_id": 0, "title": 1, "isbn": 1, "borrow_count": 1,
                                    "location": 1}).sort("borrow_count", -1).limit(10))
    write_csv("borrow_top10.csv", ["title", "isbn", "borrow_count", "location"], top)

    # 流水实数排行的 Top10（与字段值交叉校验）
    top_real = list(db["borrow_logs"].aggregate([
        {"$group": {"_id": "$book_isbn", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}},
        {"$limit": 10},
        {"$lookup": {"from": "books", "localField": "_id", "foreignField": "isbn", "as": "b"}},
        {"$unwind": "$b"},
        {"$project": {"_id": 0, "book_isbn": "$_id", "title": "$b.title", "total": 1}},
    ]))
    write_csv("borrow_top10_by_logs.csv", ["title", "book_isbn", "total"], top_real)

    # 概览
    overview = {
        "导出时间": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "集合计数": {name: db[name].count_documents({})
                     for name in ("books", "readers", "borrow_logs", "category_stats",
                                  "audit_logs")},
        "gridfs_files": db["fs.files"].count_documents({}),
        "借阅状态分布": {r["_id"]: r["n"] for r in db["borrow_logs"].aggregate(
            [{"$group": {"_id": "$status", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}])},
        "学院借阅排行": college,
        "月度趋势": trend_rows,
        "借阅Top10（字段值）": top,
        "借阅Top10（流水实数）": top_real,
    }
    with open(OUT / "overview.json", "w", encoding="utf-8") as fp:
        json.dump(overview, fp, ensure_ascii=False, indent=2, default=str)
    print("  写出 overview.json")
    print(f"概览：{overview['集合计数']}")
    close_all()


if __name__ == "__main__":
    main()
