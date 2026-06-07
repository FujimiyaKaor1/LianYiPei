"""
种子数据脚本 - 为链易配平台生成基础演示数据

用法:
    python scripts/seed_data.py [--reset]

选项:
    --reset   清除现有数据后重新生成（谨慎使用）

生成内容:
    - 13 家企业（含管理员、链主、政府用户、演示 test1 / 测试账号1、政府专用登录名 admin）
    - 产品数据
    - 信用分历史
    - 询价单与报价
    - 价格指数
    - 质量标签
    - 消息通知
    - 预警记录
    - 撮合码与履约数据
"""

import sys
import os

# 确保项目根目录在 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from calendar import monthrange
from datetime import datetime, date, timedelta
import random
import uuid

from app import create_app, db
from app.models import (
    Enterprise,
    Product,
    Alert,
    Transaction,
    Inquiry,
    Quote,
    PriceIndex,
    Message,
    RecruitmentTask,
)
from config import DEFAULT_ALERT_THRESHOLDS, register_runtime_collab_api_key

app = create_app()


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _days_ago(n: int) -> datetime:
    return datetime.utcnow() - timedelta(days=n)


def _date_ago(n: int) -> date:
    return date.today() - timedelta(days=n)


# ---------------------------------------------------------------------------
# 清除数据
# ---------------------------------------------------------------------------

def reset_data():
    """删库表并重建（11 张核心表，与 models 一致）。"""
    print("⚠️  清除现有数据（drop_all + create_all）...")
    db.drop_all()
    db.create_all()
    print("✅ 数据已清除")


# ---------------------------------------------------------------------------
# 企业
# ---------------------------------------------------------------------------

def seed_enterprises():
    print("📦 创建企业...")
    enterprises_data = [
        # (name, role, is_admin, credit_score, city, province, is_lead)
        ("链易配管理员", "admin", True, 95.0, "深圳", "广东", False),
        ("华南链主科技有限公司", "enterprise", False, 92.0, "广州", "广东", True),
        ("政府产业监管局", "government", True, 88.0, "深圳", "广东", False),
        ("深圳精密制造有限公司", "enterprise", False, 85.0, "深圳", "广东", False),
        ("东莞电子元器件厂", "enterprise", False, 78.0, "东莞", "广东", False),
        ("佛山新材料科技公司", "enterprise", False, 72.0, "佛山", "广东", False),
        ("惠州绿色能源有限公司", "enterprise", False, 65.0, "惠州", "广东", False),
        ("中山光电设备公司", "enterprise", False, 58.0, "中山", "广东", False),
        ("珠海半导体研究院", "enterprise", False, 90.0, "珠海", "广东", False),
        ("江门新能源汽车配件厂", "enterprise", False, 55.0, "江门", "广东", False),
        # 演示企业账号：登录「企业名称」填 test1 或 测试账号1，密码 password123
        ("test1", "enterprise", False, 78.0, "深圳", "广东", False),
        ("测试账号1", "enterprise", False, 78.0, "深圳", "广东", False),
        # 管理员演示：登录「企业名称」填 admin，密码 123456
        ("admin", "admin", True, 92.0, "深圳", "广东", False),
    ]

    created = []
    for name, role, is_admin, score, city, province, is_lead in enterprises_data:
        e = Enterprise(
            name=name,
            role=role,
            is_admin=is_admin,
            credit_score=score,
            city=city,
            province=province,
            is_lead_enterprise=is_lead,
            daily_quote_count=0,
            daily_quote_limit=3 if score < 70 else 999,
            last_quote_reset_date=date.today(),
            data_freshness_score=random.uniform(60, 100),
            is_dormant=False,
            current_mode='seller',
            address=f"{province}{city}高新技术产业园",
            longitude=113.0 + random.uniform(-1, 1),
            latitude=23.0 + random.uniform(-1, 1),
            registered_capital=random.choice([500, 1000, 2000, 5000]),
            business_scope="电子元器件制造、精密加工、新能源设备",
            patent_count=random.randint(0, 50),
            created_at=_days_ago(random.randint(30, 365)),
            verification_status='approved',
            is_verified=True,
            registered_at=_days_ago(random.randint(30, 365)),
        )
        # 政府端与 admin 演示号统一用 123456，其余演示企业用 password123
        if name == "admin" or role == "government":
            e.set_password("123456")
        else:
            e.set_password("password123")
        db.session.add(e)
        created.append(e)

    db.session.flush()
    print(f"  ✅ 创建了 {len(created)} 家企业")
    return created


