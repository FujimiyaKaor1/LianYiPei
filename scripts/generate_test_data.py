import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Enterprise, Product, Inquiry
import random

ENTERPRISES = [
    {'name': '成都精密机械制造有限公司', 'address': '四川省成都市高新区天府大道100号', 'longitude': 104.0657, 'latitude': 30.6595, 'contact': '张经理', 'phone': '13800138001'},
    {'name': '绵阳电子科技有限公司', 'address': '四川省绵阳市涪城区科创园路50号', 'longitude': 104.7417, 'latitude': 31.4640, 'contact': '李总', 'phone': '13800138002'},
    {'name': '德阳重型装备集团', 'address': '四川省德阳市旌阳区工业大道200号', 'longitude': 104.3979, 'latitude': 31.1267, 'contact': '王主任', 'phone': '13800138003'},
    {'name': '宜宾新材料科技公司', 'address': '四川省宜宾市翠屏区临港大道150号', 'longitude': 104.6308, 'latitude': 28.7604, 'contact': '赵经理', 'phone': '13800138004'},
    {'name': '泸州机械零部件厂', 'address': '四川省泸州市江阳区工业园区88号', 'longitude': 105.4433, 'latitude': 28.8891, 'contact': '孙总', 'phone': '13800138005'},
    {'name': '自贡精密模具有限公司', 'address': '四川省自贡市自流井区工业路66号', 'longitude': 104.7785, 'latitude': 29.3398, 'contact': '周经理', 'phone': '13800138006'},
    {'name': '攀枝花钢铁配件公司', 'address': '四川省攀枝花市东区钢铁大道1号', 'longitude': 101.7186, 'latitude': 26.5820, 'contact': '吴总', 'phone': '13800138007'},
    {'name': '乐山电机设备厂', 'address': '四川省乐山市市中区高新区路99号', 'longitude': 103.7656, 'latitude': 29.5521, 'contact': '郑经理', 'phone': '13800138008'},
    {'name': '南充汽车零部件公司', 'address': '四川省南充市顺庆区工业集中区55号', 'longitude': 106.1106, 'latitude': 30.8370, 'contact': '钱总', 'phone': '13800138009'},
    {'name': '达州电子元器件厂', 'address': '四川省达州市通川区产业园区77号', 'longitude': 107.5022, 'latitude': 31.2090, 'contact': '冯经理', 'phone': '13800138010'},
]

PRODUCTS = [
    {'name': '电机', 'category': '机械部件'},
    {'name': '电路板', 'category': '电子元件'},
    {'name': '特种钢材', 'category': '原材料'},
    {'name': '精密轴承', 'category': '零部件'},
    {'name': '芯片', 'category': '电子元件'},
    {'name': '高端传感器', 'category': '电子元件'},
    {'name': '光刻机', 'category': '机械部件'},
    {'name': '铝合金型材', 'category': '原材料'},
    {'name': '液压缸', 'category': '机械部件'},
    {'name': '密封件', 'category': '零部件'},
    {'name': '减速机', 'category': '机械部件'},
    {'name': '变压器', 'category': '电子元件'},
    {'name': '工业机器人', 'category': '机械部件'},
    {'name': '数控机床', 'category': '机械部件'},
    {'name': '模具', 'category': '零部件'},
]

def generate_test_data():
    app = create_app()
    with app.app_context():
        print("正在生成测试数据...")
        
        test_ent = Enterprise(
            name='test_ent',
            address='测试企业地址',
            longitude=104.0,
            latitude=30.6,
            contact='测试联系人',
            phone='13900000001',
            credit_score=80.0,
            capacity=60,
            role='enterprise',
        )
        test_ent.set_password('admin')
        db.session.add(test_ent)

        for ent_data in ENTERPRISES:
            enterprise = Enterprise(
                name=ent_data['name'],
                address=ent_data['address'],
                longitude=ent_data['longitude'],
                latitude=ent_data['latitude'],
                contact=ent_data['contact'],
                phone=ent_data['phone'],
                credit_score=random.uniform(60, 95),
                capacity=random.randint(30, 100),
                role='enterprise',
            )
            enterprise.set_password('123456')
            db.session.add(enterprise)
        
        db.session.commit()
        print(f"已创建 {len(ENTERPRISES)} 家企业")
        
        enterprises = Enterprise.query.all()
        
        for ent in enterprises:
            num_products = random.randint(2, 5)
            selected_products = random.sample(PRODUCTS, num_products)
            
            for prod_data in selected_products:
                product = Product(
                    name=prod_data['name'],
                    category=prod_data['category'],
                    enterprise_id=ent.id
                )
                db.session.add(product)
        
        db.session.commit()
        print("已创建产品数据")
        
        products = Product.query.all()
        units = ['件', '台', '吨', '千克', '套', '批']
        
        for product in products:
            if random.random() > 0.5:
                db.session.add(Inquiry(
                    poster_id=product.enterprise_id,
                    direction='supply',
                    product_id=product.id,
                    product_name=product.name,
                    quantity=random.randint(10, 1000),
                    unit=random.choice(units),
                    description=f"供应{product.name}，质量保证",
                    status='open',
                ))
            
            if random.random() > 0.6:
                db.session.add(Inquiry(
                    poster_id=product.enterprise_id,
                    direction='demand',
                    product_id=product.id,
                    product_name=product.name,
                    quantity=random.randint(5, 500),
                    unit=random.choice(units),
                    description=f"求购{product.name}，价格面议",
                    status='open',
                ))
        
        db.session.commit()
        print("已创建供需数据")
        
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
        print("已创建管理员账号: admin / admin（政府监管）")
        print("已创建企业测试账号: test_ent / 123456")
        
        print("测试数据生成完成！")

if __name__ == '__main__':
    generate_test_data()
