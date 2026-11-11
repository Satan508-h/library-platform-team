"""生成《智慧图书馆数字资源平台》项目文档（Word，7 章，10—14 页）。"""
import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
SHOT = ROOT / "docs" / "截图"
FIG = ROOT / "docs" / "图"
OUT = ROOT / "docs" / "智慧图书馆数字资源平台_项目文档.docx"

CJK_BODY, CJK_HEI = "宋体", "黑体"
ASCII = "Times New Roman"
BODY_PT, SMALL_PT = 10.5, 9

doc = Document()


# ---------------- 基础排版工具 ----------------
def _cn(run, cjk: str, size: float, bold: bool = False) -> None:
    run.font.name = ASCII
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), ASCII)
    rfonts.set(qn("w:hAnsi"), ASCII)
    rfonts.set(qn("w:eastAsia"), cjk)


def setup_styles() -> None:
    normal = doc.styles["Normal"]
    normal.font.name = ASCII
    normal.font.size = Pt(BODY_PT)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), CJK_BODY)
    pf = normal.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.first_line_indent = Pt(BODY_PT * 2)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    specs = {"Heading 1": (12, 12, 6), "Heading 2": (10.5, 6, 3), "Heading 3": (10.5, 6, 3)}
    for name, (size, before, after) in specs.items():
        st = doc.styles[name]
        st.font.name = ASCII
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = RGBColor(0, 0, 0)
        st.element.rPr.rFonts.set(qn("w:eastAsia"), CJK_HEI)
        pf = st.paragraph_format
        pf.space_before = Pt(before)
        pf.space_after = Pt(after)
        pf.first_line_indent = Pt(0)
        pf.keep_with_next = True


def body(text: str, indent: bool = True) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(BODY_PT * 2) if indent else Pt(0)
    r = p.add_run(text)
    _cn(r, CJK_BODY, BODY_PT)


def h1(text: str, page_break: bool = False) -> None:
    if page_break:
        brk = doc.add_paragraph()
        brk.paragraph_format.space_after = Pt(0)
        brk.paragraph_format.first_line_indent = Pt(0)
        brk.add_run().add_break(WD_BREAK.PAGE)
    p = doc.add_paragraph(style="Heading 1")
    r = p.add_run(text)
    _cn(r, CJK_HEI, 12, True)


def h2(text: str) -> None:
    p = doc.add_paragraph(style="Heading 2")
    r = p.add_run(text)
    _cn(r, CJK_HEI, BODY_PT, True)


def h3(text: str) -> None:
    p = doc.add_paragraph(style="Heading 3")
    r = p.add_run(text)
    _cn(r, CJK_HEI, BODY_PT, True)


def caption(text: str, before: int = 4, after: int = 4) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    _cn(r, CJK_HEI, SMALL_PT)


def _border(cell, edge: str, sz: int = 8) -> None:
    tcpr = cell._element.get_or_add_tcPr()
    borders = tcpr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tcpr.append(borders)
    el = OxmlElement(f"w:{edge}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(sz))
    el.set(qn("w:color"), "000000")
    borders.append(el)


def _no_table_borders(table) -> None:
    tblpr = table._element.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        borders.append(el)
    tblpr.append(borders)


def table(cap: str, header: list[str], rows: list[list[str]], widths: list[float],
          aligns: list[str] | None = None) -> None:
    caption(cap)
    t = doc.add_table(rows=1, cols=len(header))
    t.autofit = False
    _no_table_borders(t)
    tblpr = t._element.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblpr.append(layout)
    aligns = aligns or ["center"] + ["left"] * (len(header) - 1)

    def fill(row, values, bold=False, head=False):
        for i, (cell, val) in enumerate(zip(row.cells, values)):
            cell.width = Cm(widths[i])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = {"center": WD_ALIGN_PARAGRAPH.CENTER,
                           "left": WD_ALIGN_PARAGRAPH.LEFT,
                           "right": WD_ALIGN_PARAGRAPH.RIGHT}[aligns[i]]
            p.paragraph_format.first_line_indent = Pt(0)
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            r = p.add_run(val)
            _cn(r, CJK_BODY, SMALL_PT, bold)
            if head:
                _border(cell, "bottom", 4)

    hdr = t.rows[0]
    fill(hdr, header, bold=True, head=True)
    trpr = hdr._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trpr.append(el)
    for vals in rows:
        row = t.add_row()
        trpr = row._tr.get_or_add_trPr()
        el = OxmlElement("w:cantSplit")
        el.set(qn("w:val"), "true")
        trpr.append(el)
        fill(row, vals)
    # 表格上下框线
    for cell in t.rows[0].cells:
        _border(cell, "top", 8)
    for cell in t.rows[-1].cells:
        _border(cell, "bottom", 8)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def figure(name: str, cap: str, width: float = 11.5) -> None:
    path = SHOT / name
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Cm(width))
    caption(cap)


def _field(paragraph, code: str, hint: str) -> None:
    r1 = paragraph.add_run()
    b = OxmlElement("w:fldChar")
    b.set(qn("w:fldCharType"), "begin")
    r1._r.append(b)
    r2 = paragraph.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = code
    r2._r.append(it)
    r3 = paragraph.add_run()
    s = OxmlElement("w:fldChar")
    s.set(qn("w:fldCharType"), "separate")
    r3._r.append(s)
    r4 = paragraph.add_run(hint)
    _cn(r4, CJK_BODY, SMALL_PT)
    r5 = paragraph.add_run()
    e = OxmlElement("w:fldChar")
    e.set(qn("w:fldCharType"), "end")
    r5._r.append(e)