# ---------------------------------------------------------------------------
# 产品
# ---------------------------------------------------------------------------

def seed_products(enterprises):
    print("📦 创建产品...")
    product_data = [
        ("锂电池正极材料", "新能源材料", 1),
        ("精密齿轮组", "精密机械", 1),
        ("IGBT模块", "电子元器件", 2),
        ("铝合金外壳", "金属加工", 2),
        ("碳纤维复合材料", "新材料", 3),
        ("光伏逆变器", "新能源设备", 4),
        ("工业传感器", "电子元器件", 5),
        ("新能源汽车电机", "汽车配件", 6),
    ]
    products = []
    for name, category, ent_idx in product_data:
        if ent_idx < len(enterprises):
            p = Product(
                name=name,
                category=category,
                enterprise_id=enterprises[ent_idx].id,
                description=f"高品质{name}，符合国家标准",
                created_at=_days_ago(random.randint(10, 200)),
            )
            db.session.add(p)
            products.append(p)
    db.session.flush()
    print(f"  ✅ 创建了 {len(products)} 个产品")
    return products


# ---------------------------------------------------------------------------
# 信用分历史
# ---------------------------------------------------------------------------

def seed_credit_history(enterprises):
    print("📦 创建信用分历史...")
    change_types = [
        'fulfillment_on_time',
        'data_auth',
        'report_verified',
        'consecutive_bonus',
        'activity_inquiry',
    ]
    reasons = [
        "按时完成履约", "授权用电量数据", "被举报报价不实",
        "连续3次按时履约奖励", "数据过期扣分",
    ]
    count = 0
    for ent in enterprises[3:]:  # 跳过管理员账号
        for i in range(random.randint(3, 8)):
            change_val = random.choice([-10, -5, 5, 10, 15])
            old_score = max(0, min(100, ent.credit_score - change_val))
            ts = _days_ago(random.randint(1, 90))
            ts_str = ts.isoformat() + "Z" if hasattr(ts, "isoformat") else str(ts)
            ev = {
                "id": str(uuid.uuid4()),
                "old_score": float(old_score),
                "new_score": float(ent.credit_score),
                "change_value": float(change_val),
                "change_type": random.choice(change_types),
                "reason": random.choice(reasons),
                "created_at": ts_str,
            }
            rows = list(ent.credit_score_events) if isinstance(ent.credit_score_events, list) else []
            rows.append(ev)
            ent.credit_score_events = rows
            count += 1
    db.session.flush()
    print(f"  ✅ 创建了 {count} 条信用分历史")


# ---------------------------------------------------------------------------
# 询价单与报价
# ---------------------------------------------------------------------------

