"""清理功能演示产生的临时借还流水，恢复 3000 条基线（任务三收尾）。"""
import datetime as dt
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from db import get_db, close_all  # noqa: E402
from audit import log as log_action  # noqa: E402


def main() -> None:
    db = get_db()
    before = db["borrow_logs"].count_documents({})
    res = db["borrow_logs"].delete_many({"borrow_date": {"$gte": dt.datetime(2026, 1, 1)}})
    after = db["borrow_logs"].count_documents({})
    print(f"清理前 {before} 条，删除演示流水 {res.deleted_count} 条，清理后 {after} 条")
    log_action("cleanup_demo_log", "borrow_logs", "success", {"deleted": res.deleted_count})
    print(f"books={db['books'].count_documents({})} readers={db['readers'].count_documents({})} "
          f"borrow_logs={after} category_stats={db['category_stats'].count_documents({})}")
    close_all()


if __name__ == "__main__":
    main()