# ---------------- 结构图 ----------------
def draw_er() -> Path:
    from PIL import Image, ImageDraw, ImageFont

    FIG.mkdir(parents=True, exist_ok=True)
    W, H = 1500, 760
    img = Image.new("RGB", (W, H), (255, 255, 255))
    dr = ImageDraw.Draw(img)
    font = ImageFont.truetype(r"C:\Windows\Fonts\simhei.ttf", 22)
    small = ImageFont.truetype(r"C:\Windows\Fonts\simhei.ttf", 18)
    boxes = {
        "books": (40, 120, 400, 340),
        "readers": (40, 420, 400, 620),
        "borrow_logs": (560, 250, 980, 470),
        "category_stats": (1140, 90, 1460, 280),
        "audit_logs": (1140, 330, 1460, 520),
        "fs.files / fs.chunks": (560, 560, 980, 720),
    }
    texts = {
        "books": ["books（图书）", "isbn / title / author", "category / price / rating",
                  "stock / tags[ ] / location{ }"],
        "readers": ["readers（读者）", "card_no / name / college", "level / fav_categories[ ]"],
        "borrow_logs": ["borrow_logs（借阅流水，分片集合）", "reader_card / book_isbn",
                        "borrow_date / return_date / status", "索引：读者+时间、图书+时间、时间、状态"],
        "category_stats": ["category_stats（统计结果）", "category / book_count",
                           "avg_price / avg_rating"],
        "audit_logs": ["audit_logs（capped 16MB/10000）", "ts / action / target / result"],
        "fs.files / fs.chunks": ["GridFS：fs.files + fs.chunks", "电子书 PDF / 封面 PNG",
                                 "元数据 isbn、kind、upload_date"],
    }
    for key, (x0, y0, x1, y1) in boxes.items():
        dr.rounded_rectangle([x0, y0, x1, y1], radius=10, outline=(60, 60, 60), width=2,
                             fill=(246, 249, 252))
        y = y0 + 14
        for i, line in enumerate(texts[key]):
            dr.text((x0 + 16, y), line, font=font if i == 0 else small,
                    fill=(20, 20, 20) if i == 0 else (70, 70, 70))
            y += 34 if i == 0 else 30

    def arrow(p1, p2, label="", off=(0, 0)):
        dr.line([p1, p2], fill=(150, 60, 60), width=2)
        dr.text(((p1[0] + p2[0]) // 2 + off[0], (p1[1] + p2[1]) // 2 + off[1]), label,
                font=small, fill=(150, 60, 60))

    arrow((400, 230), (560, 300), "reader_card ↔ card_no", (0, -26))
    arrow((400, 470), (560, 400), "book_isbn ↔ isbn", (-40, 30))
    arrow((980, 330), (1140, 190), "聚合结果落库", (0, -24))
    arrow((850, 470), (850, 560), "同一库、不同用途", (10, -18))
    arrow((400, 300), (560, 240), "分类汇总", (-10, -26))
    path = FIG / "图3-1_集合结构与关系.png"
    img.save(path)
    return path


# ---------------- 封面 / 目录 ----------------
def cover() -> None:
    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    _cn(p.add_run("智慧图书馆数字资源平台"), CJK_HEI, 26, True)
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.first_line_indent = Pt(0)
    _cn(p2.add_run("——基于 MongoDB 的数据建模、应用实现与高可用架构演进"), CJK_HEI, 15, True)

    for _ in range(2):
        doc.add_paragraph()
    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.paragraph_format.first_line_indent = Pt(0)
    _cn(p3.add_run("《NoSQL数据库技术与应用（第2版）》期末项目文档"), "楷体", 12)

    for _ in range(6):
        doc.add_paragraph()
    info = [("姓　　名：", "何铭轩"), ("学　　号：", "＿＿＿＿＿＿＿＿"),
            ("专业班级：", "数据科学与大数据技术"), ("指导教师：", "＿＿＿＿＿＿＿＿"),
            ("完成日期：", "2026 年 11 月 11 日")]
    for k, v in info:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Pt(0)
        _cn(p.add_run(k + v), "楷体", 12)


def toc() -> None:
    doc.add_section(WD_SECTION.NEW_PAGE)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_after = Pt(12)
    _cn(p.add_run("目　　录"), CJK_HEI, 15, True)
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    _field(p, 'TOC \\o "1-2" \\h \\z \\u', "打开文档后按 Ctrl+A 再按 F9 即可生成目录页码")


def body_section() -> None:
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    pgnum = OxmlElement("w:pgNumType")
    pgnum.set(qn("w:start"), "1")
    sec._sectPr.append(pgnum)
    sec.footer.is_linked_to_previous = False
    p = sec.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    _field(p, "PAGE", "1")


def page_setup() -> None:
    for sec in doc.sections:
        sec.page_width = Cm(21)
        sec.page_height = Cm(29.7)
        sec.top_margin = Cm(2.5)
        sec.bottom_margin = Cm(2.5)
        sec.left_margin = Cm(2.5)
        sec.right_margin = Cm(2.5)


# ---------------- 正文 ----------------
def ch1() -> None:
    h1("1　项目概述", page_break=False)
    h2("1.1　项目背景与目标")
    body("校级图书馆希望把“馆藏书目、读者档案、借阅流水、电子书与封面文件”统一到一个平台上，"
         "既要支持馆员按类别、价格区间、标签、出版年份做多维检索，也要支持按学院、按年月做借阅统计，"
         "并为后续的数据增长留出可扩展空间。本项目以 MongoDB 为唯一数据底座，完成从技术选型、数据建模、"
         "单机实现到副本集高可用与分片扩展的完整链路，全部在本机 Docker 环境中真实跑通并留档。")
    body("交付目标是四项可验证的能力：其一，数据模型能同时容纳结构规整的书目与结构多变的借阅流水；"
         "其二，检索与聚合在 50 本图书、30 名读者、3000 条借阅流水的真实数据上结果正确、可复现；"
         "其三，常见故障（主节点宕机）不会造成业务写入丢失；其四，数据量增长时能通过分片平滑扩容。")

    h2("1.2　交付范围与运行环境")
    body("为保证不干扰本机已有的 MongoDB 容器与两套业务容器，本项目所有实例均新建容器、"
         "统一接入新建的 Docker 网络 libnet，端口使用空闲段并只绑定 127.0.0.1。"
         "三种部署形态通过同一个配置项 WISELIB_PROFILE 切换，应用代码不做任何改动。")
    table("表1-1　三种部署形态的容器与端口规划",
          ["部署形态", "容器名", "宿主机端口", "关键参数"],
          [["单机", "lib-mongo-single", "127.0.0.1:27018", "--auth --directoryperdb"],
           ["副本集", "lib-rs1 / lib-rs2 / lib-rs3", "27101 / 27102 / 27103",
            "rs=librs，keyFile 认证，priority 2:1:1"],
           ["副本集扩容", "lib-rs4（演练用，已停机）", "27104", "priority=0，仅参与复制与投票"],
           ["分片集群", "lib-cfg / lib-shard1 / lib-shard2 / lib-mongos",
            "27201 / 27301 / 27302 / 27030",
            "configsvr 副本集 + 2 分片副本集 + mongos"]],
          widths=[3.0, 4.6, 4.4, 4.0], aligns=["center", "left", "center", "left"])
    body("应用侧共 16 个 Python 源文件，分三层：配置与连接层（config.py、db.py、audit.py）、"
         "业务层（book_manager、reader_manager、borrow_manager、stats_manager、gridfs_manager）、"
         "入口与验证层（init_db.py、import_data.py、main.py、benchmark_index.py、"
         "verify_permissions.py、report_queries.py、ha_tools.py、shard_check.py）。"
         "数据目录、账号与端口全部写在 config/config.json 中，换形态只换一个 profile。")


def ch2() -> None:
    h1("2　技术选型论证")
    h2("2.1　选型约束来自哪里")
    body("选型不是先选数据库再找场景，而是先看清三类约束。第一是数据形态：书目里有标签数组、"
         "馆藏位置这样的嵌套结构，也有 tags、ebook_name 这类在真实数据中会整段缺失的字段；"
         "借阅流水是典型的时序数据，只追加、按读者与时间反复查询；操作日志只需要保留最近若干条。"
         "第二是访问模式：检索以“类别 + 价格区间 + 标签 + 年份”的组合过滤为主，统计以"
         "“按学院、按年月”的分组聚合为主，写操作集中在借还与库存扣减，必须保证不丢。"
         "第三是环境约束：只有一台开发机、Docker 可用、可容纳 3 至 5 个容器，且不允许影响已有容器。")
    body("把这三类约束合起来看，需要的不是一个“最快”的数据库，而是一个能在同一份数据上同时满足"
         "灵活结构、多维索引、聚合分析和水平扩展的存储。关系型数据库的前两类需求要靠宽表和多次 join 完成，"
         "键值存储则完全不支持范围与多条件检索，这是本项目选型的出发点。")

    h2("2.2　候选方案对比")
    table("表2-1　四种候选存储在图书馆场景下的对比",
          ["对比维度", "MongoDB（文档型）", "MySQL（关系型）", "Redis（键值）", "HBase（宽列）"],
          [["书目嵌套结构（location、tags）", "原生支持文档嵌套与数组", "需拆表或用 JSON 列，查询受限",
            "只能整体存取，无法按字段过滤", "列族模型，需自行设计扁平结构"],
           ["多维组合检索", "复合索引、数组索引、文本索引齐备", "复合索引成熟，但数组与文本需额外方案",
            "仅支持键与前缀匹配", "按行键设计，非主键字段过滤代价高"],
           ["分组统计", "聚合管道 $group/$lookup/$unwind", "GROUP BY + JOIN，SQL 成熟",
            "不适用", "需 MR 或 Phoenix 辅助"],
           ["水平扩展", "原生分片，按分片键自动均衡", "分库分表需中间件", "Cluster 分槽", "原生 Region 分裂"],
           ["一致性取舍", "可按读写关注点逐场景调节", "强一致为主，跨库事务成本高",
            "异步复制，可能丢数据", "强一致写入，读需自己权衡"],
           ["本机可落地性", "单容器即可起，副本集/分片均可容器化", "可落地，但多表 join 建模成本高",
            "可落地，但无法承担主存储", "依赖 Hadoop 生态，单机部署成本高"],
           ["本项目结论", "选用", "不选（结构僵化、扩展需中间件）", "不选（不作主存）", "不选（过重）"]],
          widths=[3.6, 3.4, 3.4, 3.0, 3.6],
          aligns=["left", "left", "left", "left", "left"])

    body("表2-1 的结论并不是“MongoDB 全面更好”，而是在本项目这组约束下的权衡结果："
         "馆藏结构不规整，关系型要么用大量可空列，要么把整个结构塞进 JSON 列而丧失索引能力；"
         "而 MongoDB 的数组索引恰好能直接服务 tags 的 $all / $in 查询，聚合管道也能一次完成"
         "$lookup + $group 的跨集合统计。Redis 与 HBase 的问题不在性能，而在于前者不能当主存、"
         "后者在本机环境下运维成本远超收益。")

    h2("2.3　CAP 取舍落在哪两个场景")
    body("CAP 不是给整个系统贴一个标签，而是要在具体读写路径上分别回答。本项目真正会触发取舍的只有两个场景。")
    table("表2-2　两个核心场景的 CAP 与实现手段",
          ["场景", "一致性要求", "可用性要求", "取舍", "代码中的落地"],
          [["馆藏检索、评分榜、趋势统计", "允许秒级陈旧，读到稍旧数据可接受",
            "要求高可用，节点故障时仍应可读", "AP（向可用性倾斜）",
            "读偏好 secondaryPreferred，把读分散到从节点"],
           ["借阅流水写入、还书与库存扣减", "不允许丢写，提交后必须可读",
            "短暂不可写可容忍（秒级）", "CP（向一致性倾斜）",
            "写关注 majority，读偏好 primary，关键更新用单文档原子操作"]],
          widths=[3.8, 3.9, 3.6, 3.0, 4.4],
          aligns=["left", "left", "left", "center", "left"])
    body("这样的结果是：同一套副本集，检索走从节点、借还走主节点且要求多数派确认。"
         "故障转移演练中 179 次写入零失败，恰恰说明“写走 majority”并没有把可用性牺牲到不可接受的程度——"
         "因为驱动会自动重试，切换窗口被压缩在对业务无感的两秒内。")

    h2("2.4　BASE 的可接受与不可接受清单")
    table("表2-3　最终一致性的边界划分",
          ["可接受最终一致（允许短暂陈旧）", "不可接受（必须强一致）"],
          [["分类藏书量与平均评分统计（可重算）", "借阅流水的新增（丢失即账实不符）"],
           ["学院借阅排行与借阅 Top10", "还书后的状态与 return_date 更新"],
           ["按年月借阅趋势", "库存 stock 的扣减与回补"],
           ["评分排序榜、推荐位", "audit_logs 操作留痕（审计要求完整）"]],
          widths=[7.5, 7.5], aligns=["left", "left"])
    body("清单的划分依据是“能否重算”与“是否留痕”。统计类结果全部可由原始流水重算，"
         "因此允许短暂不一致；而借还流水、库存与审计日志一旦丢失无法事后补出，必须走多数派写。"
         "实践中这条边界直接决定了两类接口的读写参数，而不是靠人工约定。")

    h2("2.5　一句话结论与两个风险")
    body("结论：在“结构不规整、检索维度多、需要水平扩展、且只有单机 Docker 环境”的条件下，"
         "MongoDB 是能够在三个部署形态之间平滑演进、且不增加应用改造量的选择；"
         "风险不在功能，而在运维与设计细节，因此把它们提前写进方案。")
    body("风险一：架构复杂度上升。副本集与分片把“一个数据库”变成了多进程、多端口、多角色的集群，"
         "运维成本随之上升。应对是把拓扑、端口、账号、启动参数全部固化在 compose 文件与配置项中，"
         "并用 ha_tools 的 status/watch 一键核对角色，避免人工记忆。")
    body("风险二：分片键一旦选错，代价极高。分片键在建集合时确定，之后几乎无法更改，"
         "选到低基数或单调递增的键会造成热点与不可分裂的大块。应对是先做方案对比（见 6.4 节），"
         "选哈希分片键保证写入均匀，并保留“必要时重建集合并迁移”的退路。")

    h2("2.6　面向非技术决策者的说明")
    body("这套系统选用的是一种“按需装盒”的数据库：书目、读者、借阅记录各自成盒，盒内字段可增可减，"
         "不必为了一个新字段重建整张表；查书时可以同时按类别、价格、标签、年份筛选，统计可以按学院和月份自动汇总。"
         "当访问量增长时，只需增加机器并把数据自动分摊，业务代码不用改。代价是运维比单机数据库复杂，"
         "需要专人看管集群状态，因此建议在数据量与并发真正上升后再启用分片，前期用三节点副本集即可。")


def ch3() -> None:
    h1("3　数据模型设计")
    h2("3.1　集合划分与逻辑结构")
    body("全库共 6 个集合：books（图书）、readers（读者）、borrow_logs（借阅流水）、"
         "category_stats（分类统计结果）、audit_logs（操作日志），以及 GridFS 的两个内部集合"
         "fs.files 与 fs.chunks。划分原则是“按写读特征分，而不是按业务部门分”："
         "高频只追加的流水单独成集合，可重算的统计结果单独落库，只追加的日志用定长集合封顶。")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(draw_er()), width=Cm(14.6))
    caption("图3-1　集合结构与关联字段示意")

    h2("3.2　字段与 BSON 类型")
    table("表3-1　books 集合字段设计",
          ["字段", "BSON 类型", "说明", "是否必需"],
          [["isbn", "String", "唯一标识，建唯一索引 uk_isbn", "必填"],
           ["title / author / publisher", "String", "书名、作者、出版社", "必填"],
           ["publish_date", "Date", "出版日期，支撑年份区间与按月聚合", "必填"],
           ["category", "String", "六个类别之一，统计与检索主维度", "必填"],
           ["price", "Double", "价格，用于区间筛选与平均价统计", "必填"],
           ["stock", "Int32", "在架库存，借还时 $inc 增减", "必填"],
           ["rating", "Double", "评分 0—5，用于倒序排行", "必填"],
           ["tags", "Array<String>", "标签数组，支持 $all/$in 多选", "可为空/缺失 4 条"],
           ["location", "Embedded Document", "馆藏位置：floor / shelf / copies", "必填"],
           ["borrow_count", "Int32", "历史借阅次数（字段值，便于排序）", "必填"],
           ["ebook_name / cover_name", "String", "对应 GridFS 文件名", "可为空 47 条"]],
          widths=[4.4, 3.8, 7.0, 3.2], aligns=["left", "left", "left", "center"])

    table("表3-2　borrow_logs 集合字段设计",
          ["字段", "BSON 类型", "说明"],
          [["reader_card", "String", "读者卡号，与 readers.card_no 关联，分片键"],
           ["book_isbn", "String", "图书 ISBN，与 books.isbn 关联"],
           ["borrow_date", "Date", "借出时间，倒序索引与按月聚合依据"],
           ["return_date", "Date | null", "归还时间，未归还为缺失（858 条）"],
           ["status", "String", "借出 / 已归还 / 逾期"],
           ["duration_days", "Int32", "借阅时长（天）"]],
          widths=[4.2, 3.6, 9.0], aligns=["left", "left", "left"])
    figure("compass_06_图书文档与嵌套结构.png",
           "图3-2　books 文档实际形态（Compass 文档视图：location 嵌套、tags 数组、BSON Date）", 14.0)

    h2("3.3　关键设计决策与理由")
    body("设计论证不写“因为 MongoDB 支持”，而要写清“还有哪些选项、为什么没选”。以下七条是本模型里"
         "最容易选错的位置。")
    body("第一，price 用 Double 而非 Decimal128。本项目的价格只参与区间筛选与平均价统计，不涉及跨表对账，"
         "而 Decimal128 的比较与索引开销更大，Python 侧还需额外的十进制转换。若平台日后接入支付与结算，"
         "应改为 Decimal128 并在应用层统一量化，这一点已在附录改进项中记录。")
    body("第二，日期一律用 BSON Date 而非字符串。趋势统计需要 $year、$month 两个聚合操作符，范围查询需要"
         "索引有序比较；若存成字符串，混合格式（2023-01-31 与 2023/1/31）会让排序与区间判断同时失效。"
         "导入时把 ISO8601 字符串统一转成 datetime，是保证类型正确的关键一步。")
    body("第三，stock 用 Int32 而非 Double。库存是计数语义，$inc 之后若为浮点会留下 3.0 与 3 比较歧义，"
         "也会让“库存为 0”的判断出现精度陷阱。金额用浮点、计数用整数，这条边界在后续统计里同样适用。")
    body("第四，location 选择嵌套而不是拆成独立集合。馆藏位置随书而定、不会独立变化，嵌套后一次查询即可"
         "返回“在哪一层哪个书架、有几本复本”，且位置调整是单文档原子更新，无需跨集合事务。"
         "只有当需要按书架做盘点、或一个 ISBN 对应多个物理馆藏点并各自独立借还时，才应拆成 collection_units 集合，"
         "那属于本项目的扩展方向而非当前需求。")
    body("第五，audit_logs 用 capped 集合（16 MB、最多 10000 条）。它的特征是只追加、只保留最近若干条、"
         "永远按插入顺序读，正好对应 capped 的语义：写入是顺序追加、空间预分配、无需额外索引，"
         "读用 $natural 倒序即可。代价是不能删除单条、不能分片，因此审计日志只保留近期窗口，"
         "长期归档需要另设通道。")
    body("第六，borrow_logs 必须是普通集合而不是 capped。它需要按读者、按图书、按时间、按状态四类索引，"
         "还书时要更新 return_date 与 status，数据量增长后还要按读者卡号分片——capped 集合既不支持更新，"
         "也不支持分片，三个需求一个都满足不了。")
    body("第七，tags 用数组而非独立的标签表。$all（同时包含）与 $in（包含任一）可以直接命中多值索引，"
         "省掉一次 join；代价是数组索引会随标签数量膨胀，若单书标签超过数十个或需要标签自身属性（如权重、层级），"
         "再拆成 book_tags 关联集合更合适。本项目 50 本书、每本 2—3 个标签，数组方案明显更划算。")

    h2("3.4　索引清单与设计依据")
    table("表3-3　16 个索引及其服务对象",
          ["集合", "索引名", "键", "类型", "服务的查询"],
          [["books", "uk_isbn", "{isbn:1}", "唯一", "按 ISBN 精确取书、导入去重"],
           ["books", "idx_category_price", "{category:1, price:1}", "复合", "类别 + 价格区间组合筛选"],
           ["books", "idx_tags", "{tags:1}", "多值", "$all / $in 标签匹配"],
           ["books", "idx_rating / idx_publish_date", "{rating:-1} / {publish_date:1}", "单列", "评分 Top10、年份区间"],
           ["books", "idx_title / idx_text_search", "标题单列索引、title+author 文本索引", "单列/文本", "书名检索、全文检索"],
           ["readers", "uk_card_no", "{card_no:1}", "唯一", "卡号查读者、$lookup 关联"],
           ["readers", "idx_college / idx_level", "{college:1} / {level:1}", "单列", "学院、等级筛选"],
           ["borrow_logs", "idx_reader_date", "{reader_card:1, borrow_date:-1}", "复合", "某读者流水倒序"],
           ["borrow_logs", "idx_book_date", "{book_isbn:1, borrow_date:-1}", "复合", "某书的借阅历史"],
           ["borrow_logs", "idx_borrow_date / idx_status", "{borrow_date:-1} / {status:1}", "单列", "时间范围、趋势与状态过滤"],
           ["category_stats", "uk_stats_category / idx_book_count", "类别唯一索引、藏书量倒序", "唯一/单列", "统计结果回查与排序"]],
          widths=[3.0, 4.2, 6.0, 2.4, 4.9], aligns=["left", "left", "left", "center", "left"])
    body("索引设计遵循三条规则：等值在前、范围在后（idx_category_price 把 category 放前、price 放后）；"
         "排序字段与过滤字段合并在同一复合索引中（idx_reader_date 让“按读者过滤 + 按时间倒序”一次走完，"
         "避免内存排序）；唯一约束优先用唯一索引而不是应用层查重（uk_isbn、uk_card_no）。"
         "文本索引用 default_language=none，避免中文被英文停用词与词干规则干扰。")
    body("实测结果是：借阅流水按读者查询的扫描文档数从 3000 降到 10，200 次平均耗时 1.949 ms 降到 0.850 ms；"
         "在 20 万条放大集合上，同一类查询从 40.625 ms 降到 0.831 ms，提速 48.89 倍（详见 4.4 节）。")