def seed_inquiries_and_quotes(enterprises, products):
    print("📦 创建询价单与报价...")
    product_names = ["锂电池正极材料", "IGBT模块", "精密齿轮组", "光伏逆变器", "工业传感器"]
    inquiries = []
    for i in range(8):
        buyer = enterprises[random.randint(3, 6)]
        seller = enterprises[random.randint(4, 9)]
        if buyer.id == seller.id:
            seller = enterprises[(seller.id % 6) + 3]
        inq = Inquiry(
            poster_id=buyer.id,
            direction='demand',
            buyer_id=buyer.id,
            seller_id=seller.id,
            product_name=random.choice(product_names),
            content="请报价，需要高品质产品，交货期30天内",
            status=random.choice(['open', 'sent', 'agreement_signed']),
            created_at=_days_ago(random.randint(1, 60)),
        )
        db.session.add(inq)
        inquiries.append(inq)
    db.session.flush()

    # 报价
    quote_count = 0
    for inq in inquiries:
        for _ in range(random.randint(1, 4)):
            supplier = enterprises[random.randint(3, 9)]
            q = Quote(
                inquiry_id=inq.id,
                supplier_id=supplier.id,
                product_name=inq.product_name,
                price=round(random.uniform(100, 5000), 2),
                quantity=random.randint(100, 10000),
                unit="个",
                delivery_days=random.randint(7, 45),
                status='active',
                created_at=_days_ago(random.randint(0, 30)),
            )
            db.session.add(q)
            quote_count += 1
    db.session.flush()
    print(f"  ✅ 创建了 {len(inquiries)} 条询价单，{quote_count} 条报价")
    return inquiries


# ---------------------------------------------------------------------------
# 价格指数
# ---------------------------------------------------------------------------

def seed_price_indices():
    print("📦 创建价格指数...")
    products = [
        ("锂电池正极材料", 850, 120),
        ("IGBT模块", 320, 60),
        ("精密齿轮组", 180, 40),
        ("光伏逆变器", 2500, 400),
        ("工业传感器", 450, 80),
        ("碳纤维复合材料", 1200, 200),
        ("新能源汽车电机", 3800, 600),
    ]
    for name, median, std in products:
        pi = PriceIndex(
            product_name=name,
            median_price=median,
            mean_price=median * 1.05,
            std_dev=std,
            min_price=median - 2 * std,
            max_price=median + 2 * std,
            sample_count=random.randint(5, 50),
            data_source='realtime',
            last_updated=_days_ago(random.randint(0, 3)),
        )
        db.session.add(pi)
    db.session.flush()
    print(f"  ✅ 创建了 {len(products)} 条价格指数")


# ---------------------------------------------------------------------------
# 质量标签
# ---------------------------------------------------------------------------

def seed_quality_labels(enterprises):
    print("📦 创建质量标签（Enterprise.qualifications）...")
    count = 0
    for ent in enterprises[3:7]:
        rows = list(ent.qualifications) if isinstance(ent.qualifications, list) else []
        rows.append(
            {
                'id': ent.id * 100 + len(rows) + 1,
                'label_type': random.choice(
                    ['government_green', 'lead_inspection', 'third_party']
                ),
                'label_name': random.choice(
                    ["ISO9001认证", "绿色工厂认证", "链主验厂通过", "AA级信用评级"]
                ),
                'issuer_id': enterprises[1].id,
                'valid_from': _date_ago(180).isoformat(),
                'valid_until': (date.today() + timedelta(days=180)).isoformat(),
                'status': 'active',
                'created_at': _days_ago(180).isoformat(),
            }
        )
        ent.qualifications = rows
        count += 1
    db.session.flush()
    print(f"  ✅ 创建了 {count} 条质量标签")


# ---------------------------------------------------------------------------
# 数据授权
# ---------------------------------------------------------------------------

def seed_data_authorizations(enterprises):
    print("📦 创建数据授权（Enterprise.data_auth）...")
    count = 0
    for ent in enterprises[3:8]:
        auth = dict(ent.data_auth) if isinstance(ent.data_auth, dict) else {}
        for dtype in ['power_consumption', 'invoice_data']:
            if random.random() > 0.4:
                auth[dtype] = {
                    'authorized': True,
                    'authorized_at': _days_ago(random.randint(10, 90)).isoformat(),
                    'last_sync_at': _days_ago(random.randint(0, 7)).isoformat(),
                    'sync_status': 'success',
                }
                count += 1
        ent.data_auth = auth
    db.session.flush()
    print(f"  ✅ 创建了 {count} 条数据授权")


