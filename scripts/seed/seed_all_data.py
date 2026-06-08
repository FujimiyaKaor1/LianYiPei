"""
链易配 - 完整数据初始化脚本
一键初始化 MySQL + Neo4j，包含企业画像、产品、供需、交易、预警、进口依赖度、专利等
"""
import sys
import os
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# GB/T 4754 行业编码（制造业）
INDUSTRY_CODES = [
    ('C32', '黑色金属冶炼和压延加工业'),
    ('C33', '金属制品业'),
    ('C34', '通用设备制造业'),
    ('C35', '专用设备制造业'),
    ('C36', '汽车制造业'),
    ('C37', '电气机械和器材制造业'),
    ('C38', '计算机、通信和电子设备制造业'),
    ('C39', '仪器仪表制造业'),
]

ENTERPRISES = [
    {'name': '成都精密机械制造有限公司', 'address': '四川省成都市高新区天府大道100号',
     'longitude': 104.0657, 'latitude': 30.6595, 'contact': '张经理', 'phone': '13800138001',
     'registered_capital': 5000, 'business_scope': '精密机械、数控机床、工业机器人研发与制造',
     'province': '四川', 'patent_count': 15, 'patent_category': '发明专利,实用新型',
     'tech_keywords': '数控机床,精密加工,自动化', 'rd_investment': 320},
    {'name': '绵阳电子科技有限公司', 'address': '四川省绵阳市涪城区科创园路50号',
     'longitude': 104.7417, 'latitude': 31.4640, 'contact': '李总', 'phone': '13800138002',
     'registered_capital': 3000, 'business_scope': '电子元器件、电路板、智能传感器',
     'province': '四川', 'patent_count': 8, 'patent_category': '实用新型',
     'tech_keywords': 'PCB,传感器,物联网', 'rd_investment': 180},
    {'name': '德阳重型装备集团', 'address': '四川省德阳市旌阳区工业大道200号',
     'longitude': 104.3979, 'latitude': 31.1267, 'contact': '王主任', 'phone': '13800138003',
     'registered_capital': 15000, 'business_scope': '重型机械、液压设备、工程机械',
     'province': '四川', 'patent_count': 25, 'patent_category': '发明专利',
     'tech_keywords': '液压缸,工程机械,重型装备', 'rd_investment': 580},
    {'name': '宜宾新材料科技公司', 'address': '四川省宜宾市翠屏区临港大道150号',
     'longitude': 104.6308, 'latitude': 28.7604, 'contact': '赵经理', 'phone': '13800138004',
     'registered_capital': 8000, 'business_scope': '铝合金型材、特种合金、新材料',
     'province': '四川', 'patent_count': 12, 'patent_category': '发明专利,实用新型',
     'tech_keywords': '铝合金,特种钢材,新材料', 'rd_investment': 450},
    {'name': '泸州机械零部件厂', 'address': '四川省泸州市江阳区工业园区88号',
     'longitude': 105.4433, 'latitude': 28.8891, 'contact': '孙总', 'phone': '13800138005',
     'registered_capital': 2000, 'business_scope': '精密轴承、密封件、机械零部件',
     'province': '四川', 'patent_count': 5, 'patent_category': '实用新型',
     'tech_keywords': '轴承,密封件,零部件', 'rd_investment': 90},
    {'name': '自贡精密模具有限公司', 'address': '四川省自贡市自流井区工业路66号',
     'longitude': 104.7785, 'latitude': 29.3398, 'contact': '周经理', 'phone': '13800138006',
     'registered_capital': 1800, 'business_scope': '精密模具、注塑件、冲压件',
     'province': '四川', 'patent_count': 6, 'patent_category': '实用新型',
     'tech_keywords': '模具,注塑,冲压', 'rd_investment': 120},
    {'name': '攀枝花钢铁配件公司', 'address': '四川省攀枝花市东区钢铁大道1号',
     'longitude': 101.7186, 'latitude': 26.5820, 'contact': '吴总', 'phone': '13800138007',
     'registered_capital': 6000, 'business_scope': '特种钢材、钢铁配件、金属加工',
     'province': '四川', 'patent_count': 10, 'patent_category': '发明专利',
     'tech_keywords': '特种钢材,钢铁,金属', 'rd_investment': 200},
    {'name': '乐山电机设备厂', 'address': '四川省乐山市市中区高新区路99号',
     'longitude': 103.7656, 'latitude': 29.5521, 'contact': '郑经理', 'phone': '13800138008',
     'registered_capital': 3500, 'business_scope': '电机、变压器、电气设备',
     'province': '四川', 'patent_count': 9, 'patent_category': '发明专利,实用新型',
     'tech_keywords': '电机,变压器,电气', 'rd_investment': 260},
    {'name': '南充汽车零部件公司', 'address': '四川省南充市顺庆区工业集中区55号',
     'longitude': 106.1106, 'latitude': 30.8370, 'contact': '钱总', 'phone': '13800138009',
     'registered_capital': 4200, 'business_scope': '汽车零部件、减速机、传动件',
     'province': '四川', 'patent_count': 7, 'patent_category': '实用新型',
     'tech_keywords': '汽车零部件,减速机,传动', 'rd_investment': 150},
    {'name': '达州电子元器件厂', 'address': '四川省达州市通川区产业园区77号',
     'longitude': 107.5022, 'latitude': 31.2090, 'contact': '冯经理', 'phone': '13800138010',
     'registered_capital': 2500, 'business_scope': '电阻电容、芯片封装、电子元器件',
     'province': '四川', 'patent_count': 4, 'patent_category': '实用新型',
     'tech_keywords': '电阻,电容,芯片', 'rd_investment': 110},
]