def ch4() -> None:
    h1("4　功能实现")
    h2("4.1　程序结构与运行方式")
    table("表4-1　源码模块与职责",
          ["模块", "职责"],
          [["config.py / db.py", "多形态配置加载；统一客户端（tz_aware=True）、uri_for 与 admin 客户端"],
           ["audit.py", "写操作日志到 capped 集合，按 $natural 倒序读取，统计各动作次数"],
           ["book / reader / borrow_manager", "图书检索、读者查询、借书还书与流水查询"],
           ["stats_manager", "分类统计、学院排行（$lookup）、月度趋势、借阅 Top10"],
           ["gridfs_manager", "电子书与封面上传、按书名下载、字节校验、文件清单"],
           ["init_db / import_data", "建集合与 16 个索引；三表 JSON 按 BSON 类型导入并核对"],
           ["main.py", "15 项功能菜单，支持 --demo 一次性演示与 --choice N 单项执行"],
           ["benchmark / verify_permissions", "explain(executionStats) 索引对比；三账号权限矩阵验证"],
           ["ha_tools / shard_check", "副本集状态下探、故障演练编排；分片分布与查询路由对比"]],
          widths=[5.4, 11.4], aligns=["left", "left"])
    body("运行入口只有一条命令：python app/main.py --demo，等价于依次执行菜单 1 至 15。"
         "所有脚本都不硬编码绝对路径，配置文件路径由文件位置推导，因此同一份代码可以在宿主机（单机形态）"
         "与容器内（副本集、分片形态）运行。")

    h2("4.2　检索功能")
    body("菜单 1 至 5 覆盖五类检索：类别 + 价格区间（带分页与排序，命中 8 条）；标签 $all 与 $in（1 条与 7 条）；"
         "书名正则模糊（Python 命中 2 条）；出版年份区间（2020—2023 命中 9 条）；缺失 tags 的存在性核查（4 条）。"
         "这里刻意保留了“数据质量核查”这一类查询：真实馆藏数据里 tags、ebook_name、email 都有缺失，"
         "用 $exists:false 精确找出缺口，比在应用层遍历判断更省资源，也为后续补数据提供清单。")
    figure("compass_04_逾期状态过滤429条.png",
           "图4-1　按状态过滤逾期流水（Compass 过滤条件与命中条数 429）", 14.0)

    h2("4.3　统计聚合")
    body("菜单 6 至 9 覆盖四类统计：分类藏书量/平均价格/平均评分并落库 category_stats；学院借阅排行（用 $lookup "
         "把流水与读者档案关联后按学院分组）；按年月借阅趋势（$year/$month 分组，37 个月合计 3000 次）；"
         "借阅 Top10 并用深投影带出馆藏位置。学院排行前五为经济管理学院 500 次、计算机学院 500 次、"
         "历史文化学院 400 次、外国语学院 400 次、文学院 400 次，与流水实数一致。")
    body("借阅 Top10 用图书字段 borrow_count 排序，同时用流水实数做交叉校验：字段值前三是高等数学（上册）312 次、"
         "线性代数（第6版）287 次、新概念英语（第2册）265 次；流水实数只有 60 余次。"
         "这个差异不是错误，而是源数据中 borrow_count 为历史累计值、流水只覆盖 2023—2025 三年，"
         "文档中保留两种口径并说明来源，避免下游把字段值当成“近三年借阅量”使用。")

    h2("4.4　索引优化与实测")
    table("表4-2　建索引前后扫描量与耗时对比",
          ["查询场景", "前：方式/扫描文档/耗时", "后：方式/扫描文档/耗时", "提速"],
          [["books 类别 + 价格（50 条）", "COLLSCAN / 50 / 0.798 ms", "IXSCAN / 6 / 0.864 ms", "0.94x（噪声）"],
           ["流水按读者倒序（3000 条）", "COLLSCAN / 3000 / 1.949 ms", "IXSCAN / 10 / 0.850 ms", "2.29x"],
           ["流水时间范围（3000 条）", "COLLSCAN / 3000 / 2.096 ms", "IXSCAN / 10 / 0.866 ms", "2.42x"],
           ["流水按读者（20 万条放大）", "COLLSCAN / 200000 / 40.625 ms", "IXSCAN / 10 / 0.831 ms", "48.89x"]],
          widths=[5.2, 4.6, 4.6, 3.0], aligns=["left", "center", "center", "center"])
    body("小集合上的耗时差异不可信：50 条与 3000 条的数据全部在内存中，绝对耗时是亚毫秒级，"
         "0.94x 的“变慢”纯属测量噪声。真正有说服力的是扫描文档数（50→6、3000→10）与放大实验的 48.89 倍，"
         "因此把结论写在扫描量上，而不是写在一个不可复现的毫秒数上。这也解释了为什么基准测试要另建 20 万条的"
         "bench_borrow：只有数据量足够，索引收益才从噪声里显现。")
    figure("compass_03_借阅流水索引.png",
           "图4-2　borrow_logs 的 5 个索引（Compass 索引页，含 COMPOUND 与 UNIQUE 标记）", 14.0)

    h2("4.5　权限控制")
    body("三个账号都建在 admin 库：lib_admin（root）、lib_rw（readWrite@library）、lib_ro（read@library）。"
         "验证脚本对每个账号逐一尝试 7 类操作，结果为：只读账号的插入、更新、删除、写日志、serverStatus、"
         "createUser 全部被拒（错误码 13，Unauthorized）；读写账号写操作与聚合查询通过，serverStatus 与"
         "createUser 被拒；管理账号全部通过。结论是权限边界按“只读—读写—管理”三层收口，"
         "业务进程不需要 root 权限。")
    body("这里有一个容易踩的坑：listDatabases 对普通账号也是允许的，用它区分权限会得出错误结论；"
         "必须改用 serverStatus（需要 clusterMonitor 角色）才能暴露差异。这一点在文档中保留下来，"
         "是因为它决定了权限验证脚本是否可信。")