# ---------------------------------------------------------------------------
# 消息
# ---------------------------------------------------------------------------

def seed_messages(enterprises):
    print("📦 创建消息...")
    msg_data = [
        ("transaction", "新报价通知", "您的询价单收到了新报价，请及时查看。"),
        ("alert", "产能风险预警", "检测到供应链断链风险，请关注。"),
        ("system", "系统通知", "平台规则已更新，请查阅最新版本。"),
        ("credit", "信用分变动", "您的信用分因按时履约增加了5分。"),
    ]
    count = 0
    for ent in enterprises[3:]:
        for mtype, title, content in random.sample(msg_data, k=random.randint(1, 3)):
            m = Message(
                recipient_id=ent.id,
                message_type=mtype,
                title=title,
                content=content,
                is_read=random.choice([True, False]),
                priority='high' if mtype == 'alert' else 'normal',
                created_at=_days_ago(random.randint(0, 30)),
            )
            db.session.add(m)
            count += 1
    db.session.flush()
    print(f"  ✅ 创建了 {count} 条消息")


# ---------------------------------------------------------------------------
# 预警
# ---------------------------------------------------------------------------

def seed_alerts(enterprises):
    print("📦 创建预警记录...")
    alerts_data = [
        ("锂电池正极材料", "上游供应商仅2家，存在供应链断链风险", "red", "supply_chain"),
        ("IGBT模块", "产能利用率达92%，交货周期延长风险", "yellow", "capacity"),
        ("精密齿轮组", "某供应商信用分7天内下降18分", "red", "credit_anomaly"),
        ("光伏逆变器", "本地供应商占比仅25%，低于30%阈值", "yellow", "supply_chain"),
        ("工业传感器", "进口依赖度高达65%，存在供应风险", "blue", "business_risk"),
    ]
    alerts = []
    for product, msg, level, dimension in alerts_data:
        a = Alert(
            product_name=product,
            message=msg,
            level=level,
            dimension=dimension,
            is_active=True,
            suggestion=f"建议针对{product}开展补链招商工作",
            created_at=_days_ago(random.randint(0, 14)),
        )
        db.session.add(a)
        alerts.append(a)
    db.session.flush()

    thresholds = [
        ("supply_chain", 3.0),
        ("capacity", 0.85),
        ("credit_anomaly", 15.0),
        ("local_ratio", 0.3),
    ]
    for dim, val in thresholds:
        DEFAULT_ALERT_THRESHOLDS[dim] = val

    db.session.flush()
    print(f"  ✅ 创建了 {len(alerts)} 条预警，{len(thresholds)} 条阈值写入 config")
    return alerts


# ---------------------------------------------------------------------------
# 撮合码与履约数据
# ---------------------------------------------------------------------------

def seed_collaboration_codes(enterprises):
    print("📦 创建撮合码与履约数据（Transaction）...")
    codes = []
    for i in range(5):
        buyer = enterprises[random.randint(3, 6)]
        seller = enterprises[random.randint(4, 9)]
        cid = f"CONTRACT-{i+1:04d}"
        code_str = Transaction.generate_match_code(buyer.id, seller.id, cid)
        fs = random.choice(['pending', 'fulfilled'])
        inv = {
            'contract_id': cid,
            'amount_range': random.choice(["10-50万", "50-100万", "100-500万"]),
            'valid_until': (datetime.utcnow() + timedelta(days=365)).isoformat(),
        }
        if fs == 'fulfilled':
            inv.update(
                {
                    'invoice_no': f"INV-{random.randint(10000, 99999)}",
                    'invoice_amount': random.uniform(100000, 5000000),
                    'on_time': random.choice([True, True, True, False]),
                    'quality_rating': random.randint(3, 5),
                    'verified': True,
                }
            )
        cc = Transaction(
            buyer_id=buyer.id,
            seller_id=seller.id,
            product_name=random.choice(["锂电池正极材料", "IGBT模块", "精密齿轮组"]),
            status='pending',
            match_code=code_str,
            invoice_info=inv,
            fulfillment_status=fs,
            created_at=_days_ago(random.randint(10, 90)),
        )
        db.session.add(cc)
        codes.append((cc, buyer, seller))

    db.session.flush()
    print(f"  ✅ 创建了 {len(codes)} 条撮合/履约 Transaction")