PRODUCTS = [
    {'name': '电机', 'category': '机械部件', 'industry_code': 'C37'},
    {'name': '电路板', 'category': '电子元件', 'industry_code': 'C38'},
    {'name': '特种钢材', 'category': '原材料', 'industry_code': 'C32'},
    {'name': '精密轴承', 'category': '零部件', 'industry_code': 'C33'},
    {'name': '芯片', 'category': '电子元件', 'industry_code': 'C38'},
    {'name': '高端传感器', 'category': '电子元件', 'industry_code': 'C38'},
    {'name': '液压缸', 'category': '机械部件', 'industry_code': 'C34'},
    {'name': '铝合金型材', 'category': '原材料', 'industry_code': 'C32'},
    {'name': '减速机', 'category': '机械部件', 'industry_code': 'C34'},
    {'name': '变压器', 'category': '电子元件', 'industry_code': 'C37'},
    {'name': '工业机器人', 'category': '机械部件', 'industry_code': 'C34'},
    {'name': '数控机床', 'category': '机械部件', 'industry_code': 'C34'},
    {'name': '模具', 'category': '零部件', 'industry_code': 'C35'},
    {'name': '密封件', 'category': '零部件', 'industry_code': 'C33'},
]

IMPORT_RISKS = [
    {'product_name': '芯片', 'import_ratio': 0.85, 'source_countries': '台湾,韩国,日本', 'hs_code': '8542', 'data_source': '海关总署'},
    {'product_name': '光刻机', 'import_ratio': 0.92, 'source_countries': '荷兰,日本', 'hs_code': '8486', 'data_source': '海关总署'},
    {'product_name': '高端传感器', 'import_ratio': 0.72, 'source_countries': '德国,日本,美国', 'hs_code': '9033', 'data_source': '海关总署'},
    {'product_name': '特种钢材', 'import_ratio': 0.48, 'source_countries': '日本,德国', 'hs_code': '7225', 'data_source': '海关总署'},
    {'product_name': '精密轴承', 'import_ratio': 0.58, 'source_countries': '德国,日本', 'hs_code': '8482', 'data_source': '海关总署'},
]


