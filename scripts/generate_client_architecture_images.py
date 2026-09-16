from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).resolve().parents[1] / "docs" / "client-architecture"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1600, 1000
FONT_PATH = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_REGULAR = "/System/Library/Fonts/STHeiti Light.ttc"
MONO = "/System/Library/Fonts/Menlo.ttc"

COLORS = {
    "ink": "#111827",
    "body": "#374151",
    "muted": "#6B7280",
    "faint": "#9CA3AF",
    "line": "#E5E7EB",
    "canvas": "#F6F7F9",
    "surface": "#FFFFFF",
    "subtle": "#F9FAFB",
    "nav": "#0B1220",
    "nav2": "#111A2B",
    "navtext": "#A7B0C0",
    "blue": "#155EEF",
    "blue_soft": "#EAF1FF",
    "green": "#0E9F6E",
    "green_soft": "#E8F8F1",
    "orange": "#D97706",
    "orange_soft": "#FFF4DE",
    "red": "#D92D20",
    "red_soft": "#FEECEC",
    "purple": "#6941C6",
    "purple_soft": "#F2EDFF",
}


def font(size: int, regular: bool = False, mono: bool = False):
    path = MONO if mono else (FONT_REGULAR if regular else FONT_PATH)
    return ImageFont.truetype(path, size=size)


def rounded(draw, box, radius=10, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, value, size=16, fill=None, regular=False, mono=False, anchor=None):
    draw.text(xy, value, font=font(size, regular=regular, mono=mono), fill=fill or COLORS["ink"], anchor=anchor)


