"""主程序：智慧图书馆数字资源平台（菜单式交互）。

运行：
    python app/main.py            # 交互式菜单
    python app/main.py --demo     # 无人值守演示（按固定参数跑完 8 项以上功能，便于录制过程记录）
    python app/main.py --choice 3 # 直接执行某一项功能
"""
from __future__ import annotations

import json
import sys
from typing import Any

import audit
import book_manager as bm
import borrow_manager as lm
import gridfs_manager as gm
import reader_manager as rm
import stats_manager as sm
from db import close_all, ping
from config import get_config

MENU = """
================ 智慧图书馆数字资源平台 ================
  1. 图书检索（类别 + 价格区间 + 分页排序）
  2. 标签多选匹配（$all / $in）
  3. 书名模糊检索
  4. 出版年份区间检索 / 缺失 tags 数据核查
  5. 评分 Top10（仅书名、作者、评分）
  6. 分类统计（藏书量 / 平均价格 / 平均评分）并可落库
  7. 学院借阅总量排行 Top5（$lookup 多集合联合）
  8. 按年月借阅趋势
  9. 借阅次数 Top10 图书 + 馆藏位置
 10. 借书 / 还书
 11. 上传电子书与封面到 GridFS
 12. 按书名查电子书并下载校验
 13. GridFS 文件清单
 14. 最近 100 条操作日志
 15. 平台数据总览
  0. 退出
=======================================================
"""


def _print_rows(rows: list[dict[str, Any]], title: str, limit: int = 12) -> None:
    print(f"\n{title}（共 {len(rows)} 条，展示前 {min(limit, len(rows))} 条）")
    for row in rows[:limit]:
        print("  " + json.dumps(row, ensure_ascii=False, default=str))


def f1_search(category: str = "计算机", price_min: float = 60, price_max: float = 120,
              page: int = 1, size: int = 8) -> None:
    res = bm.search(category=category, price_min=price_min, price_max=price_max, page=page, size=size)
    print(f"\n[检索] 类别={category} 价格={price_min}~{price_max} 第{res['page']}页 "
          f"每页{res['size']} -> 命中 {res['total']} 条")
    for b in res["items"]:
        print(f"  {b['title']:<32}{b['price']:>7.1f}元  评分{b['rating']:<4} 库存{b['stock']}")


def f2_tags(tags: list[str] | None = None) -> None:
    tags = tags or ["编程", "入门"]
    rows = bm.by_tags(tags, "all")
    print(f"\n[标签匹配 $all] 同时包含 {tags} -> {len(rows)} 条")
    for r in rows:
        print(f"  {r['title']:<32}{r['tags']}")
    rows_any = bm.by_tags(tags, "any")
    print(f"[标签匹配 $in] 包含任一 {tags} -> {len(rows_any)} 条")


def f3_title(keyword: str = "Python") -> None:
    rows = bm.by_title_fuzzy(keyword)
    print(f"\n[书名模糊] 关键字“{keyword}” -> {len(rows)} 条")
    for r in rows:
        print(f"  {r['title']:<36}{r['author']:<16}{r['category']}")


def f4_year_and_check(start: int = 2020, end: int = 2023) -> None:
    rows = bm.by_publish_year(start, end)
    print(f"\n[出版年份] {start}—{end} -> {len(rows)} 条")
    for r in rows[:8]:
        print(f"  {r['publish_date'].date()}  {r['title']}")
    missing = bm.missing_tags()
    print(f"[数据质量] 缺少 tags 字段的图书 -> {len(missing)} 条")
    for m in missing:
        print(f"  {m['isbn']}  {m['title']}（{m['category']}）")


def f5_top_rated() -> None:
    rows = bm.top_rated(10)
    print(f"\n[评分 Top10] 共 {len(rows)} 条（仅书名/作者/评分）")
    for i, r in enumerate(rows, 1):
        print(f"  {i:>2}. {r['rating']}  {r['title']:<34}{r['author']}")


def f6_category_stats(persist: bool = True) -> None:
    rows = sm.by_category()
    print(f"\n[分类统计] 共 {len(rows)} 个类别")
    print(f"  {'类别':<10}{'藏书量':>6}{'平均价格':>10}{'平均评分':>10}{'在架库存':>8}")
    for r in rows:
        print(f"  {r['category']:<10}{r['book_count']:>6}{r['avg_price']:>10.2f}{r['avg_rating']:>10.2f}"
              f"{r['total_stock']:>8}")
    if persist:
        n = sm.save_category_stats()
        print(f"[落库] 分类统计已写入集合 category_stats，共 {n} 条")


def f7_college_rank() -> None:
    rows = sm.college_rank(5)
    print(f"\n[学院借阅排行 Top5] 共 {len(rows)} 条")
    for i, r in enumerate(rows, 1):
        detail = "/".join(f"{d['level']}:{d['n']}" for d in r["detail"])
        print(f"  {i}. {r['college']:<18}{r['borrow_total']:>6} 次  ({detail})")


