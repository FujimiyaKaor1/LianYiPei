"""
enrich_mock_data.py — 模拟数据填充脚本（与 enrich_enterprises_and_products.py 逻辑一致）

使用 Faker(zh_CN) 连接 Flask 应用与数据库，补全 enterprises 表中为空的字段（address、contact、phone、
credit_score、registered_capital、capacity、max_capacity 等），再根据 business_scope 映射行业并
向 products 表插入 1～3 条模拟产品（含 description、category、enterprise_id），分阶段 db.session.commit()。

重复执行：默认仅对「当前无产品」的企业插入产品；使用 --force 可追加产品。

运行：在项目根目录执行
  python scripts/enrich_mock_data.py
  python scripts/enrich_mock_data.py -v --force
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from faker import Faker
except ImportError:
    print("未安装 Faker，请先执行: pip install Faker")
    print("或: pip install -r requirements.txt")
    sys.exit(1)

from app import create_app, db
from app.models import Enterprise, Product


# 行业名 -> 典型产品名词（键用于 Product.category；匹配时优先最长键命中）
INDUSTRY_PRODUCTS: dict[str, list[str]] = {
    "软件和信息技术服务业": [
        "ERP管理系统",
        "SaaS云平台",
        "数据库运维服务",
        "数据分析大屏",
        "API接口授权",
        "工业互联网网关",
        "低代码开发平台",
        "信息安全审计系统",
    ],
    "汽车制造业": [
        "新能源电池模组",
        "高强度底盘",
        "车载中控屏",
        "线控制动系统",
        "热管理系统总成",
        "智能驾驶域控制器",
    ],
    "电气机械和器材制造业": [
        "伺服电机",
        "PLC控制柜",
        "变频器",
        "工业母线槽",
        "智能配电箱",
        "永磁同步电机",
    ],
    "通用设备制造业": [
        "数控机床主轴",
        "工业机器人关节",
        "液压泵站",
        "精密减速机",
        "空压机机组",
        "工业泵阀总成",
    ],
    "专用设备制造业": [
        "半导体封装设备",
        "锂电涂布机",
        "激光切割工作站",
        "AGV调度系统",
        "焊接专机",
        "视觉检测设备",
    ],
    "化学原料和化学制品制造业": [
        "工程塑料粒子",
        "工业涂料",
        "电解液添加剂",
        "高分子粘合剂",
        "特种溶剂",
        "阻燃母粒",
    ],
    "医药制造业": [
        "原料药中间体",
        "无菌制剂",
        "医用敷料",
        "体外诊断试剂",
        "缓释胶囊",
        "中药提取物",
    ],
    "纺织业": [
        "高强涤纶丝",
        "功能性面料",
        "产业用无纺布",
        "数码印花布",
        "芳纶纤维",
        "医用防护服面料",
    ],
    "金属制品业": [
        "精密钣金件",
        "不锈钢紧固件",
        "铝合金型材",
        "粉末冶金齿轮",
        "模具钢模块",
        "镀锌卷板",
    ],
    "橡胶和塑料制品业": [
        "密封橡胶圈",
        "工程塑料件",
        "硅胶管",
        "注塑外壳",
        "汽车密封条",
        "改性PP材料",
    ],
    "非金属矿物制品业": [
        "特种陶瓷件",
        "玻璃纤维布",
        "耐火砖",
        "石英坩埚",
        "碳化硅衬底",
        "建筑幕墙板材",
    ],
    "黑色金属冶炼和压延加工业": [
        "冷轧钢卷",
        "镀锌板带",
        "特种型钢",
        "硅钢片",
        "不锈钢薄板",
        "管线钢",
    ],
    "有色金属冶炼和压延加工业": [
        "铝箔卷材",
        "铜排铜带",
        "镁合金压铸件",
        "钛合金棒材",
        "镍钴材料",
        "铝合金铸锭",
    ],
    "仪器仪表制造业": [
        "压力变送器",
        "流量计",
        "在线水质分析仪",
        "温度巡检仪",
        "称重传感器",
        "气体检测仪",
    ],
    "计算机、通信和其他电子设备制造业": [
        "多层PCB",
        "射频模组",
        "存储芯片封装",
        "液晶显示模组",
        "电源管理IC",
        "连接器组件",
    ],
    "铁路、船舶、航空航天和其他运输设备制造业": [
        "高铁制动盘",
        "船舶轴系",
        "航空紧固件",
        "复合材料舱体",
        "轨道交通座椅",
        "起落架部件",
    ],
    "电力、热力生产和供应业": [
        "分布式光伏组件",
        "储能电池柜",
        "余热锅炉",
        "智能电表",
        "箱式变电站",
        "风电变流器",
    ],
    "批发和零售业": [
        "供应链集采服务",
        "区域分销代理",
        "冷链仓储服务",
        "SKU数字化管理",
        "渠道返利系统",
        "跨境备货方案",
    ],
    "通用制造业": [
        "标准机械零部件",
        "工业耗材包",
        "产线升级改造",
        "设备维保服务",
        "工装夹具",
        "来图加工服务",
    ],
}

DEFAULT_INDUSTRY_KEY = "通用制造业"

# 关键词子串 -> 选用的行业键（在经营范围中任一词命中即采用该行）
KEYWORD_INDUSTRY_FALLBACK: list[tuple[tuple[str, ...], str]] = [
    (("软件", "信息", "互联网", "SaaS", "系统", "数据", "云计算"), "软件和信息技术服务业"),
    (("汽车", "新能源", "车载", "零部件", "底盘", "电池"), "汽车制造业"),
    (("电机", "电气", "变压器", "配电", "电控"), "电气机械和器材制造业"),
    (("机床", "数控", "液压", "工业机器人", "减速机", "机械", "精密"), "通用设备制造业"),
    (("半导体", "封装", "锂电", "激光", "专机", "设备"), "专用设备制造业"),
    (("化工", "涂料", "塑料粒子", "化学", "溶剂", "粘合剂"), "化学原料和化学制品制造业"),
    (("医药", "制剂", "试剂", "原料药"), "医药制造业"),
    (("纺织", "面料", "纤维", "无纺"), "纺织业"),
    (("金属", "钢材", "钣金", "紧固件", "模具", "铝合金"), "金属制品业"),
    (("橡胶", "塑料", "注塑", "硅胶", "密封"), "橡胶和塑料制品业"),
    (("陶瓷", "玻璃", "石英", "耐火"), "非金属矿物制品业"),
    (("钢铁", "冷轧", "镀锌", "型钢"), "黑色金属冶炼和压延加工业"),
    (("铜", "铝箔", "有色", "镁合金", "钛合金"), "有色金属冶炼和压延加工业"),
    (("仪表", "传感器", "变送器", "检测"), "仪器仪表制造业"),
    (("电路", "芯片", "电子", "PCB", "射频", "液晶"), "计算机、通信和其他电子设备制造业"),
    (("高铁", "船舶", "航空", "轨道", "交通"), "铁路、船舶、航空航天和其他运输设备制造业"),
    (("光伏", "储能", "电力", "锅炉", "风电"), "电力、热力生产和供应业"),
    (("批发", "零售", "供应链", "分销", "仓储"), "批发和零售业"),
]


def _empty_str(v) -> bool:
    return v is None or (isinstance(v, str) and not str(v).strip())


def _empty_num(v) -> bool:
    return v is None


def resolve_industry_key(business_scope: str | None) -> str:
    """根据经营范围文本解析行业键：先最长子串匹配 INDUSTRY_PRODUCTS 键，再关键词回退，最后默认。"""
    scope = (business_scope or "").strip()
    if not scope:
        return DEFAULT_INDUSTRY_KEY

    keys = sorted(INDUSTRY_PRODUCTS.keys(), key=len, reverse=True)
    best: str | None = None
    for key in keys:
        if key in scope:
            best = key
            break
    if best:
        return best

    for kws, industry_key in KEYWORD_INDUSTRY_FALLBACK:
        if any(kw in scope for kw in kws):
            return industry_key

    return DEFAULT_INDUSTRY_KEY


def product_candidates_for_industry(industry_key: str) -> list[str]:
    return INDUSTRY_PRODUCTS.get(industry_key) or INDUSTRY_PRODUCTS[DEFAULT_INDUSTRY_KEY]


def fill_capacity_pair(capacity, max_capacity):
    """若两者皆空则成对生成；若仅一侧空则与另一侧协调。"""
    if not _empty_num(max_capacity) and not _empty_num(capacity):
        return capacity, max_capacity
    if _empty_num(max_capacity) and _empty_num(capacity):
        max_c = random.randint(8000, 12000)
        cap = random.randint(max(int(max_c * 0.5), 1), max_c)
        return cap, max_c
    if _empty_num(max_capacity) and not _empty_num(capacity):
        cap = int(capacity)
        max_c = random.randint(cap, max(cap * 2, cap + 1000))
        return cap, max_c
    # max 有值，capacity 空
    max_c = int(max_capacity)
    low = max(int(max_c * 0.5), 1)
    cap = random.randint(low, max_c)
    return cap, max_c


def enrich_enterprises(fake: Faker, verbose: bool) -> int:
    enterprises = Enterprise.query.order_by(Enterprise.id).all()
    n = len(enterprises)
    print(f"\n[第二部分] 补全 enterprises，共 {n} 条")
    updated = 0
    for i, e in enumerate(enterprises, 1):
        if verbose:
            print(f"  [{i}/{n}] id={e.id} {e.name!r}")
        changed = False
        if _empty_str(e.address):
            parts = [p for p in (e.province, e.city) if p and str(p).strip()]
            parts.append(fake.street_address())
            e.address = " ".join(parts)
            changed = True
        if _empty_str(e.contact):
            e.contact = fake.name()
            changed = True
        if _empty_str(e.phone):
            e.phone = fake.phone_number()[:20]
            changed = True
        if _empty_num(e.credit_score):
            e.credit_score = float(random.randint(70, 100))
            changed = True
        if _empty_num(e.registered_capital):
            e.registered_capital = round(random.uniform(100.0, 10000.0), 2)
            changed = True
        if _empty_num(e.capacity) or _empty_num(e.max_capacity):
            cap, max_c = fill_capacity_pair(e.capacity, e.max_capacity)
            e.capacity = cap
            e.max_capacity = max_c
            changed = True
        if changed:
            updated += 1
    db.session.commit()
    print(f"[第二部分] 完成，已更新 {updated} 家企业（含字段补全）")
    return updated


def seed_products(fake: Faker, force: bool, verbose: bool) -> int:
    enterprises = Enterprise.query.order_by(Enterprise.id).all()
    n = len(enterprises)
    print(f"\n[第三部分] 生成 products，企业数 {n}；force={force}")
    created = 0
    skipped = 0
    for i, e in enumerate(enterprises, 1):
        existing = Product.query.filter_by(enterprise_id=e.id).count()
        if existing > 0 and not force:
            skipped += 1
            if verbose:
                print(f"  [{i}/{n}] 跳过 id={e.id}（已有 {existing} 条产品，加 --force 可追加）")
            continue
        industry_key = resolve_industry_key(e.business_scope)
        pool = product_candidates_for_industry(industry_key)
        k = random.randint(1, min(3, len(pool)))
        names = random.sample(pool, k=k)
        if verbose:
            print(f"  [{i}/{n}] id={e.id} 行业={industry_key} 产品数={k}")
        for name in names:
            desc = fake.text(max_nb_chars=120).replace("\n", " ").strip()
            if len(desc) > 200:
                desc = desc[:200]
            p = Product(
                name=name[:100],
                description=desc,
                category=industry_key[:50],
                enterprise_id=e.id,
            )
            db.session.add(p)
            created += 1
    db.session.commit()
    print(f"[第三部分] 完成，新建 {created} 条产品；跳过 {skipped} 家企业（无 --force 且已有产品）")
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Faker 补全企业与生成产品数据")
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使该企业已有产品仍追加 1~3 条（默认仅对无产品企业插入）",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="逐条打印进度")
    args = parser.parse_args()

    fake = Faker("zh_CN")
    print("=" * 60)
    print("链易配 - Faker 填充 enterprises / products")
    print("=" * 60)

    try:
        app = create_app()
        with app.app_context():
            enrich_enterprises(fake, args.verbose)
            seed_products(fake, args.force, args.verbose)
    except Exception as ex:
        print(f"\n[错误] {ex}", file=sys.stderr)
        traceback.print_exc()
        try:
            db.session.rollback()
        except Exception:
            pass
        sys.exit(1)

    print("\n全部完成。")


if __name__ == "__main__":
    main()