# ---------------------------------------------------------------------------
# 合作案例库
# ---------------------------------------------------------------------------

def seed_case_library(enterprises):
    print("📦 创建合作案例库（Enterprise.cooperation_cases）...")
    masked_buyers = ["某世界500强企业", "某上市新能源公司", "某知名汽车主机厂", "某头部电子制造商"]
    count = 0
    for ent in enterprises[3:7]:
        cases = list(ent.cooperation_cases) if isinstance(ent.cooperation_cases, list) else []
        for j in range(random.randint(1, 3)):
            cases.append(
                {
                    'id': f"case_{ent.id}_{count}",
                    'buyer_name_masked': random.choice(masked_buyers),
                    'product_category': random.choice(["电子元器件", "新能源材料", "精密机械"]),
                    'cooperation_time': f"2024年Q{random.randint(1, 4)}",
                    'amount_range': random.choice(["10-50万", "50-100万"]),
                    'is_public': random.choice([True, False]),
                    'created_at': _days_ago(random.randint(30, 180)).isoformat(),
                }
            )
            count += 1
        ent.cooperation_cases = cases
    db.session.flush()
    print(f"  ✅ 创建了 {count} 条合作案例")


# ---------------------------------------------------------------------------
# 招商任务
# ---------------------------------------------------------------------------

def seed_recruitment_tasks(enterprises):
    print("📦 创建招商任务...")
    tasks_data = [
        ("引进锂电池正极材料供应商", "锂电池正极材料", "宁德时代系供应商", "福建"),
        ("引进IGBT模块制造商", "IGBT模块", "英飞凌合作伙伴", "上海"),
        ("引进碳纤维复合材料企业", "碳纤维复合材料", "东丽系供应商", "北京"),
    ]
    for name, product, target_name, location in tasks_data:
        t = RecruitmentTask(
            task_name=name,
            target_product=product,
            target_enterprise_name=target_name,
            target_enterprise_location=location,
            assigned_to=enterprises[2].id,
            assigned_by=enterprises[0].id,
            priority='high',
            status=random.choice(['pending', 'contacted', 'negotiating']),
            deadline=date.today() + timedelta(days=random.randint(30, 90)),
            created_at=_days_ago(random.randint(5, 30)),
        )
        db.session.add(t)
    db.session.flush()
    print(f"  ✅ 创建了 {len(tasks_data)} 条招商任务")


# ---------------------------------------------------------------------------
# API密钥
# ---------------------------------------------------------------------------

def seed_api_keys():
    print("📦 登记协作 API 密钥（config 运行时列表，原 api_keys 表已移除）...")
    keys_data = [
        "招商银行供应链金融",
        "平安银行贸易融资",
        "政府数据接口",
    ]
    for name in keys_data:
        register_runtime_collab_api_key(name)
    print(f"  ✅ 登记了 {len(keys_data)} 个 API 密钥（进程内有效）")


# ---------------------------------------------------------------------------
# 操作日志
# ---------------------------------------------------------------------------

def seed_operation_logs(enterprises):
    print("📦 操作日志（已改为 logging app.ops，跳过落库）")


# ---------------------------------------------------------------------------
# 演示看板：履约 / 产能日历 / 集采（重复执行会先清理 DEMO-FUL 履约与同名集采再写入，saas_orders 当月覆盖）
# ---------------------------------------------------------------------------

def _find_enterprise(enterprises, *names):
    for n in names:
        for e in enterprises:
            if e.name == n:
                return e
    for e in enterprises:
        if getattr(e, "role", None) == "enterprise" and not e.is_admin:
            return e
    return enterprises[0]


