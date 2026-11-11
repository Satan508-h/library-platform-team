"""把运行实录渲染为终端风格截图，并绘制统计图表（任务七验收材料）。

说明：截图内容全部来自 `records/` 下的真实运行日志、`exports/` 导出结果与
`docker` 实时命令输出，仅做了等宽排版与统一底色的可视化包装，未改写任何数据。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "records"
OUT = ROOT / "docs" / "截图"
OUT.mkdir(parents=True, exist_ok=True)

FONT_CJK = Path(r"C:\Windows\Fonts\simhei.ttf")
FONT_ASCII = Path(r"C:\Windows\Fonts\consola.ttf")
BG = (30, 30, 30)
BAR = (60, 60, 60)
FG = (230, 230, 230)
ACCENT = (120, 200, 255)

idx: list[str] = []
_counter = {"n": 0}


def _font(size: int):
    return ImageFont.truetype(str(FONT_CJK if FONT_CJK.exists() else FONT_ASCII), size)


def render(name: str, title: str, text: str, width: int = 1360, size: int = 19) -> None:
    """渲染终端风格截图"""
    f = _font(size)
    f_small = _font(size - 5)
    tmp = Image.new("RGB", (width, 10), BG)
    d = ImageDraw.Draw(tmp)
    maxw = width - 48
    lines: list[str] = []
    for raw in text.replace("\t", "    ").splitlines() or [""]:
        if raw == "":
            lines.append("")
            continue
        cur = ""
        for ch in raw:
            if d.textlength(cur + ch, font=f) > maxw:
                lines.append(cur)
                cur = "  "
            cur += ch
        lines.append(cur)
    line_h = int(size * 1.55)
    head_h = 58
    height = head_h + 26 + line_h * len(lines) + 24
    img = Image.new("RGB", (width, height), BG)
    dr = ImageDraw.Draw(img)
    # 标题栏
    dr.rectangle([0, 0, width, head_h], fill=BAR)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = 26 + i * 26
        dr.ellipse([cx - 8, head_h // 2 - 8, cx + 8, head_h // 2 + 8], fill=c)
    dr.text((120, 14), title, font=f_small, fill=(210, 210, 210))
    # 正文
    y = head_h + 20
    for ln in lines:
        color = ACCENT if ln.startswith((">", "[", "===")) else FG
        dr.text((24, y), ln, font=f, fill=color)
        y += line_h
    _counter["n"] += 1
    path = OUT / f"{_counter['n']:02d}_{name}.png"
    img.save(path)
    idx.append(f"- `{path.name}` — {title}")


def read(name: str) -> str:
    p = REC / name
    if not p.exists():
        return f"[缺少文件] {name}"
    return p.read_text(encoding="utf-8", errors="replace")


def sh(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                             timeout=30, errors="replace")
        return (out.stdout or "") + (out.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return f"[命令失败] {' '.join(cmd)}: {exc}"


def demo_sections() -> dict[int, str]:
    text = read("task3_3_functions_demo.log")
    parts = re.split(r">> 菜单项 (\d+)", text)
    out: dict[int, str] = {}
    for i in range(1, len(parts) - 1, 2):
        out[int(parts[i])] = parts[i + 1].strip()
    return out


DEMO_TITLES = {
    1: "菜单1 图书检索（类别+价格区间+排序分页）",
    2: "菜单2 标签多选匹配（$all / $in）",
    3: "菜单3 书名模糊检索",
    4: "菜单4 出版年份区间与缺失 tags 核查",
    5: "菜单5 评分 Top10 投影查询",
    6: "菜单6 分类统计聚合与落库",
    7: "菜单7 学院借阅排行（$lookup 多集合）",
    8: "菜单8 按年月借阅趋势",
    9: "菜单9 借阅 Top10 与馆藏位置深投影",
    10: "菜单10 借书 / 还书事务性写操作",
    11: "菜单11 GridFS 上传电子书与封面",
    12: "菜单12 按书名下载并字节级校验",
    13: "菜单13 GridFS 文件清单与块数",
    14: "菜单14 操作日志（capped 集合倒序）",
    15: "菜单15 平台数据总览",
}


def bar_chart(name: str, title: str, labels: list[str], values: list[int],
              color=(120, 200, 255), width: int = 1400, height: int = 560) -> None:
    img = Image.new("RGB", (width, height), (250, 250, 250))
    dr = ImageDraw.Draw(img)
    f = _font(16)
    f2 = _font(13)
    dr.text((30, 18), title, font=_font(20), fill=(30, 30, 30))
    left, top, right, bottom = 70, 70, width - 30, height - 70
    maxv = max(values) if values and max(values) > 0 else 1
    n = len(values)
    slot = (right - left) / n
    bw = max(4, slot * 0.62)
    dr.line([left, bottom, right, bottom], fill=(120, 120, 120), width=1)
    for i, (lb, v) in enumerate(zip(labels, values)):
        x = left + slot * i + (slot - bw) / 2
        h = (bottom - top) * v / maxv
        dr.rectangle([x, bottom - h, x + bw, bottom], fill=color)
        if n <= 14 or i % 3 == 0:
            dr.text((x - 2, bottom + 6), lb, font=f2, fill=(60, 60, 60))
        if n <= 14:
            dr.text((x, bottom - h - 18), str(v), font=f2, fill=(40, 40, 40))
    dr.text((left, top - 34), f"最大值 {maxv}", font=f, fill=(90, 90, 90))
    _counter["n"] += 1
    path = OUT / f"{_counter['n']:02d}_{name}.png"
    img.save(path)
    idx.append(f"- `{path.name}` — {title}")


def hbar_chart(name: str, title: str, labels: list[str], values: list[float],
               width: int = 1200, height: int = 460) -> None:
    img = Image.new("RGB", (width, height), (250, 250, 250))
    dr = ImageDraw.Draw(img)
    f2 = _font(15)
    dr.text((30, 18), title, font=_font(20), fill=(30, 30, 30))
    left, top, right = 190, 70, width - 80
    maxv = max(values) if values else 1
    row = (height - top - 40) / max(1, len(values))
    for i, (lb, v) in enumerate(zip(labels, values)):
        y = top + i * row
        dr.text((30, y + 4), lb, font=f2, fill=(50, 50, 50))
        w = (right - left) * v / maxv
        dr.rectangle([left, y + 2, left + w, y + row - 8], fill=(255, 160, 90))
        dr.text((left + w + 8, y + 4), f"{v:g}", font=f2, fill=(50, 50, 50))
    _counter["n"] += 1
    path = OUT / f"{_counter['n']:02d}_{name}.png"
    img.save(path)
    idx.append(f"- `{path.name}` — {title}")


def main() -> None:
    overview = json.loads((ROOT / "exports" / "overview.json").read_text(encoding="utf-8"))

    # ---------- 环境与工程结构 ----------
    render("docker容器清单", "docker ps — 本项目新建容器（未触碰原有 mongodb 容器）",
           sh(["docker", "ps", "--format",
              "table {{.Names}}\t{{.Status}}\t{{.Ports}}"]))
    tree = sh(["cmd", "/c", "tree", "/f", str(ROOT / "app")])
    render("项目源码目录", "app/ 源码与 scripts/ 脚本清单",
           tree + "\n" + sh(["cmd", "/c", "dir", "/b", str(ROOT / "scripts")])
           + "\n" + sh(["cmd", "/c", "dir", "/b", str(ROOT / "deploy")])
           + "\n" + sh(["cmd", "/c", "dir", "/b", str(ROOT / "data")]))
    render("多形态配置config.json",
           "config/config.json — 三种部署形态的连接串与账号",
           (ROOT / "config" / "config.json").read_text(encoding="utf-8"))

    # ---------- 任务三 ----------
    render("建库建集合与索引", "init_db.py --reset：5 个集合、16 个索引", read("task3_1_init_db.log"))
    render("数据导入校验", "import_data.py：50/30/3000 三表逐项核对", read("task3_2_import_data.log"))
    render("索引优化基准测试", "benchmark_index.py：COLLSCAN→IXSCAN 扫描量与耗时",
           read("index_benchmark.md"))
    render("权限边界验证", "verify_permissions.py：三账号权限矩阵", read("task3_5_permissions.log"))
    render("检索统计记录", "report_queries.py：11 项检索与统计结果条数", read("task3_queries_and_stats.md"))
    render("演示流水清理", "清理演示临时流水，恢复 3000 条基线", read("task3_7_cleanup.log"))

    secs = demo_sections()
    for k in sorted(secs):
        render(f"菜单{k:02d}", DEMO_TITLES.get(k, f"菜单项 {k}"), secs[k])

    # ---------- 任务五 ----------
    render("副本集初始化", "rs.initiate：三节点 librs 主从建立", read("task5_3_rs_status.log"))
    render("副本集建库导入", "副本集形态下重建库与导入数据", read("task5_1_rs_init_db.log")[-2400:])
    render("读取偏好矩阵", "5 种读取偏好实际落点", read("task5_4_read_preference.log"))
    render("故障转移时间线", "stop lib-rs1 → lib-rs2 上位 → 原主回归",
           "\n".join([ln for ln in read("task5_5_failover_timeline.log").splitlines()
                      if "STEP" in ln or "演练开始" in ln or "已停止" in ln]))
    render("故障转移业务影响", "故障转移期间探针统计与写入耗时",
           read("task5_5_failover_summary.md"))
    render("节点增删演练", "addnode 3→4 成员，removenode 回到 3 成员",
           read("task5_7_add_remove_node.log"))

    # ---------- 任务六 ----------
    render("分片集群建库导入", "两分片 + mongos 下的建库、索引与导入",
           read("task6_1_shard_init_db.log")[-2600:] + "\n" + read("task6_2_shard_import.log"))
    render("分片分布与查询路由", "哈希分片分布、定向/跨分片执行阶段与耗时",
           read("task6_3_shard_status.log"))
    render("分片集群权限", "分片形态下三账号权限边界", read("task6_5_shard_permissions.log"))
    render("集群状态sh.status", "sh.status()：分片、集合分片键与块分布", read("task6_4_sh_status.log")[:3000])

    # ---------- 导出与图表 ----------
    files = sh(["cmd", "/c", "dir", "/b", str(ROOT / "exports")])
    render("统计结果导出清单", "exports/ 统计结果文件（CSV + JSON）", files)
    rank = [(r["college"], r["total"]) for r in overview["学院借阅排行"]]
    hbar_chart("学院借阅排行", "各学院借阅总量（多集合 $lookup 聚合）",
               [r[0] for r in rank][:7], [r[1] for r in rank][:7])
    trend = overview["月度趋势"]
    bar_chart("月度借阅趋势", "2023-01—2025-12 借阅总量月度趋势",
              [t["period"][2:] for t in trend], [t["total"] for t in trend])
    rows = []
    for line in (ROOT / "exports" / "category_stats.csv").read_text(
            encoding="utf-8-sig").splitlines()[1:]:
        if line.strip():
            cells = line.split(",")
            rows.append((cells[0], float(cells[3])))
    hbar_chart("分类平均评分", "各类别平均评分（category_stats 落库结果）",
               [r[0] for r in rows], [r[1] for r in rows])

    (OUT / "截图索引.md").write_text(
        "# 验收截图索引（共 %d 张）\n\n- 生成脚本：`scripts/make_screenshots.py`\n"
        "- 数据来源：`records/` 运行日志与 `exports/` 导出结果，未改写数据\n\n%s\n"
        % (_counter["n"], "\n".join(idx)), encoding="utf-8")
    print(f"共生成 {_counter['n']} 张截图 -> {OUT}")


if __name__ == "__main__":
    main()
