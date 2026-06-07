from app.models import Enterprise, Product, Inquiry
from app import db

def build_enterprise_profile(ent_id):
    """构建企业画像：基础信息、技术能力、供需标签"""
    enterprise = Enterprise.query.get(ent_id)
    if not enterprise:
        return None
    
    products = Product.query.filter_by(enterprise_id=ent_id).all()
    supply_tags = list(set([p.name for p in products]))
    
    demands = Inquiry.query.filter_by(poster_id=ent_id, direction='demand').all()
    demand_tags = []
    for d in demands:
        if d.product and d.product.name:
            demand_tags.append(d.product.name)
        elif d.product_name:
            demand_tags.append(d.product_name)
    demand_tags = list(set(demand_tags))
    
    # 技术能力画像
    tech_keywords = []
    if enterprise.tech_keywords:
        tech_keywords = [k.strip() for k in enterprise.tech_keywords.split(',') if k.strip()]
    
    # 雷达图数据：信用、产能、技术、供应能力、需求覆盖 (0-100归一化)
    rd_score = min(100, (enterprise.rd_investment or 0) / 10)  # 研发投入每10万得1分
    capacity_score = min(100, (enterprise.capacity or 0) * 1.2)
    tech_score = min(100, len(tech_keywords) * 20 + (10 if enterprise.patent_category else 0))
    supply_score = min(100, len(supply_tags) * 15)
    demand_score = min(100, len(demand_tags) * 20)
    
    profile = {
        'id': enterprise.id,
        'name': enterprise.name,
        'address': enterprise.address,
        'contact': enterprise.contact,
        'phone': enterprise.phone,
        'credit_score': enterprise.credit_score or 0,
        'capacity': enterprise.capacity or 0,
        'longitude': enterprise.longitude,
        'latitude': enterprise.latitude,
        'supply_tags': supply_tags,
        'demand_tags': demand_tags,
        'product_count': len(products),
        'demand_count': len(demands),
        # 技术能力
        'patent_category': enterprise.patent_category or '',
        'tech_keywords': tech_keywords,
        'rd_investment': enterprise.rd_investment or 0,
        'industry_code': enterprise.industry_code or '',
        # 雷达图维度
        'radar_data': {
            'credit': round(enterprise.credit_score or 0, 1),
            'capacity': round(capacity_score, 1),
            'tech': round(tech_score, 1),
            'supply': round(supply_score, 1),
            'demand': round(demand_score, 1),
        }
    }
    
    return profile