def _clear_demo_board_seed(seller: Enterprise, gp_titles: list[str]) -> None:
    """重复执行时先清理本脚本写入的演示数据，避免拼单/履约无限叠加。"""
    to_del = [
        t
        for t in Transaction.query.filter_by(seller_id=seller.id).all()
        if isinstance(t.invoice_info, dict)
        and str(t.invoice_info.get("contract_id") or "").startswith("DEMO-FUL-")
    ]
    for t in to_del:
        db.session.delete(t)
    if to_del:
        print(f"  🧹 已移除 {len(to_del)} 条旧演示履约 Transaction（DEMO-FUL-*）")

    q = Inquiry.query.filter(
        Inquiry.poster_id == seller.id,
        Inquiry.is_group_buy == True,  # noqa: E712
        Inquiry.status == "open",
        Inquiry.product_name.in_(gp_titles),
    )
    n_gp = q.delete(synchronize_session=False)
    if n_gp:
        print(f"  🧹 已移除 {n_gp} 条旧演示集采 Inquiry")


def seed_demo_boards(enterprises):
    """为 test1 / 深圳精密 灌入：进行中履约、当月产能排期、开放集采拼单。"""
    print("📦 演示看板数据（履约 / 产能 / 集采）...")
    seller = _find_enterprise(enterprises, "test1", "深圳精密制造有限公司")
    buyers = [e for e in enterprises if e.id != seller.id and e.role == "enterprise"][:8]
    if not buyers:
        buyers = [enterprises[0]]

    gp_titles = [
        "高压屏蔽线缆联合采购",
        "锂电铜箔集采拼单",
        "工业连接器年度锁价",
        "伺服电机批量议价",
        "液冷板联合招标",
        "MCU 芯片拼单",
        "结构件钣金集中采购",
        "IGBT 模块团购",
    ]
    _clear_demo_board_seed(seller, gp_titles)

    statuses_cycle = ["pending", "invoiced", "delivered", "pending", "invoiced", "delivered", "pending", "invoiced", "delivered", "pending"]
    products = [
        "高压屏蔽线缆",
        "IGBT 模块",
        "精密齿轮组",
        "锂电铜箔",
        "工业连接器",
        "伺服电机",
        "碳纤维板",
        "液冷板",
        "MCU 芯片",
        "结构件钣金",
    ]
    for i in range(10):
        buyer = buyers[i % len(buyers)]
        st = statuses_cycle[i]
        inv = {
            "contract_id": f"DEMO-FUL-{seller.id}-{i}",
            "invoice_amount": float(random.randint(50, 500) * 1000),
            "paid_amount": float(random.randint(10, 200) * 1000),
            "verified": False,
            "on_time": True,
            "qc_status": random.choice(["pending", "passed", "pending"]),
            "payment_progress": random.randint(15, 85),
            "logistics": {
                "nodes": [
                    {"label": "已发货", "done": st in ("delivered", "invoiced")},
                    {"label": "在途", "done": st == "delivered"},
                    {"label": "已签收", "done": False},
                ],
                "current": "在途" if st == "invoiced" else "仓储",
            },
            "logistics_nodes": [
                {"label": "发货", "done": True},
                {"label": "在途", "done": st != "pending"},
                {"label": "签收", "done": False},
            ],
        }
        code_str = Transaction.generate_match_code(buyer.id, seller.id, inv["contract_id"])
        tx = Transaction(
            buyer_id=buyer.id,
            seller_id=seller.id,
            product_name=products[i],
            status="pending",
            match_code=code_str,
            invoice_info=inv,
            fulfillment_status=st,
            created_at=_days_ago(random.randint(1, 20)),
        )
        db.session.add(tx)

    # 当月产能：Enterprise.extras.saas_orders + max_capacity
    today = date.today()
    y, m = today.year, today.month
    _, last_d = monthrange(y, m)
    saas_orders = []
    oid = 1
    for day in range(1, last_d + 1):
        n_touch = random.randint(0, 5)
        for _ in range(n_touch):
            d = date(y, m, day)
            saas_orders.append(
                {
                    "id": oid,
                    "order_no": f"SAAS{y}{m:02d}{oid:04d}",
                    "product_name": random.choice(["定制件", "批量加工", "模组"]),
                    "quantity": random.randint(10, 500),
                    "unit": "件",
                    "customer_name": random.choice(["客户A", "客户B", "客户C"]),
                    "order_date": d.isoformat(),
                    "delivery_date": d.isoformat(),
                    "status": random.choice(["pending", "in_progress"]),
                    "notes": "seed 产能日历",
                }
            )
            oid += 1

    ex = dict(seller.extras) if isinstance(seller.extras, dict) else {}
    ex["saas_orders"] = saas_orders
    seller.extras = ex
    seller.max_capacity = 5
    seller.current_orders = sum(
        1 for r in saas_orders if r.get("status") in ("pending", "in_progress")
    )

    # 集采拼单：Inquiry.is_group_buy
    poster = seller
    for j, title in enumerate(random.sample(gp_titles, k=min(8, len(gp_titles)))):
        tq = random.randint(5000, 50000)
        cq = int(tq * random.uniform(0.35, 0.72))
        dl = datetime.utcnow() + timedelta(days=random.randint(3, 21))
        gb = {
            "deadline": dl.isoformat() + "Z",
            "min_credit_score": 60.0,
            "target_quantity": tq,
            "current_quantity": cq,
            "participant_count": random.randint(2, 12),
        }
        inq = Inquiry(
            poster_id=poster.id,
            direction="demand",
            product_name=title,
            quantity=tq,
            status="open",
            is_group_buy=True,
            group_members=[
                {
                    "enterprise_id": poster.id,
                    "quantity": min(cq, 5000),
                    "joined_at": datetime.utcnow().isoformat() + "Z",
                }
            ],
            match_context={"group_buy": gb},
            created_at=_days_ago(random.randint(0, 5)),
        )
        db.session.add(inq)

    db.session.flush()
    print(f"  ✅ 演示看板：10 条进行中履约（卖方 {seller.name}）、{len(saas_orders)} 条 SaaS 排期、8 条集采")