def wrap(value: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    for para in value.split("\n"):
        current = ""
        for ch in para:
            current += ch
            if len(current) >= max_chars:
                lines.append(current)
                current = ""
        if current or not para:
            lines.append(current)
    return lines


def paragraph(draw, xy, value, size=14, fill=None, max_chars=28, line_gap=8, regular=True):
    x, y = xy
    line_h = size + line_gap
    for line in wrap(value, max_chars):
        text(draw, (x, y), line, size=size, fill=fill or COLORS["body"], regular=regular)
        y += line_h
    return y


def pill(draw, x, y, label, fill, color, pad_x=12, h=28, size=12):
    f = font(size)
    bbox = draw.textbbox((0, 0), label, font=f)
    width = bbox[2] - bbox[0] + pad_x * 2
    rounded(draw, (x, y, x + width, y + h), radius=h // 2, fill=fill)
    text(draw, (x + width // 2, y + h // 2), label, size=size, fill=color, anchor="mm")
    return x + width


def panel(draw, box, title=None, subtitle=None, accent=None):
    rounded(draw, box, radius=10, fill=COLORS["surface"], outline=COLORS["line"], width=1)
    x1, y1, x2, y2 = box
    if accent:
        draw.rounded_rectangle((x1, y1, x1 + 5, y2), radius=3, fill=accent)
    if title:
        text(draw, (x1 + 20, y1 + 18), title, size=16, fill=COLORS["ink"])
    if subtitle:
        text(draw, (x1 + 20, y1 + 46), subtitle, size=12, fill=COLORS["muted"], regular=True)


def progress(draw, x, y, w, value, color):
    rounded(draw, (x, y, x + w, y + 8), radius=4, fill=COLORS["line"])
    rounded(draw, (x, y, x + int(w * value), y + 8), radius=4, fill=color)


def line(draw, points, fill=COLORS["line"], width=2):
    draw.line(points, fill=fill, width=width, joint="curve")


def badge_icon(draw, x, y, label, fill, color):
    rounded(draw, (x, y, x + 30, y + 30), radius=8, fill=fill)
    text(draw, (x + 15, y + 15), label, size=13, fill=color, anchor="mm")


def shell(title, kicker, client, active, nav_items, page_no):
    im = Image.new("RGB", (W, H), COLORS["canvas"])
    d = ImageDraw.Draw(im)
    # quiet technical grid
    for x in range(260, W, 80):
        d.line((x, 84, x, H - 42), fill="#F0F2F5", width=1)
    for y in range(120, H - 42, 80):
        d.line((250, y, W - 36, y), fill="#F0F2F5", width=1)

    d.rectangle((0, 0, 232, H), fill=COLORS["nav"])
    # mark
    rounded(d, (28, 28, 66, 66), radius=10, fill=COLORS["blue"])
    text(d, (47, 47), "链", size=21, fill="#FFFFFF", anchor="mm")
    text(d, (78, 32), "链易配", size=19, fill="#FFFFFF")
    text(d, (78, 58), "SUPPLY CHAIN OS", size=9, fill=COLORS["navtext"], regular=True, mono=True)
    text(d, (28, 108), client, size=12, fill=COLORS["navtext"], regular=True)
    y = 140
    for item in nav_items:
        is_active = item == active
        if is_active:
            rounded(d, (18, y - 8, 214, y + 34), radius=7, fill=COLORS["nav2"])
            d.rectangle((18, y - 2, 21, y + 28), fill=COLORS["blue"])
        text(d, (38, y), item, size=14, fill="#FFFFFF" if is_active else COLORS["navtext"], regular=True)
        y += 52
    line(d, (28, 670, 204, 670), fill="#253149", width=1)
    text(d, (28, 700), "Agent 权限", size=12, fill=COLORS["navtext"], regular=True)
    pill(d, 28, 728, "可读 / 可整理", COLORS["green_soft"], COLORS["green"], h=26, size=11)
    pill(d, 28, 764, "写入需确认", COLORS["orange_soft"], COLORS["orange"], h=26, size=11)
    text(d, (28, H - 66), "CHAIN OS / 2026", size=10, fill="#66738A", regular=True, mono=True)

    # top bar
    text(d, (264, 26), kicker, size=11, fill=COLORS["blue"], regular=True, mono=True)
    text(d, (264, 48), title, size=27, fill=COLORS["ink"])
    text(d, (264, 86), "传统业务工作台 + 对话式 Agent · 人在关键节点做最终决策", size=14, fill=COLORS["muted"], regular=True)
    pill(d, 1324, 34, f"CLIENT 0{page_no}", COLORS["blue_soft"], COLORS["blue"], h=28, size=11)
    return im, d


def save(im: Image.Image, name: str):
    path = OUT / name
    im.save(path, "PNG", optimize=True)
    return path


def buyer():
    im, d = shell(
        "企业采购端｜让采购人只做决策",
        "BUYER WORKSPACE / PROCUREMENT",
        "企业采购客户端",
        "智能工作台",
        ["智能工作台", "需求管理", "供应商库", "询价与报价", "订单履约", "消息中心"],
        1,
    )
    # conversation panel
    panel(d, (264, 126, 948, 414), "Agent 采购工作台", "自然语言输入 → 任务拆解 → 调用平台工具", accent=COLORS["blue"])
    rounded(d, (286, 190, 926, 258), radius=8, fill=COLORS["blue_soft"])
    text(d, (306, 202), "我需要 100 件整车控制器，优先距离近、信用高、产能充足的供应商。", size=14, fill=COLORS["ink"], regular=True)
    pill(d, 306, 274, "需求已结构化", COLORS["green_soft"], COLORS["green"], h=26, size=11)
    text(d, (448, 280), "产品：整车控制器   数量：100 件   交期：30 天", size=12, fill=COLORS["body"], regular=True)
    # tool calls
    text(d, (306, 326), "Agent 已调用", size=12, fill=COLORS["muted"], regular=True)
    tool_x = 306
    for label, color in [("匹配供应商", COLORS["blue"]), ("查产能日历", COLORS["green"]), ("查信用画像", COLORS["purple"]), ("汇总报价", COLORS["orange"])]:
        tool_x = pill(d, tool_x, 350, label, COLORS["subtle"], color, h=28, size=11) + 8
    # right confirmation panel
    panel(d, (970, 126, 1536, 414), "决策确认区", "Agent 给建议，人确认后产生外部动作", accent=COLORS["orange"])
    badge_icon(d, 994, 186, "!", COLORS["orange_soft"], COLORS["orange"])
    text(d, (1036, 187), "已生成 3 家候选供应商", size=15, fill=COLORS["ink"])
    text(d, (1036, 216), "建议先发送询价，尚未触达任何供应商", size=12, fill=COLORS["muted"], regular=True)
    for i, (label, val, color) in enumerate([("产品匹配", "96", COLORS["blue"]), ("产能充足", "92", COLORS["green"]), ("信用评分", "88", COLORS["purple"])]):
        yy = 268 + i * 36
        text(d, (994, yy), label, size=12, fill=COLORS["body"], regular=True)
        progress(d, 1100, yy + 5, 200, int(val) / 100, color)
        text(d, (1320, yy), val, size=12, fill=color, mono=True)
    rounded(d, (994, 368, 1508, 400), radius=7, fill=COLORS["blue"])
    text(d, (1251, 384), "确认并发送询价", size=13, fill="#FFFFFF", anchor="mm")
    # candidates
    panel(d, (264, 434, 1536, 784), "候选供应商比较", "平台原有匹配、企业画像、产能、信用、历史合作等能力，在这里被 Agent 统一整理", accent=COLORS["green"])
    card_xs = [286, 692, 1098]
    suppliers = [
        ("湘潭精控科技", "93", "产能 120 / 交期 18 天", "信用 91 · 绿色 A", COLORS["green"]),
        ("株洲智造电子", "89", "产能 100 / 交期 25 天", "信用 88 · 绿色 B", COLORS["blue"]),
        ("长沙新联动力", "86", "产能 160 / 交期 32 天", "信用 86 · 绿色 A", COLORS["purple"]),
    ]
    for x, (name, score, cap, trust, color) in zip(card_xs, suppliers):
        rounded(d, (x, 494, x + 370, 734), radius=8, fill=COLORS["subtle"], outline=COLORS["line"])
        badge_icon(d, x + 18, 514, "厂", COLORS["blue_soft"], COLORS["blue"])
        text(d, (x + 60, 516), name, size=15, fill=COLORS["ink"])
        pill(d, x + 258, 516, f"匹配 {score}", color + "18", color, h=26, size=11)
        text(d, (x + 20, 570), cap, size=13, fill=COLORS["body"], regular=True)
        text(d, (x + 20, 602), trust, size=13, fill=COLORS["body"], regular=True)
        text(d, (x + 20, 648), "匹配理由", size=11, fill=COLORS["muted"], regular=True)
        paragraph(d, (x + 20, 672), "产品能力强；距离 48km；有同类历史合作", size=12, fill=COLORS["body"], max_chars=25, line_gap=4)
    # bottom contract
    rounded(d, (264, 804, 1536, 924), radius=9, fill=COLORS["nav"])
    text(d, (288, 827), "采购闭环", size=13, fill="#FFFFFF")
    steps = [("01", "说清需求"), ("02", "Agent 找与比"), ("03", "确认询价"), ("04", "确认下单"), ("05", "跟踪履约")]
    sx = 430
    for i, (n, label) in enumerate(steps):
        d.ellipse((sx, 834, sx + 30, 864), fill=COLORS["blue"] if i < 3 else "#253149")
        text(d, (sx + 15, 849), n, size=9, fill="#FFFFFF", mono=True, anchor="mm")
        text(d, (sx + 42, 842), label, size=13, fill="#FFFFFF" if i < 3 else COLORS["navtext"], regular=True)
        if i < len(steps) - 1:
            line(d, (sx + 140, 849, sx + 190, 849), fill="#42516B", width=2)
        sx += 218
    return im


def supplier():
    im, d = shell(
        "供应商端｜把询价变成可执行订单",
        "SUPPLIER WORKSPACE / RESPONSE",
        "供应商经营客户端",
        "询价工作台",
        ["经营总览", "我的产品", "产能日历", "询价工作台", "订单履约", "信用与资质"],
        2,
    )
    # KPI strip
    kpis = [("待处理询价", "06", "较昨日 +2", COLORS["orange"]), ("本月成交", "18", "成交率 42%", COLORS["green"]), ("产能利用率", "72%", "未来 30 天", COLORS["blue"]), ("信用评分", "91", "A级企业", COLORS["purple"])]
    x = 264
    for label, val, hint, color in kpis:
        panel(d, (x, 126, x + 292, 224), accent=color)
        text(d, (x + 20, 147), label, size=12, fill=COLORS["muted"], regular=True)
        text(d, (x + 20, 174), val, size=31, fill=COLORS["ink"], mono=True)
        text(d, (x + 20, 208), hint, size=12, fill=color, regular=True)
        x += 314
    # agent response assistant
    panel(d, (264, 244, 948, 612), "Agent 响应助手", "自动读取询价、产能和历史报价，生成可编辑的回应草稿", accent=COLORS["blue"])
    rounded(d, (286, 304, 926, 368), radius=8, fill=COLORS["blue_soft"])
    text(d, (306, 318), "采购方询价：整车控制器 × 100，30 天内交付，关注信用与绿色等级", size=13, fill=COLORS["ink"], regular=True)
    pill(d, 306, 386, "Agent 已分析", COLORS["green_soft"], COLORS["green"], h=26, size=11)
    text(d, (428, 392), "库存与产能可覆盖；推荐报价区间 ¥238–252 / 件", size=12, fill=COLORS["body"], regular=True)
    for i, (title, desc, color) in enumerate([("产能冲突检查", "当前排产无冲突，交期可承诺 25 天", COLORS["green"]), ("报价建议", "基于历史成交与成本区间生成参考价", COLORS["blue"]), ("风险提示", "原材料价格近 30 天波动 4.2%", COLORS["orange"]) ]):
        yy = 438 + i * 52
        badge_icon(d, 306, yy, "✓" if i == 0 else "·", color + "18", color)
        text(d, (350, yy + 2), title, size=13, fill=COLORS["ink"])
        text(d, (350, yy + 26), desc, size=11, fill=COLORS["muted"], regular=True)
    rounded(d, (306, 570, 906, 600), radius=7, fill=COLORS["subtle"], outline=COLORS["line"])
    text(d, (326, 585), "回应草稿：我司可在 25 天内交付 100 件，含税报价 ¥246 / 件……", size=12, fill=COLORS["body"], regular=True, anchor="lm")
    # confirmation
    panel(d, (970, 244, 1536, 612), "供应商确认区", "Agent 负责准备，企业负责人确认后提交", accent=COLORS["orange"])
    text(d, (994, 306), "待确认报价", size=12, fill=COLORS["muted"], regular=True)
    text(d, (994, 334), "¥246", size=32, fill=COLORS["ink"], mono=True)
    text(d, (1108, 348), "/ 件 · 含税", size=12, fill=COLORS["muted"], regular=True)
    for label, val, color in [("交付周期", "25 天", COLORS["blue"]), ("预计毛利", "18.6%", COLORS["green"]), ("绿色等级", "A", COLORS["green"])]:
        yy = 402 + [("交付周期", "25 天", COLORS["blue"]), ("预计毛利", "18.6%", COLORS["green"]), ("绿色等级", "A", COLORS["green"])].index((label, val, color)) * 40
        text(d, (994, yy), label, size=12, fill=COLORS["muted"], regular=True)
        text(d, (1335, yy), val, size=13, fill=color, mono=True, anchor="ra")
    rounded(d, (994, 526, 1508, 558), radius=7, fill=COLORS["blue"])
    text(d, (1251, 542), "确认并提交报价", size=13, fill="#FFFFFF", anchor="mm")
    # order backflow
    panel(d, (264, 636, 1536, 844), "报价 → 订单 → 履约", "供应商侧数据持续回流到采购决策与平台风控", accent=COLORS["green"])
    xs = [352, 650, 948, 1246]
    stages = [("询价", "收到需求", COLORS["blue"]), ("报价", "人工确认", COLORS["orange"]), ("订单", "双方确认", COLORS["purple"]), ("履约", "状态回流", COLORS["green"])]
    for i, (x, (stage, sub, color)) in enumerate(zip(xs, stages)):
        d.ellipse((x, 704, x + 60, 764), fill=color)
        text(d, (x + 30, 734), str(i + 1).zfill(2), size=13, fill="#FFFFFF", mono=True, anchor="mm")
        text(d, (x - 4, 780), stage, size=15, fill=COLORS["ink"])
        text(d, (x - 4, 810), sub, size=12, fill=COLORS["muted"], regular=True)
        if i < 3:
            line(d, (x + 66, 734, xs[i + 1] - 14, 734), fill="#CBD5E1", width=3)
    rounded(d, (264, 870, 1536, 924), radius=8, fill=COLORS["green_soft"])
    text(d, (288, 887), "供应商得到的创新价值：少填表、少重复沟通，但保留对价格、交期、履约的经营控制权。", size=13, fill=COLORS["green"], regular=True)
    return im


def admin():
    im, d = shell(
        "平台运营端｜从看数据到推动处置",
        "PLATFORM CONTROL ROOM / GOVERNANCE",
        "平台 / 园区运营客户端",
        "风险与产业链",
        ["运营总览", "企业审核", "供需治理", "风险与产业链", "数据授权", "审计日志"],
        3,
    )
    # metrics
    metrics = [("入驻企业", "32", "已审核 28", COLORS["blue"]), ("活跃供需", "16", "本周 +4", COLORS["green"]), ("风险预警", "03", "红 1 · 橙 2", COLORS["red"]), ("撮合交易", "08", "履约中 5", COLORS["purple"])]
    x = 264
    for label, value, hint, color in metrics:
        panel(d, (x, 126, x + 292, 224), accent=color)
        text(d, (x + 20, 147), label, size=12, fill=COLORS["muted"], regular=True)
        text(d, (x + 20, 174), value, size=31, fill=COLORS["ink"], mono=True)
        text(d, (x + 20, 208), hint, size=12, fill=color, regular=True)
        x += 314
    # agent task panel
    panel(d, (264, 244, 730, 598), "Agent 运营助手", "用自然语言查询、解释、生成处置草案；所有写操作留痕并确认", accent=COLORS["blue"])
    rounded(d, (286, 300, 708, 358), radius=8, fill=COLORS["blue_soft"])
    text(d, (306, 314), "找出本地芯片供应不足且存在单一来源风险的企业。", size=13, fill=COLORS["ink"], regular=True)
    pill(d, 306, 376, "任务拆解", COLORS["purple_soft"], COLORS["purple"], h=26, size=11)
    y = 426
    for n, title, desc, color in [("01", "查产业链图谱", "定位芯片上下游与关键节点", COLORS["purple"]), ("02", "查预警引擎", "汇总进口依赖、跨省依赖、本地短缺", COLORS["orange"]), ("03", "生成处置草案", "推荐补链企业与招商任务", COLORS["green"])]:
        d.ellipse((306, y, 338, y + 32), fill=color)
        text(d, (322, y + 16), n, size=9, fill="#FFFFFF", mono=True, anchor="mm")
        text(d, (356, y + 1), title, size=13, fill=COLORS["ink"])
        text(d, (356, y + 24), desc, size=11, fill=COLORS["muted"], regular=True)
        y += 55
    rounded(d, (286, 548, 708, 576), radius=7, fill=COLORS["orange_soft"])
    text(d, (306, 562), "发现 1 个红色预警，建议创建招商任务", size=12, fill=COLORS["orange"], regular=True, anchor="lm")
    # alert table / graph
    panel(d, (752, 244, 1150, 598), "风险与产业链视图", "预警引擎 + 图谱分析 + 时序预测", accent=COLORS["red"])
    # mini network
    nodes = [(824, 362, "芯片", COLORS["red"]), (930, 318, "控制器", COLORS["blue"]), (1018, 382, "整车", COLORS["green"]), (930, 452, "电机", COLORS["orange"]), (815, 482, "传感器", COLORS["purple"])]
    for x1, y1, _, _ in nodes[1:]:
        line(d, (854, 378, x1, y1), fill="#CBD5E1", width=2)
    for x1, y1, label, color in nodes:
        d.ellipse((x1 - 28, y1 - 28, x1 + 28, y1 + 28), fill=color + "18", outline=color, width=2)
        text(d, (x1, y1), label, size=11, fill=color, anchor="mm")
    pill(d, 784, 526, "红色 · 单一进口来源", COLORS["red_soft"], COLORS["red"], h=26, size=11)
    # confirmation and audit
    panel(d, (1172, 244, 1536, 598), "处置确认与审计", "运营人员是责任主体，Agent 不越权执行", accent=COLORS["orange"])
    text(d, (1194, 302), "待处理预警", size=12, fill=COLORS["muted"], regular=True)
    text(d, (1194, 328), "芯片进口依赖度 74%", size=15, fill=COLORS["ink"])
    pill(d, 1194, 362, "高风险", COLORS["red_soft"], COLORS["red"], h=26, size=11)
    text(d, (1194, 410), "Agent 建议", size=11, fill=COLORS["muted"], regular=True)
    paragraph(d, (1194, 434), "发起本地替代供应商招商，通知产业链相关企业补充产能信息。", size=12, fill=COLORS["body"], max_chars=18, line_gap=4)
    rounded(d, (1194, 532, 1512, 562), radius=7, fill=COLORS["blue"])
    text(d, (1353, 547), "确认创建处置任务", size=12, fill="#FFFFFF", anchor="mm")
    text(d, (1194, 576), "已记录：查询条件 · 数据来源 · 建议 · 操作人", size=10, fill=COLORS["muted"], regular=True)
    # governance footer
    panel(d, (264, 622, 1536, 844), "平台治理闭环", "三类客户端共享同一套企业、供需、交易、风险与审计数据", accent=COLORS["purple"])
    cards = [("数据治理", "企业审核 · 授权 · 外部接口", COLORS["blue"]), ("智能决策", "匹配 · 图谱 · 预测 · Agent", COLORS["purple"]), ("风险处置", "预警 · 派单 · 回执 · 审计", COLORS["red"])]
    for x, (title, desc, color) in zip([286, 700, 1114], cards):
        rounded(d, (x, 690, x + 380, 798), radius=8, fill=COLORS["subtle"], outline=COLORS["line"])
        d.rectangle((x, 690, x + 380, 696), fill=color)
        text(d, (x + 20, 718), title, size=15, fill=COLORS["ink"])
        text(d, (x + 20, 754), desc, size=12, fill=COLORS["body"], regular=True)
        pill(d, x + 20, 778, "可追溯", color + "18", color, h=24, size=10)
    rounded(d, (264, 870, 1536, 924), radius=8, fill=COLORS["nav"])
    text(d, (288, 887), "运营端的 Agent 不是聊天机器人，而是受权限、确认、审计约束的业务操作助手。", size=13, fill="#FFFFFF", regular=True)
    return im


if __name__ == "__main__":
    paths = [
        save(buyer(), "01-enterprise-buyer-agent.png"),
        save(supplier(), "02-supplier-agent.png"),
        save(admin(), "03-platform-operations-agent.png"),
    ]
    for path in paths:
        print(path)