def seed_mysql(app):
    from app import db
    from app.models import Enterprise, Product, Inquiry, Transaction
    from config import DEFAULT_ALERT_THRESHOLDS

    with app.app_context():
        db.create_all()

        # 若已有企业数据，仅补充管理员和配置表
        if Enterprise.query.count() > 0:
            print("  [MySQL] 检测到已有数据，跳过企业/产品/供需/交易种子")
            admin = Enterprise.query.filter_by(is_admin=True).first()
            if not admin:
                admin = Enterprise(
                    name='admin',
                    address='系统管理员',
                    contact='管理员',
                    phone='00000000000',
                    is_admin=True,
                    role='admin',
                    credit_score=100,
                )
                admin.set_password('admin')
                db.session.add(admin)
                db.session.commit()
                print("  [MySQL] 已创建管理员 admin / admin")
            if not Enterprise.query.filter_by(name='test_ent').first():
                te = Enterprise(
                    name='test_ent',
                    address='测试企业',
                    contact='测试',
                    phone='13900000001',
                    credit_score=80.0,
                    capacity=60,
                    role='enterprise',
                )
                te.set_password('123456')
                db.session.add(te)
                db.session.commit()
                print("  [MySQL] 已创建企业账号 test_ent / 123456")
            # 政府端 SPA：须 role=government；与 scripts/seed_data.py 一致
            if not Enterprise.query.filter_by(role='government').first():
                gov = Enterprise(
                    name='政府产业监管局',
                    address='广东省深圳市（监管演示）',
                    contact='监管',
                    phone='00000000002',
                    role='government',
                    is_admin=True,
                    credit_score=88.0,
                    province='广东',
                    city='深圳',
                    verification_status='approved',
                    is_verified=True,
                )
                gov.set_password('123456')
                db.session.add(gov)
                db.session.commit()
                print("  [MySQL] 已创建政府账号 政府产业监管局 / 123456")
            for row in Enterprise.query.filter_by(is_admin=True).all():
                if getattr(row, 'role', None) != 'admin':
                    row.role = 'admin'
            db.session.commit()
            # 补充产品进口依赖 JSON（尚无 import_risk 的产品）
            need_risk = False
            for r in IMPORT_RISKS:
                p = Product.query.filter_by(name=r['product_name']).first()
                if p and not p.import_risk:
                    p.import_risk = {
                        'import_ratio': r['import_ratio'],
                        'source_countries': r['source_countries'],
                        'hs_code': r['hs_code'],
                        'data_source': r['data_source'],
                    }
                    need_risk = True
            if need_risk:
                db.session.commit()
                print("  [MySQL] 已补充产品 import_risk JSON")
            return

        print("  [MySQL] 创建企业...")
        for e in ENTERPRISES:
            ent = Enterprise(
                name=e['name'], address=e['address'], longitude=e['longitude'], latitude=e['latitude'],
                contact=e['contact'], phone=e['phone'],
                credit_score=round(random.uniform(65, 95), 1),
                capacity=random.randint(30, 120),
                registered_capital=e.get('registered_capital'),
                business_scope=e.get('business_scope'),
                province=e.get('province'),
                patent_count=e.get('patent_count'),
                patent_category=e.get('patent_category'),
                tech_keywords=e.get('tech_keywords'),
                rd_investment=e.get('rd_investment'),
                industry_code=random.choice(INDUSTRY_CODES)[0],
                role='enterprise',
            )
            ent.set_password('123456')
            db.session.add(ent)
        db.session.commit()

        print("  [MySQL] 创建产品...")
        enterprises = Enterprise.query.filter_by(role='enterprise').all()
        for ent in enterprises:
            selected = random.sample(PRODUCTS, random.randint(2, 5))
            for p in selected:
                prod = Product(
                    name=p['name'], category=p['category'], industry_code=p.get('industry_code'),
                    enterprise_id=ent.id
                )
                db.session.add(prod)
        db.session.commit()

        print("  [MySQL] 创建询盘/供需（Inquiry）...")
        products = Product.query.all()
        units = ['件', '台', '吨', '千克', '套', '批']
        for prod in products:
            if random.random() > 0.45:
                db.session.add(Inquiry(
                    poster_id=prod.enterprise_id,
                    direction='supply',
                    product_id=prod.id,
                    product_name=prod.name,
                    quantity=random.randint(20, 800),
                    unit=random.choice(units),
                    description=f"供应{prod.name}，质量保证",
                    status='open',
                ))
            if random.random() > 0.55:
                db.session.add(Inquiry(
                    poster_id=prod.enterprise_id,
                    direction='demand',
                    product_id=prod.id,
                    product_name=prod.name,
                    quantity=random.randint(10, 400),
                    unit=random.choice(units),
                    description=f"求购{prod.name}",
                    status='open',
                ))
        db.session.commit()

        print("  [MySQL] 创建交易历史...")
        for _ in range(25):
            sellers = [p for p in products if p.enterprise_id != enterprises[0].id]
            if not sellers:
                break
            p = random.choice(sellers)
            seller_ent = Enterprise.query.get(p.enterprise_id)
            buyer_ent = random.choice([e for e in enterprises if e.id != seller_ent.id])
            if buyer_ent:
                db.session.add(Transaction(
                    buyer_id=buyer_ent.id, seller_id=seller_ent.id, product_name=p.name,
                    quantity=random.randint(5, 200), price=round(random.uniform(10, 500), 2),
                    status='completed',
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 90))
                ))
        db.session.commit()

        print("  [MySQL] 写入产品进口依赖（import_risk JSON）...")
        for r in IMPORT_RISKS:
            for p in Product.query.filter_by(name=r['product_name']).all():
                if not p.import_risk:
                    p.import_risk = {
                        'import_ratio': r['import_ratio'],
                        'source_countries': r['source_countries'],
                        'hs_code': r['hs_code'],
                        'data_source': r['data_source'],
                    }
        db.session.commit()

        print("  [MySQL] 同步预警阈值到 config.DEFAULT_ALERT_THRESHOLDS（内存）...")
        DEFAULT_ALERT_THRESHOLDS.setdefault('import', 0.6)
        DEFAULT_ALERT_THRESHOLDS.setdefault('interprovincial', 0.7)
        DEFAULT_ALERT_THRESHOLDS.setdefault('local', 3)

        print("  [MySQL] 创建管理员...")
        admin = Enterprise(
            name='admin',
            address='系统管理员',
            contact='管理员',
            phone='00000000000',
            is_admin=True,
            role='admin',
            credit_score=100,
        )
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()

        print("  [MySQL] 创建政府监管账号（链易配政府端 /gov）...")
        gov = Enterprise(
            name='政府产业监管局',
            address='广东省深圳市（监管演示）',
            contact='监管',
            phone='00000000002',
            role='government',
            is_admin=True,
            credit_score=88.0,
            province='广东',
            city='深圳',
            verification_status='approved',
            is_verified=True,
        )
        gov.set_password('123456')
        db.session.add(gov)
        db.session.commit()

        print("  [MySQL] 创建固定企业测试账号 test_ent...")
        test_ent = Enterprise(
            name='test_ent',
            address='测试企业',
            contact='测试',
            phone='13900000001',
            credit_score=80.0,
            capacity=60,
            role='enterprise',
        )
        test_ent.set_password('123456')
        db.session.add(test_ent)
        db.session.commit()

        # 示例专利数据（Enterprise.patents JSON）
        print("  [MySQL] 创建示例专利...")
        for ent in enterprises[:3]:
            rows = list(ent.patents) if isinstance(ent.patents, list) else []
            for i in range(2):
                rows.append({
                    'patent_no': f'CN2023100{ent.id}{i}',
                    'title': f'{ent.name}专利{i+1}',
                    'patent_type': '实用新型',
                    'ipc_code': 'F16C',
                    'apply_date': (datetime.now().date() - timedelta(days=365)).isoformat(),
                })
            ent.patents = rows
        db.session.commit()

        print("  [MySQL] 种子数据完成！")