def run_demo_boards_only():
    """在已有库上仅灌演示看板数据（不 reset）。"""
    with app.app_context():
        ents = Enterprise.query.filter_by(role="enterprise").all()
        if not ents:
            print("❌ 无企业数据，请先运行 python scripts/seed_data.py")
            return
        seed_demo_boards(ents)
        db.session.commit()
        print("\n✅ 演示看板数据已写入（可刷新前端验证）。")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def run_seed(reset: bool = False):
    with app.app_context():
        if reset:
            reset_data()

        print("\n🌱 开始生成种子数据...\n")
        try:
            enterprises = seed_enterprises()
            products = seed_products(enterprises)
            seed_credit_history(enterprises)
            inquiries = seed_inquiries_and_quotes(enterprises, products)
            seed_price_indices()
            seed_quality_labels(enterprises)
            seed_data_authorizations(enterprises)
            seed_messages(enterprises)
            alerts = seed_alerts(enterprises)
            seed_collaboration_codes(enterprises)
            seed_case_library(enterprises)
            seed_recruitment_tasks(enterprises)
            seed_api_keys()
            seed_operation_logs(enterprises)
            seed_demo_boards(enterprises)

            db.session.commit()
            print("\n✅ 种子数据生成完成！")
            print(f"   管理员账号: 链易配管理员 / password123")
            print(f"   企业账号示例: 深圳精密制造有限公司 / password123")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ 种子数据生成失败: {e}")
            raise


if __name__ == '__main__':
    if '--demo-boards-only' in sys.argv:
        run_demo_boards_only()
    else:
        reset_flag = '--reset' in sys.argv
        run_seed(reset=reset_flag)