def ch5() -> None:
    h1("5　文件存储")
    h2("5.1　为什么用 GridFS 而不是直接存字段")
    body("电子书 PDF 与封面 PNG 属于二进制内容，直接放进 BSON 文档会遇到三个问题：单个文档上限 16 MB，"
         "超过即写入失败；文档整体读写会把整个文件载入内存，几 MB 的文件并发上传很容易把应用内存打满；"
         "文件内容与元数据混在一起后，按书名检索会连带把二进制读出来。GridFS 把文件切成 255 KB 的 chunk"
         "存入 fs.chunks，元数据（文件名、长度、上传时间、ISBN、类型）存入 fs.files，"
         "既能流式读写，也能用普通查询按元数据检索。")
    h2("5.2　上传、下载与一致性校验")
    table("表5-1　GridFS 中的 6 个文件",
          ["文件名", "字节数", "块数", "关联 ISBN", "类型"],
          [["ebook_1.pdf", "39837", "1", "9787115428028", "电子书"],
           ["ebook_2.pdf", "38524", "1", "9787121362726", "电子书"],
           ["ebook_3.pdf", "37004", "1", "9787115546081", "电子书"],
           ["cover_1.png", "23611", "1", "9787115428028", "封面"],
           ["cover_2.png", "26053", "1", "9787121362726", "封面"],
           ["cover_3.png", "15171", "1", "9787115546081", "封面"]],
          widths=[4.4, 3.2, 2.4, 4.4, 3.0],
          aligns=["left", "right", "center", "center", "center"])
    body("每个文件只有 1 个 chunk，因为大小都在 40 KB 以下，不足一个 255 KB 的块。"
         "上传时把 ISBN 与类型写入 metadata，下载时先按书名查出文件，再按 GridFS 记录的 length 逐块写出，"
         "最后做三方比对：下载字节数、GridFS 记录字节数、源文件字节数。测试结果为 ebook_1.pdf 39837 / "
         "39837 / 39837、cover_1.png 23611 / 23611 / 23611，两次下载全部一致。")
    figure("compass_08_GridFS文件元数据.png",
           "图5-1　fs.files 中的 6 个文件（Compass 文档视图：文件名、length、chunkSize 与 metadata）", 14.0)
    body("校验的意义不止于“下载成功”：GridFS 的 length 存在 fs.files 中、真实内容存在 fs.chunks 中，"
         "两者不一致（例如上传中断）时，只判断“能下载”是发现不了的，必须比对字节数。"
         "这也解释了为什么每次演示都保留这份 6 行清单：它是文件完整性的最小证据。")


