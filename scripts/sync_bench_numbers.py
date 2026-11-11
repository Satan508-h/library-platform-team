"""把文档与答辩材料中的索引基准数字同步为最新一次实测结果。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAIRS = [
    ("3002", "3000"),
    ("1.966", "1.949"),
    ("0.814", "0.850"),
    ("1.996", "2.096"),
    ("0.824", "0.866"),
    ("42.083", "40.625"),
    ("0.904", "0.831"),
    ("46.55", "48.89"),
    ("0.92x", "0.94x"),
    ('["流水按读者倒序（3000 条）", "COLLSCAN / 3000 / 1.949 ms", "IXSCAN / 10 / 0.850 ms", "2.42x"]',
     '["流水按读者倒序（3000 条）", "COLLSCAN / 3000 / 1.949 ms", "IXSCAN / 10 / 0.850 ms", "2.29x"]'),
    ("2.42 倍", "2.29 倍"),
    ("扫描文档数从 3002", "扫描文档数从 3000"),
]

for name in ("scripts/build_docx.py", "docs/答辩材料_8分钟.md"):
    p = ROOT / name
    text = p.read_text(encoding="utf-8")
    for old, new in PAIRS:
        text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")
    print(f"已同步 {name}")
