"""Generate deterministic, Chinese-readable client and Agent architecture diagrams.

Usage:
    python3 scripts/generate_client_architecture_diagrams.py

The project already has Pillow available.  requirements-diagrams.txt documents the
small, isolated dependency so the images can be regenerated on another machine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "client-architecture"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1800, 1125
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_LIGHT = "/System/Library/Fonts/STHeiti Light.ttc"
MONO = "/System/Library/Fonts/Menlo.ttc"

C = {
    "ink": "#101828", "body": "#344054", "muted": "#667085", "faint": "#98A2B3",
    "line": "#D0D5DD", "canvas": "#F7F8FA", "white": "#FFFFFF", "soft": "#F9FAFB",
    "nav": "#0B1220", "nav2": "#111A2B", "navtext": "#A7B0C0",
    "blue": "#155EEF", "blue_soft": "#EAF1FF", "green": "#0E9F6E", "green_soft": "#E8F8F1",
    "orange": "#D97706", "orange_soft": "#FFF4DE", "red": "#D92D20", "red_soft": "#FEECEC",
    "purple": "#6941C6", "purple_soft": "#F2EDFF", "cyan": "#0891B2", "cyan_soft": "#E6F8FC",
}


def f(size: int, light=False, mono=False):
    return ImageFont.truetype(MONO if mono else (FONT_LIGHT if light else FONT), size)


def t(d, xy, value, size=16, color=None, light=False, mono=False, anchor=None):
    d.text(xy, value, font=f(size, light, mono), fill=color or C["ink"], anchor=anchor)


def rr(d, box, fill, outline=None, radius=10, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def wrap(value: str, n: int) -> list[str]:
    out: list[str] = []
    for para in value.split("\n"):
        cur = ""
        for ch in para:
            cur += ch
            if len(cur) >= n:
                out.append(cur)
                cur = ""
        if cur or not para:
            out.append(cur)
    return out


def para(d, x, y, value, size=13, color=None, n=24, gap=7):
    for row in wrap(value, n):
        t(d, (x, y), row, size=size, color=color or C["body"], light=True)
        y += size + gap
    return y


def chip(d, x, y, label, fill, color, size=11, h=26):
    box = d.textbbox((0, 0), label, font=f(size))
    w = box[2] - box[0] + 22
    rr(d, (x, y, x + w, y + h), fill, radius=h // 2)
    t(d, (x + w / 2, y + h / 2), label, size=size, color=color, anchor="mm")
    return w


def heading(d, x, y, num, title, subtitle, color):
    rr(d, (x, y, x + 34, y + 34), color, radius=9)
    t(d, (x + 17, y + 17), num, size=12, color=C["white"], mono=True, anchor="mm")
    t(d, (x + 48, y + 1), title, size=18, color=C["ink"])
    t(d, (x + 48, y + 27), subtitle, size=11, color=C["muted"], light=True)


def card(d, box, title, subtitle=None, color=None):
    rr(d, box, C["white"], outline=C["line"], radius=10)
    x1, y1, x2, _ = box
    if color:
        d.rectangle((x1, y1, x1 + 5, y1 + 64), fill=color)
    t(d, (x1 + 20, y1 + 15), title, size=15, color=C["ink"])
    if subtitle:
        t(d, (x1 + 20, y1 + 42), subtitle, size=11, color=C["muted"], light=True)


def bullet(d, x, y, label, desc, color, width=380):
    d.ellipse((x, y + 4, x + 12, y + 16), fill=color)
    t(d, (x + 25, y), label, size=13, color=C["ink"])
    t(d, (x + 25, y + 23), desc, size=11, color=C["muted"], light=True)


def arrow(d, a, b, color=C["line"], width=3):
    d.line((a, b), fill=color, width=width)
    x1, y1 = a
    x2, y2 = b
    if abs(x2 - x1) >= abs(y2 - y1):
        pts = [(x2, y2), (x2 - 11, y2 - 6), (x2 - 11, y2 + 6)] if x2 > x1 else [(x2, y2), (x2 + 11, y2 - 6), (x2 + 11, y2 + 6)]
    else:
        pts = [(x2, y2), (x2 - 6, y2 - 11), (x2 + 6, y2 - 11)] if y2 > y1 else [(x2, y2), (x2 - 6, y2 + 11), (x2 + 6, y2 + 11)]
    d.polygon(pts, fill=color)


def base(title, kicker, client, page):
    im = Image.new("RGB", (W, H), C["canvas"])
    d = ImageDraw.Draw(im)
    for x in range(275, W, 90):
        d.line((x, 106, x, H - 40), fill="#EEF1F5", width=1)
    for y in range(145, H - 40, 90):
        d.line((250, y, W - 35, y), fill="#EEF1F5", width=1)
    d.rectangle((0, 0, 236, H), fill=C["nav"])
    rr(d, (28, 28, 66, 66), C["blue"], radius=10)
    t(d, (47, 47), "链", size=21, color=C["white"], anchor="mm")
    t(d, (78, 31), "链易配", size=19, color=C["white"])
    t(d, (78, 57), "SUPPLY CHAIN OS", size=9, color=C["navtext"], light=True, mono=True)
    t(d, (28, 107), client, size=12, color=C["navtext"], light=True)
    t(d, (28, H - 65), "CHAIN OS / 2026", size=10, color="#66738A", light=True, mono=True)
    t(d, (264, 27), kicker, size=11, color=C["blue"], light=True, mono=True)
    t(d, (264, 51), title, size=28, color=C["ink"])
    t(d, (264, 91), "客户端能力 + 实现架构 + Agent 增量 · 基于当前项目模块归类", size=14, color=C["muted"], light=True)
    chip(d, 1570, 38, f"CLIENT 0{page}", C["blue_soft"], C["blue"], size=11)
    return im, d


def nav(d, active, items):
    t(d, (28, 148), "客户端导航", size=11, color=C["faint"], light=True)
    y = 180
    for item in items:
        if item == active:
            rr(d, (18, y - 8, 216, y + 34), C["nav2"], radius=7)
            d.rectangle((18, y - 2, 21, y + 28), fill=C["blue"])
            color = C["white"]
        else:
            color = C["navtext"]
        t(d, (39, y), item, size=14, color=color, light=True)
        y += 51
    d.line((28, 650, 205, 650), fill="#253149", width=1)
    t(d, (28, 681), "Agent 边界", size=11, color=C["faint"], light=True)
    chip(d, 28, 710, "查询 / 整理", C["green_soft"], C["green"], size=10, h=24)
    chip(d, 28, 745, "写入先确认", C["orange_soft"], C["orange"], size=10, h=24)
    chip(d, 28, 780, "全程留审计", C["purple_soft"], C["purple"], size=10, h=24)


def layer_stack(d, x, y, w, rows, accent):
    for i, (title, desc, color) in enumerate(rows):
        yy = y + i * 61
        rr(d, (x, yy, x + w, yy + 49), color, radius=8)
        t(d, (x + 16, yy + 8), title, size=13, color=C["white"] if color != C["blue_soft"] else C["blue"])
        t(d, (x + 16, yy + 30), desc, size=11, color=C["white"] if color != C["blue_soft"] else C["body"], light=True)
        if i < len(rows) - 1:
            arrow(d, (x + w / 2, yy + 50), (x + w / 2, yy + 61), color=accent, width=2)


def footer(d, text_value, color=C["nav"]):
    rr(d, (264, 1048, 1764, 1090), color, radius=8)
    t(d, (284, 1069), text_value, size=12, color=C["white"], light=True, anchor="lm")


def buyer():
    im, d = base("企业采购端｜从需求到决策", "CLIENT BLUEPRINT / BUYER", "企业采购客户端", 1)
    nav(d, "智能工作台", ["智能工作台", "需求管理", "供应商库", "询价与报价", "订单履约", "消息中心"])
    # three columns: function, implementation, data/boundary
    card(d, (264, 140, 680, 690), "一、客户端能干什么", "保留传统路径，Agent 负责减少重复劳动", C["blue"])
    heading(d, 286, 202, "01", "提出采购任务", "自然语言 / 表单均可进入", C["blue"])
    bullet(d, 286, 264, "发布需求", "产品、数量、交期、地区、绿色偏好", C["blue"])
    bullet(d, 286, 332, "找供应商", "按产品、距离、产能、信用、历史合作筛选", C["green"])
    bullet(d, 286, 400, "看懂候选", "查看企业画像、资质、产能日历、风险标签", C["purple"])
    bullet(d, 286, 468, "比价与沟通", "询价、报价池、消息、反馈、收藏", C["orange"])
    bullet(d, 286, 536, "确认交易", "生成订单、查看履约状态、接收状态回流", C["red"])
    rr(d, (286, 602, 658, 658), C["blue_soft"], radius=8)
    t(d, (306, 615), "Agent 自动", size=12, color=C["blue"])
    t(d, (306, 637), "解析需求 · 调用匹配 · 汇总报价 · 解释理由", size=11, color=C["body"], light=True)

    card(d, (704, 140, 1196, 690), "二、功能怎样实现", "客户端入口 → Agent 编排 → 现有业务服务", C["purple"])
    t(d, (730, 204), "前端与路由", size=12, color=C["muted"], light=True)
    layer_stack(d, 730, 232, 436, [
        ("React SPA / Jinja 页面", "workspace · /match · /demand · /orders", C["blue"]),
        ("Agent 编排层（新增）", "intent → plan → tool calls → result summary", C["purple"]),
        ("既有业务服务", "matcher · profile · quote_pool · order_service", C["green"]),
        ("接口与持久化", "Flask API · SQLAlchemy · SQLite/MySQL", C["blue_soft"]),
    ], C["purple"])
    t(d, (730, 508), "关键工具映射", size=12, color=C["muted"], light=True)
    for i, row in enumerate([("search_suppliers", "match_suppliers"), ("get_supplier_profile", "profile.build_enterprise_profile"), ("compare_quotes", "quote_pool / inquiry"), ("draft_order", "order_service")]):
        yy = 538 + i * 31
        t(d, (730, yy), row[0], size=11, color=C["purple"], mono=True)
        t(d, (930, yy), "→  " + row[1], size=11, color=C["body"], light=True)

    card(d, (1220, 140, 1764, 690), "三、数据与责任边界", "结果可解释，外部动作可控", C["orange"])
    heading(d, 1246, 202, "A", "可读取数据", "Agent 只读工具自动执行", C["green"])
    for i, v in enumerate(["企业画像 / 信用", "产品目录 / 供需", "产能日历 / 距离", "历史交易 / 报价"]):
        chip(d, 1246 + (i % 2) * 224, 258 + (i // 2) * 35, v, C["green_soft"], C["green"], size=10, h=25)
    heading(d, 1246, 354, "B", "必须确认动作", "Agent 只生成草稿", C["orange"])
    for i, v in enumerate(["发送询价", "确认报价", "创建订单", "更新履约"]):
        chip(d, 1246 + (i % 2) * 224, 410 + (i // 2) * 35, v, C["orange_soft"], C["orange"], size=10, h=25)
    rr(d, (1246, 506, 1738, 640), C["soft"], outline=C["line"], radius=8)
    t(d, (1266, 526), "演示时的决策节点", size=12, color=C["ink"])
    para(d, 1266, 558, "采购人确认候选供应商后，Agent 才能把询价草稿提交给供应商；订单同样需要二次确认。", size=12, n=28, gap=5)
    footer(d, "采购主链：需求 → 匹配 → 画像/产能/信用 → 询价报价 → 人工确认 → 订单履约；Agent 是业务操作层，不替代采购责任人。")
    return im


def supplier():
    im, d = base("供应商端｜从接单到履约回流", "CLIENT BLUEPRINT / SUPPLIER", "供应商经营客户端", 2)
    nav(d, "询价工作台", ["经营总览", "我的产品", "产能日历", "询价工作台", "订单履约", "信用与资质"])
    card(d, (264, 140, 680, 690), "一、客户端能干什么", "企业掌握报价与履约的经营控制权", C["green"])
    heading(d, 286, 202, "01", "维护可交易能力", "让平台知道“我能不能接”", C["green"])
    bullet(d, 286, 264, "企业与产品", "企业画像、产品目录、资质、绿色标签", C["blue"])
    bullet(d, 286, 332, "产能与交期", "产能日历、可见范围、排产状态", C["green"])
    bullet(d, 286, 400, "处理询价", "收件、消息沟通、提交意向报价", C["orange"])
    bullet(d, 286, 468, "订单履约", "确认订单、更新节点、回传履约结果", C["purple"])
    bullet(d, 286, 536, "信用沉淀", "交易反馈、质量标签、信用事件回流", C["red"])
    rr(d, (286, 602, 658, 658), C["green_soft"], radius=8)
    t(d, (306, 615), "Agent 自动", size=12, color=C["green"])
    t(d, (306, 637), "读询价 · 查产能 · 给报价建议 · 生成回应草稿", size=11, color=C["body"], light=True)

    card(d, (704, 140, 1196, 690), "二、功能怎样实现", "供应商动作与采购主链共享数据", C["purple"])
    t(d, (730, 204), "前端与路由", size=12, color=C["muted"], light=True)
    layer_stack(d, 730, 232, 436, [
        ("企业工作台 / 询价控制台", "enterprise · inquiry · messages", C["green"]),
        ("Agent 响应助手（新增）", "read inquiry → check capacity → draft quote", C["purple"]),
        ("既有业务服务", "profile · quote_pool · fulfillment · credit_engine", C["blue"]),
        ("接口与持久化", "Flask API · SQLAlchemy · transactions", C["blue_soft"]),
    ], C["purple"])
    t(d, (730, 508), "关键工具映射", size=12, color=C["muted"], light=True)
    for i, row in enumerate([("get_inquiry", "inquiry_chat / messages"), ("check_capacity", "capacity calendar"), ("draft_quote", "quote_pool"), ("update_fulfillment", "fulfillment_service")]):
        yy = 538 + i * 31
        t(d, (730, yy), row[0], size=11, color=C["purple"], mono=True)
        t(d, (930, yy), "→  " + row[1], size=11, color=C["body"], light=True)

    card(d, (1220, 140, 1764, 690), "三、数据与责任边界", "Agent 生成建议，负责人决定是否承诺", C["orange"])
    heading(d, 1246, 202, "A", "Agent 可自动准备", "基于已有经营数据", C["green"])
    for i, v in enumerate(["询价摘要", "产能冲突检查", "报价区间建议", "回应草稿"]):
        chip(d, 1246 + (i % 2) * 224, 258 + (i // 2) * 35, v, C["green_soft"], C["green"], size=10, h=25)
    heading(d, 1246, 354, "B", "负责人确认提交", "承诺即产生业务责任", C["orange"])
    for i, v in enumerate(["提交报价", "确认交期", "接受订单", "回传履约"]):
        chip(d, 1246 + (i % 2) * 224, 410 + (i // 2) * 35, v, C["orange_soft"], C["orange"], size=10, h=25)
    rr(d, (1246, 506, 1738, 640), C["soft"], outline=C["line"], radius=8)
    t(d, (1266, 526), "供应商得到的价值", size=12, color=C["ink"])
    para(d, 1266, 558, "少填表、少重复沟通；价格、交期和履约承诺仍由供应商自己控制，避免 Agent 误承诺。", size=12, n=28, gap=5)
    footer(d, "供应商主链：维护企业/产品/产能 → 接收询价 → Agent 整理 → 人工确认报价 → 订单 → 履约状态回流 → 信用沉淀。", C["nav"])
    return im


def operations():
    im, d = base("平台运营端｜从监测到补链处置", "CLIENT BLUEPRINT / PLATFORM CONTROL", "平台 / 园区运营客户端", 3)
    nav(d, "风险与产业链", ["运营总览", "企业审核", "供需治理", "风险与产业链", "数据授权", "审计日志"])
    card(d, (264, 140, 680, 690), "一、客户端能干什么", "把平台数据变成治理与招商动作", C["red"])
    heading(d, 286, 202, "01", "治理平台数据", "确保进入撮合的数据可信", C["blue"])
    bullet(d, 286, 264, "企业审核", "入驻审核、企业状态、质量标签", C["blue"])
    bullet(d, 286, 332, "供需治理", "供需发布、数据授权、外部接口配置", C["green"])
    bullet(d, 286, 400, "监测产业链", "图谱、关键节点、产业集群与缺口", C["purple"])
    bullet(d, 286, 468, "识别风险", "进口依赖、跨省依赖、本地短缺、绿色风险", C["red"])
    bullet(d, 286, 536, "推动处置", "预警派单、招商任务、处理回执、审计", C["orange"])
    rr(d, (286, 602, 658, 658), C["red_soft"], radius=8)
    t(d, (306, 615), "人工研判", size=12, color=C["red"])
    t(d, (306, 637), "查看证据 · 判断风险 · 派单处置 · 审核回执", size=11, color=C["body"], light=True)

    card(d, (704, 140, 1196, 690), "二、功能怎样实现", "运营客户端连接分析服务与治理流程", C["purple"])
    t(d, (730, 204), "前端与路由", size=12, color=C["muted"], light=True)
    layer_stack(d, 730, 232, 436, [
        ("React 管理端 / SSR 大屏", "dashboard · admin · recruitment", C["red"]),
        ("运营分析与治理层", "evidence → human judgment → action → audit", C["purple"]),
        ("既有分析与治理服务", "alerter · forecaster · graph · audit · scheduler", C["orange"]),
        ("数据访问层", "MySQL/SQLite · Neo4j · external interfaces", C["blue_soft"]),
    ], C["purple"])
    t(d, (730, 508), "关键工具映射", size=12, color=C["muted"], light=True)
    for i, row in enumerate([("query_risk", "alerter.run_all_checks"), ("inspect_chain", "graph_manager / algorithms"), ("forecast_gap", "forecaster"), ("draft_task", "alert_workflow / recruitment")]):
        yy = 538 + i * 31
        t(d, (730, yy), row[0], size=11, color=C["purple"], mono=True)
        t(d, (930, yy), "→  " + row[1], size=11, color=C["body"], light=True)

    card(d, (1220, 140, 1764, 690), "三、数据与责任边界", "运营人员是责任主体，Agent 不越权执行", C["orange"])
    heading(d, 1246, 202, "A", "自动分析", "可重复、可解释、可追溯", C["green"])
    for i, v in enumerate(["指标汇总", "风险筛选", "图谱解释", "招商候选"]):
        chip(d, 1246 + (i % 2) * 224, 258 + (i // 2) * 35, v, C["green_soft"], C["green"], size=10, h=25)
    heading(d, 1246, 354, "B", "审批后执行", "影响企业/平台状态的动作", C["orange"])
    for i, v in enumerate(["创建处置任务", "派单通知", "修改阈值", "导出报告"]):
        chip(d, 1246 + (i % 2) * 224, 410 + (i // 2) * 35, v, C["orange_soft"], C["orange"], size=10, h=25)
    rr(d, (1246, 506, 1738, 640), C["soft"], outline=C["line"], radius=8)
    t(d, (1266, 526), "运营端最重要的证据链", size=12, color=C["ink"])
    para(d, 1266, 558, "查询条件 → 数据来源 → 计算结果 → Agent 建议 → 审批人 → 执行动作 → 审计日志。", size=12, n=28, gap=5)
    footer(d, "治理主链：企业审核/授权 → 数据汇聚 → 图谱/预测/预警 → 人工研判 → 派单处置 → 回执审计。", C["nav"])
    return im


def agent():
    im, d = base("Agent 设计｜一个入口，调用两类业务能力", "SYSTEM BLUEPRINT / AGENT ORCHESTRATION", "Agent 共用能力层", 4)
    # replace nav content with system-specific labels
    nav(d, "对话与任务", ["对话与任务", "工具注册表", "权限策略", "执行记录", "评估与反馈"])
    card(d, (264, 140, 730, 850), "一、Agent 怎么工作", "自然语言不是终点，必须落到可验证的业务计划", C["blue"])
    heading(d, 286, 202, "01", "理解意图", "提取产品、数量、角色、目标、约束", C["blue"])
    heading(d, 286, 290, "02", "生成计划", "把一句话拆成可执行的工具步骤", C["purple"])
    heading(d, 286, 378, "03", "调用工具", "只允许注册过、参数合法的业务工具", C["green"])
    heading(d, 286, 466, "04", "生成证据", "返回来源、结果、风险和待确认动作", C["orange"])
    heading(d, 286, 554, "05", "确认执行", "高风险写操作必须得到用户确认", C["red"])
    rr(d, (286, 654, 700, 806), C["blue_soft"], radius=9)
    t(d, (306, 674), "示例：采购一句话", size=13, color=C["blue"])
    para(d, 306, 710, "“找 100 件整车控制器，30 天内交付，优先近距离和高信用。”", size=13, n=26, gap=5)
    t(d, (306, 778), "→ 结构化任务：search → inspect → compare → confirm inquiry", size=11, color=C["body"], light=True)

    card(d, (754, 140, 1290, 850), "二、Agent 的核心架构", "新增的是编排层，不是替换原有业务系统", C["purple"])
    # central vertical pipeline
    layer_stack(d, 786, 207, 472, [
        ("对话入口", "企业采购 / 供应商 / 运营人员", C["blue"]),
        ("意图解析与上下文", "intent_parser · session · role context", C["purple"]),
        ("任务规划与工具编排", "plan · validate · retry · summarize", C["purple"]),
        ("策略闸门", "permission · confirmation · idempotency", C["orange"]),
        ("业务工具注册表", "read tools / draft tools / write tools", C["green"]),
        ("原有业务服务", "match · profile · quote · order · risk · graph", C["blue_soft"]),
    ], C["purple"])
    t(d, (786, 610), "三种工具级别", size=12, color=C["muted"], light=True)
    chip(d, 786, 642, "只读：自动执行", C["green_soft"], C["green"], size=11)
    chip(d, 786, 680, "草稿：展示预览", C["blue_soft"], C["blue"], size=11)
    chip(d, 786, 718, "写入：确认后执行", C["orange_soft"], C["orange"], size=11)
    para(d, 786, 767, "每个工具都要有：名称、参数 Schema、权限要求、数据来源、错误处理、审计事件。", size=11, n=30, gap=4)

    card(d, (1314, 140, 1764, 850), "三、Agent 接到哪里", "三端复用同一套工具，但权限不同", C["orange"])
    roles = [("企业采购端", "找 / 看 / 比 / 询价 / 下单", C["blue"]), ("供应商端", "读询价 / 查产能 / 报价 / 履约", C["green"])]
    y = 218
    for title, desc, color in roles:
        rr(d, (1342, y, 1736, y + 90), C["soft"], outline=C["line"], radius=8)
        d.rectangle((1342, y, 1348, y + 90), fill=color)
        t(d, (1366, y + 17), title, size=14, color=C["ink"])
        t(d, (1366, y + 48), desc, size=11, color=C["body"], light=True)
        y += 115
    t(d, (1342, 470), "安全与可靠性", size=12, color=C["muted"], light=True)
    for i, v in enumerate(["角色权限：谁可以调用", "参数校验：调用什么对象", "确认机制：何时产生外部动作", "审计日志：谁在何时做了什么"]):
        bullet(d, 1342, 504 + i * 46, v, "", C["purple"])
    rr(d, (1342, 708, 1736, 732), C["red_soft"], radius=6)
    t(d, (1358, 720), "Agent 不直接访问任意 URL / 不绕过原有权限", size=10, color=C["red"], light=True, anchor="lm")
    footer(d, "推荐落地顺序：先打通采购端“找供应商 → 查看详情 → 生成询价 → 比较报价”，再复用工具到供应商端；运营端坚持人工研判。", C["nav"])
    return im


if __name__ == "__main__":
    outputs = [
        (buyer(), "01-buyer-functions-and-architecture.png"),
        (supplier(), "02-supplier-functions-and-architecture.png"),
        (operations(), "03-platform-operations-functions-and-architecture.png"),
        (agent(), "04-agent-orchestration-design.png"),
    ]
    for (image, name) in outputs:
        path = OUT / name
        image.save(path, "PNG", optimize=True)
        print(path)