def ch6() -> None:
    h1("6　架构演进")
    h2("6.1　从单机到三节点副本集")
    body("副本集 librs 由 lib-rs1、lib-rs2、lib-rs3 三个容器组成，端口 27101—27103，"
         "用共享 keyFile 做内部认证，priority 依次为 2:1:1，因此正常情况下 rs1 为主。"
         "切换形态只改环境变量 WISELIB_PROFILE=replicaset，应用代码与数据模型完全不变，"
         "库表、索引与账号在三节点上重建后导入同一份数据（50 / 30 / 3000 一致）。")
    table("表6-1　五种读取偏好的实际落点（实测）",
          ["读取偏好", "含义", "实测命中节点", "适用功能"],
          [["primary", "只读主节点", "lib-rs1", "借还书后的立即校验、库存查询"],
           ["primaryPreferred", "主优先，主不可用读从", "lib-rs1", "要求新鲜度的查询"],
           ["secondary", "只读从节点", "lib-rs3", "报表导出，明确接受陈旧"],
           ["secondaryPreferred", "从优先，从不可用读主", "lib-rs2", "馆藏检索、评分榜（默认）"],
           ["nearest", "读延迟最低的节点", "lib-rs1", "跨机房部署时的就近读"]],
          widths=[4.4, 5.2, 3.4, 5.4], aligns=["left", "left", "center", "left"])
    body("实测中最容易出错的是“读偏好写在哪里”。在 PyMongo 4.x 中，构造 MongoClient 时传 read_preference "
         "并不会让 admin.command('hello') 换节点，必须写成 db.command({'hello':1}, read_preference=RP)；"
         "集合级也要用 coll.with_options(read_preference=RP)，直接给 find 传参数会抛 TypeError。"
         "这些细节决定了“读取偏好矩阵”这张表是实测出来的还是想象出来的。")

    h2("6.2　故障转移演练")
    body("演练编排为一个 PowerShell 脚本：先启动 0.5 秒间隔的读写探针（写一条流水 + 主库读 + 从库读），"
         "同时启动 1 秒间隔的角色轮询；12 秒后停止 lib-rs1，逐 2 秒记录角色变化，再重启 lib-rs1 观察回归。")
    table("表6-2　故障转移关键时间点（2026-11-11，本地时间）",
          ["时间", "事件", "集群状态"],
          [["17:44:33", "基线快照", "term=3，lib-rs1=PRIMARY，rs2/rs3=SECONDARY"],
           ["17:44:34.2", "对 lib-rs1 发送停止信号", "主节点开始优雅退出"],
           ["17:44:34.6", "探针首次读到新主节点", "term=4，lib-rs2=PRIMARY（切换在 1 秒内完成）"],
           ["17:44:37.7", "lib-rs1 容器完全退出", "rs2 独立承担读写，rs3 保持 SECONDARY"],
           ["17:44:47", "重启 lib-rs1", "加入后先以 SECONDARY 追赶 oplog"],
           ["17:45:02", "lib-rs1 恢复为 SECONDARY", "三节点健康，主仍为 rs2"],
           ["17:45:13", "原主按 priority 夺回主位", "term=5，lib-rs1=PRIMARY"]],
          widths=[3.2, 5.6, 9.0], aligns=["center", "left", "left"])
    figure("28_故障转移时间线.png", "图6-1　故障转移演练编排时间线", 11.5)
    body("这次演练最有价值的结论不是“切换成功”，而是“业务无感”：探针在 90 秒内完成 179 次写入、"
         "179 次主库读、179 次从库读，全部成功，最长一次写入 20.7 ms（首次建连），P99 为 2.8 ms，"
         "切换窗口内的写入平均耗时 1.1 ms。原因是写关注为 majority 时驱动可重试，"
         "选主在 1 秒内完成，重试落在服务端超时之前。")
    figure("29_故障转移业务影响.png", "图6-2　故障转移期间探针统计与写入耗时分布", 11.5)
    body("需要如实记录的一点是：本轮演练之前的一次编排因探针脚本把字符串 'primary' 当作读偏好传入而直接报错，"
         "定位后改用 ReadPreference.PRIMARY 对象并重跑，才有了上面这份 179 条的有效样本。"
         "文档里保留这次返工，是因为它说明“演练脚本本身也要自测”，否则得到的是一份看起来完整、实际为空的记录。")

    h2("6.3　节点增删演练")
    body("扩容演练启动第四个容器 lib-rs4（27104，priority=0，只参与复制与投票），用 replSetReconfig 把它加入配置，"
         "12 秒后状态显示 4 个成员（1 主 3 从、health 全为 1）；随后在同一集合上执行 removenode，"
         "8 秒后回到 3 个成员，主节点始终是 lib-rs1，term 保持 5，未触发重新选举。"
         "priority=0 的用意是让新节点只承担读与投票，避免刚加入、oplog 尚未追平就被选为主。"
         "演练结束后容器停机，但配置与日志保留，可随时复用。")
    figure("30_节点增删演练.png", "图6-3　addnode 与 removenode 前后成员变化", 11.5)

    h2("6.4　分片集群与分片键论证")
    body("分片集群由 4 类角色组成：配置服务器 lib-cfg（configsvr 副本集 cfgrs，27201）、"
         "两个分片 lib-shard1 与 lib-shard2（各自是单节点副本集 shard1rs / shard2rs，27301 / 27302）、"
         "路由 lib-mongos（27030，内部 27017）。只对 borrow_logs 分片，分片键为 {reader_card: 'hashed'}；"
         "books、readers、category_stats 保持不分片，落在主分片上——这是有意的取舍："
         "后三者数据量小、以等值查询为主，分片带来的路由开销大于收益。")
    body("分片键为什么选 reader_card 的哈希值，需要把三个备选方案放在一起比较。方案一，用 {borrow_date: 1} 做范围分片："
         "好处是按时间范围查询可以定向到少数分片，坏处是借阅流水天然按时间递增，新写入永远落在最后一个分片，"
         "形成写入热点，而且历史数据所在的块无法再分裂，只能靠迁移均衡，长期看是“越写越偏”。"
         "方案二，用 {book_isbn: 1}：热门书的流水会集中到同一个块，热门书恰恰是查询最频繁的对象，"
         "热点从写入转移到了读，且 ISBN 前缀高度集中（9787 开头），单调性同样明显。"
         "方案三，用 {reader_card: 'hashed'}：卡号基数足够（30 名读者、后续可扩展到数万），"
         "哈希后写入在分片间近似均匀，30 名读者 3000 条流水实测分布为 1300 : 1700（43.3% : 56.7%），"
         "两个分片各 2 个块，没有出现单点大块。代价是按读者查询才能定向，按 ISBN 或按时间查询会变成跨分片。")
    body("这个代价是否可接受，取决于真实的查询分布。本项目最高频的读路径是“查某位读者的借阅历史”"
         "（管理端与读者端都会触发），其次是“某本书的借阅历史”和“按时间统计趋势”。"
         "前者恰好命中分片键，执行计划为 SINGLE_SHARD，实测 200 次 count 平均 0.71 ms；"
         "后两者会走 SHARD_MERGE，实测 1.50 ms，是定向查询的 2.1 倍。在 3000 条数据上这个差距只有 0.8 ms，"
         "但当数据涨到千万级时，跨分片的代价会体现在网络往返与合并排序上，而不是本地索引扫描。")
    figure("32_分片分布与查询路由.png", "图6-4　分片分布、执行阶段与定向/跨分片耗时对比", 11.5)
    body("一个常被忽略的约束是：分片键决定后几乎不能改。MongoDB 支持通过 refineCollectionShardKey 追加后缀，"
         "但不允许更换主分片键；真要改只能重建集合并迁移数据。因此这里的结论不是“哈希一定最优”，"
         "而是“在本项目的查询分布下，哈希 reader_card 的收益（写入均匀、读者查询定向）大于损失（ISBN 与时间查询跨分片）”，"
         "并且为后者保留了索引与聚合管道的优化空间。如果未来业务重心转向按书统计，正确的做法是用 "
         "{book_isbn: 1, borrow_date: 1} 做复合范围分片并接受写入热点，而不是硬改现有分片键。")
    body("分片集群同样开启了三账号权限体系，验证结果与单机一致：只读账号 6 类写与管理操作被拒，"
         "读写账号仅写与查询通过，管理账号全部通过。这说明权限模型是跟着角色走、与部署形态无关的。")

    h2("6.5　当前架构的局限")
    body("必须说清这套集群离生产还有多远。其一，配置服务器只有 1 个节点，生产要求 3 节点副本集，"
         "否则配置库本身成为单点。其二，两个分片各自是单节点副本集，只验证了“分片能工作”，"
         "没有验证“分片内部的高可用”，生产应为每个分片配 3 节点。其三，所有容器同在一台物理机上，"
         "故障域没有真正隔离，断网、磁盘故障、宿主机宕机都无法通过副本集规避。其四，数据量只有 3000 条，"
         "分片均衡与块迁移的行为在小数据量下观察不到，需要百万级数据才能看到真实的 chunk 分裂与迁移。"
         "其五，keyFile 与账号密码以明文写在 compose 与配置文件中，生产应改为密钥管理与环境注入。"
         "这些局限不影响本项目对“技术可行性与演进路径”的验证结论，但不能被当作生产方案直接照搬。")


