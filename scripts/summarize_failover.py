"""汇总故障转移演练记录：时间线关键点 + 探针统计 + 读写偏好落点。"""
from pathlib import Path
import csv, re, collections

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "records"

rows = list(csv.DictReader((REC / "ha_probe.log").open(encoding="utf-8")))
steps = []
for line in (REC / "task5_5_failover_timeline.log").read_text(encoding="utf-8").splitlines():
    if "STEP" in line or "演练开始" in line or "已停止" in line or "完成" in line:
        steps.append(line.strip())

writes = [r for r in rows if r["操作"] == "insert_one"]
fail_w = [r for r in writes if r["结果"] != "成功"]
reads_p = [r for r in rows if r["操作"] == "primary 读 books"]
reads_s = [r for r in rows if r["操作"] == "secondaryPreferred 读 books"]
fail_rp = [r for r in reads_p if r["结果"] != "成功"]
fail_rs = [r for r in reads_s if r["结果"] != "成功"]

def spans(seq):
    """把连续的失败记录压成区间"""
    out, cur = [], None
    for r in seq:
        t = r["时间"]
        if cur is None:
            cur = [t, t, 1, r["备注"] or ""]
        else:
            cur[1] = t; cur[2] += 1
    if cur:
        out.append(cur)
    return out

primaries = collections.OrderedDict()
for r in rows:
    if r["操作"] == "主节点变化":
        primaries.setdefault(r["当前主节点"], r["时间"])

# secondaryPreferred 命中的节点（从备注中解析）
hit = collections.Counter()
for r in reads_s:
    m = re.search(r"(lib-rs\d):\d+\s+返回", r["备注"] or "")
    if m:
        hit[m.group(1)] += 1

dur_fail = None
if fail_w:
    dur_fail = (fail_w[0]["时间"], fail_w[-1]["时间"], len(fail_w))

lines = []
lines.append("# 副本集故障转移演练汇总（任务五-5）\n")
lines.append(f"- 记录文件：`records/task5_5_failover_timeline.log`（编排时间线）、`records/ha_probe.log`（逐 0.5 秒探针）、`records/task5_5_watch.log`（角色轮询）")
lines.append(f"- 探针样本：写入 {len(writes)} 次、primary 读 {len(reads_p)} 次、secondaryPreferred 读 {len(reads_s)} 次\n")

lines.append("## 一、编排时间线（关键节点）\n")
lines.append("| 时刻（宿主本地 UTC+8） | 事件 |\n|---|---|")
for s in steps:
    parts = s.split("  ", 1)
    if len(parts) == 2:
        lines.append(f"| {parts[0][11:]} | {parts[1].replace('|', '/')} |")
    else:
        lines.append(f"| - | {s} |")

lines.append("\n## 二、主节点角色变化（容器内 UTC 时间，+8 小时即本地时间）\n")
lines.append("| 首次出现时刻 | 主节点 |\n|---|---|")
for k, v in primaries.items():
    lines.append(f"| {v} | {k} |")

lines.append("\n## 三、业务影响（探针实测）\n")
lines.append(f"- 写入失败次数：{len(fail_w)} / {len(writes)}")
if dur_fail:
    lines.append(f"- 写入失败区间：{dur_fail[0]} — {dur_fail[1]}（连续 {dur_fail[2]} 次）")
else:
    lines.append("- 写入失败区间：无")
lines.append(f"- primary 读失败次数：{len(fail_rp)} / {len(reads_p)}")
lines.append(f"- secondaryPreferred 读失败次数：{len(fail_rs)} / {len(reads_s)}")
errs = collections.Counter(r["备注"][:70] for r in fail_w + fail_rp + fail_rs if r["备注"])
if errs:
    lines.append("\n失败原因分类：\n")
    lines.append("| 错误摘要 | 次数 |\n|---|---|")
    for k, c in errs.most_common(6):
        lines.append(f"| {k} | {c} |")

lines.append("\n## 四、写入耗时分布（含切换瞬间的重试代价）\n")
lat = sorted(float(r["耗时ms"]) for r in writes)
lines.append(f"- 平均 {sum(lat)/len(lat):.2f} ms，P50 {lat[len(lat)//2]:.2f} ms，P99 {lat[int(len(lat)*0.99)]:.2f} ms，最大 {lat[-1]:.2f} ms")
slow = sorted(writes, key=lambda r: float(r["耗时ms"]), reverse=True)[:6]
lines.append("\n最慢的 6 次写入：\n")
lines.append("| 时刻 | 耗时 ms | 主节点 |\n|---|---|---|")
for r in slow:
    lines.append(f"| {r['时间']} | {r['耗时ms']} | {r['当前主节点']} |")

lines.append("\n## 五、读取偏好落点（secondaryPreferred）\n")
lines.append("| 实际返回节点 | 次数 |\n|---|---|")
for k, c in hit.most_common():
    lines.append(f"| {k} | {c} |")

(REC / "task5_5_failover_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("written", REC / "task5_5_failover_summary.md")
print("\n".join(lines[8:40]))