def f8_trend() -> None:
    rows = sm.monthly_trend()
    print(f"\n[借阅趋势] 共 {len(rows)} 个月份有数据")
    for r in rows:
        bar = "█" * int(r["borrow_count"] / 5)
        print(f"  {r['label']:<10}{r['borrow_count']:>4} 次  独立读者{r['unique_readers']:>3}  {bar}")
    print(f"  合计 {sum(r['borrow_count'] for r in rows)} 次")


def f9_top_books() -> None:
    rows = sm.top_borrowed_books(10)
    print(f"\n[借阅 Top10] 共 {len(rows)} 条")
    for i, r in enumerate(rows, 1):
        print(f"  {i:>2}. {r['title']:<32}借阅{r['borrow_count']:>4}次  "
              f"位置：{r.get('floor')}/{r.get('shelf')} 复本{r.get('copies')}")
    cross = sm.top_borrowed_from_logs(10)
    print("[交叉校验] 以流水实数统计的前 3 本：")
    for r in cross[:3]:
        print(f"  {r['title']:<32}流水{r['log_count']:>3}次  字段值{r.get('borrow_count_field')}")


def f10_borrow_return(card_no: str = "", isbn: str = "") -> None:
    if not card_no or not isbn:
        card_no = rm.get_db().readers.find_one({}, {"card_no": 1})["card_no"]
        isbn = bm.get_db().books.find_one({"stock": {"$gt": 0}}, {"isbn": 1})["isbn"]
    print(f"\n[借书] 读者 {card_no} 借 {isbn}")
    print("  " + json.dumps(lm.borrow(card_no, isbn), ensure_ascii=False, default=str))
    print(f"[还书] 读者 {card_no} 归还 {isbn}")
    print("  " + json.dumps(lm.give_back(card_no, isbn), ensure_ascii=False, default=str))


def f11_upload() -> None:
    rows = gm.upload_seed_files()
    print(f"\n[GridFS 上传] 共上传 {len(rows)} 个文件")
    for r in rows:
        print(f"  {r['filename']:<14}{r['bytes']:>8} 字节  {r['kind']:<6}{r['isbn']}")


def f12_download(keyword: str = "Python") -> None:
    hits = gm.find_by_book_title(keyword)
    print(f"\n[按书名查电子书] 书名包含“{keyword}” -> {len(hits)} 个文件")
    for h in hits:
        print(f"  {h['filename']:<14}{h['bytes']:>8} 字节  {h['title']}")
        res = gm.download(h["filename"])
        print(f"    下载到 {res['dest']}")
        print(f"    校验：下载 {res['downloaded_bytes']} / GridFS {res['gridfs_length']} / "
              f"源文件 {res['source_bytes']} -> {'一致' if res['match'] else '不一致'}")


def f13_files() -> None:
    gm.print_files()


def f14_audit() -> None:
    audit.print_recent(20)
    print("\n[日志集合属性] " + json.dumps(audit.stats(), ensure_ascii=False, default=str))


def f15_overview() -> None:
    print("\n[平台总览] " + json.dumps(sm.overview(), ensure_ascii=False))


ACTIONS = {
    "1": f1_search, "2": f2_tags, "3": f3_title, "4": f4_year_and_check, "5": f5_top_rated,
    "6": f6_category_stats, "7": f7_college_rank, "8": f8_trend, "9": f9_top_books,
    "10": f10_borrow_return, "11": f11_upload, "12": f12_download, "13": f13_files,
    "14": f14_audit, "15": f15_overview,
}


def demo() -> None:
    cfg = get_config()
    print(MENU)
    print(f"[环境] 部署形态={cfg.profile_name}（{cfg.profile_desc}）")
    print(f"[连接] {json.dumps(ping(), ensure_ascii=False, default=str)}")
    for key in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15"):
        print("\n" + "=" * 60 + f"\n>> 菜单项 {key}")
        ACTIONS[key]()


def interactive() -> None:
    print(MENU)
    print(f"[环境] {get_config().profile_name} / {ping()}")
    while True:
        choice = input("\n请选择功能编号（0 退出）：").strip()
        if choice in ("0", "q", "exit"):
            break
        action = ACTIONS.get(choice)
        if not action:
            print("无效编号，请重新输入")
            continue
        try:
            action()
        except Exception as exc:  # noqa: BLE001 —— 菜单程序需要兜底，避免一次异常退出整个会话
            print(f"[错误] {type(exc).__name__}: {exc}")


def main() -> None:
    try:
        if "--demo" in sys.argv:
            demo()
        elif "--choice" in sys.argv:
            idx = sys.argv[sys.argv.index("--choice") + 1]
            ACTIONS[idx]()
        else:
            interactive()
    finally:
        close_all()


if __name__ == "__main__":
    main()