def ch7() -> None:
    h1("7　问题与总结")
    h2("7.1　实施中遇到的问题与解决")
    table("表7-1　典型问题与处理方式",
          ["问题现象", "根因", "解决方式"],
          [["首次 createUser 成功后，后续建账号报 Unauthorized",
            "mongod 的 localhost exception 在第一次创建用户后立即失效",
            "后续建号统一带 admin 凭证连接，账号全部建在 admin 库"],
           ["text 索引报 code 67 CannotCreateIndex",
            "default_language 设为 simple 时中文分词不可用",
            "改为 default_language=none，按中文原词匹配"],
           ["还书时报 naive 与 aware datetime 不能相减",
            "MongoClient 默认 tz_aware=False，读出的时间是朴素时间",
            "客户端统一 tz_aware=True，全链路用带时区时间"],
           ["给 find 传 read_preference 抛 TypeError",
            "read_preference 是客户端/集合级选项，不是方法参数",
            "改用 coll.with_options(read_preference=RP) 与 command(…, read_preference=RP)"],
           ["探针脚本启动即崩，报 'primary' is not a read preference",
            "把字符串当成了 ReadPreference 对象",
            "改为 ReadPreference.PRIMARY / SECONDARY_PREFERRED 后重跑演练"],
           ["listDatabases 对普通账号也成功，权限验证结论错误",
            "listDatabases 不需要额外权限",
            "改用 serverStatus（需 clusterMonitor）作为区分依据"],
           ["Top10 排序结果在平票时抖动",
            "borrow_count 相同且 $sort 未指定次序",
            "$sort 追加 _id:1 保证稳定顺序"],
           ["27017 端口被占用、不敢动已有容器",
            "本机已有 mongodb 容器占用 0.0.0.0:27017",
            "全部新开容器，端口改用 27018/27101+/27201/27301+/27030，只绑 127.0.0.1"]],
          widths=[5.0, 5.0, 7.8], aligns=["left", "left", "left"])

    h2("7.2　结论")
    body("本项目在真实数据上完成了从建模到集群的完整验证：五类检索与四类统计的结果与源数据一致（50 / 30 / 3000）；"
         "16 个索引把借阅流水的扫描文档数从 3000 降到 10，20 万条放大实验中提速 48.89 倍；"
         "三个账号形成只读—读写—管理的清晰边界；GridFS 六个文件字节级校验全部一致；"
         "三节点副本集在 1 秒内完成选主，179 次探针读写零失败，原主按 priority 平稳回归；"
         "节点从 3 扩到 4 再回到 3，未触发重新选举；两个分片按哈希分片键分布 43.3% : 56.7%，"
         "定向查询比跨分片快 2.1 倍，权限体系与单机一致。")
    body("从方法论上，有三点比结果更值得记录。第一，结论要写在可复现的指标上：小集合的毫秒数不可信，"
         "扫描文档数与放大实验才可信。第二，取舍必须落到具体场景：同一个副本集里，检索走从节点、"
         "借还走主节点并要求多数派，这不是矛盾，而是 CAP 的分场景执行。第三，文档要保留返工痕迹："
         "把探针脚本报错、权限验证误判这两次返工写进来，比只写“全部通过”更接近真实工程。")

    h2("7.3　遗留问题与改进方向")
    body("第一，图形化核对已完成但覆盖有限。MongoDB Compass 1.50.0 已直连单机实例并核对集合文档数、"
         "索引、过滤命中条数与 fs.files 元数据（图3-2、图4-1、图4-2、图5-1 均取自 Compass 界面）；"
         "副本集与分片集群因容器服务名只在 libnet 网络内可解析，宿主机上的 Compass 无法直连，"
         "这部分证据仍依赖 lib-app 容器内的 mongosh 输出。"
         "第二，事务性未压测。借还与库存扣减目前依赖单文档原子更新与顺序写入，"
         "跨集合事务（流水 + 库存同时成功）只在设计层面讨论过，未在多文档事务上做并发压测。"
         "第三，价格字段建议改 Decimal128，以适配未来的费用结算。第四，配置服务器与分片应扩为 3 节点副本集，"
         "并把 keyFile、口令迁到密钥管理，才能真正具备生产可用性。")