def seed_neo4j(app):
    from app.services.graph_manager import get_driver, clear_all_products, import_relations_from_csv, create_index

    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'relations.csv')
    if not os.path.exists(csv_path):
        print("  [Neo4j] 未找到 data/relations.csv，跳过")
        return

    driver = get_driver()
    if not driver:
        print("  [Neo4j] 连接失败，请确保 Neo4j Desktop 已启动且 bolt://localhost:7687 可访问")
        return

    print("  [Neo4j] 清空现有图谱...")
    clear_all_products()
    print("  [Neo4j] 导入产业链关系...")
    count = import_relations_from_csv(csv_path)
    create_index()
    print(f"  [Neo4j] 导入 {count} 条关系完成！")


def main():
    from app import create_app

    print("=" * 50)
    print("链易配 - 完整数据初始化")
    print("=" * 50)
    app = create_app()

    print("\n[1/2] MySQL 数据...")
    seed_mysql(app)

    print("\n[2/2] Neo4j 图谱...")
    seed_neo4j(app)

    print("\n" + "=" * 50)
    print("初始化完成！")
    print("  政府端（/gov）: 企业名称「政府产业监管局」/ 密码 123456")
    print("  管理员后台: 企业名称「admin」/ 密码 admin")
    print("  企业测试号: test_ent / 123456")
    print("  访问: http://localhost:5000")
    print("=" * 50)


if __name__ == '__main__':
    main()