def refs() -> None:
    h1("参考文献", page_break=True)
    items = [
        "[1] MongoDB, Inc. MongoDB Manual: Replication and Sharding[EB/OL]. "
        "https://www.mongodb.com/docs/manual/.",
        "[2] MongoDB, Inc. MongoDB Manual: GridFS[EB/OL]. "
        "https://www.mongodb.com/docs/manual/core/gridfs/.",
        "[3] MongoDB, Inc. MongoDB Manual: Indexes and Aggregation Pipeline[EB/OL]. "
        "https://www.mongodb.com/docs/manual/indexes/.",
        "[4] MongoDB, Inc. MongoDB Manual: Read Preference and Write Concern[EB/OL]. "
        "https://www.mongodb.com/docs/manual/core/read-preference/.",
        "[5] MongoDB, Inc. PyMongo 4.x Documentation[EB/OL]. https://pymongo.readthedocs.io/en/stable/.",
        "[6] 课程教材. NoSQL数据库技术与应用（第2版）[M]. 本项目数据、任务书与验收要求均取自该教材配套学生包.",
    ]
    for it in items:
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Pt(0)
        p.paragraph_format.left_indent = Pt(SMALL_PT * 2)
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(it)
        _cn(r, CJK_BODY, SMALL_PT)


def appendix() -> None:
    h1("附录A　运行说明与产物清单", page_break=True)
    body("启动单机形态：docker compose -f deploy/compose.single.yml up -d；"
         "启动副本集：docker compose -f deploy/compose.replicaset.yml up -d；"
         "启动分片集群：docker compose -f deploy/compose.shard.yml up -d。"
         "初始化与导入：python app/init_db.py --reset 与 python app/import_data.py；"
         "功能演示：python app/main.py --demo；副本集/分片内的命令需在 lib-app 容器执行并指定 "
         "WISELIB_PROFILE=replicaset 或 sharded。")
    body("产物目录：app/（16 个源文件）、config/config.json、deploy/（3 个 compose 文件）、"
         "data/（7 个自定义数据目录）、records/（24 份运行日志与汇总）、exports/（9 个统计结果文件与下载校验副本）、"
         "docs/截图/（46 张截图：38 张运行日志 + 8 张 Compass 真机截图）、docs/图/（集合结构图）、docs/（本文件与答辩材料）。"
         "全部记录均来自真实运行，日志中的时间戳、文档计数、耗时数据未做人工修改。")


def main() -> None:
    setup_styles()
    page_setup()
    cover()
    toc()
    body_section()
    ch1()
    ch2()
    ch3()
    ch4()
    ch5()
    ch6()
    ch7()
    refs()
    appendix()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT))
    print(f"已生成 {OUT}")


if __name__ == "__main__":
    main()



