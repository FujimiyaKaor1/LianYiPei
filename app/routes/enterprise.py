from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from app.authz import role_required
from app.models import Enterprise, Product
from app import db

enterprise = Blueprint('enterprise', __name__)


@enterprise.route('/profile/classic')
@role_required('enterprise')
def profile_classic():
    """经典 Jinja 画像页（雷达图、标签云）；须注册在 /profile 之前避免路径被吞。"""
    from app.services.profile import build_enterprise_profile

    profile_data = build_enterprise_profile(current_user.id)
    return render_template('enterprise/profile.html', profile=profile_data)


@enterprise.route('/profile')
@role_required('enterprise')
def profile():
    """企业 SPA 工作台入口，与 Flash → Sonner 桥接一致。"""
    from app.routes.main import _get_initial_data

    return render_template('spa.html', initial_data=_get_initial_data())

def _get_industry_codes():
    """行业标准编码(GB/T 4754简化)"""
    return [
        ('C34', '通用设备制造业'),
        ('C35', '专用设备制造业'),
        ('C36', '汽车制造业'),
        ('C37', '电气机械和器材制造业'),
        ('C38', '计算机、通信和其他电子设备制造业'),
        ('C39', '仪器仪表制造业'),
        ('C33', '金属制品业'),
        ('C32', '黑色金属冶炼和压延加工业'),
    ]

@enterprise.route('/edit', methods=['GET', 'POST'])
@role_required('enterprise')
def edit():
    if request.method == 'POST':
        current_user.address = request.form.get('address')
        current_user.contact = request.form.get('contact')
        current_user.phone = request.form.get('phone')
        longitude = request.form.get('longitude')
        latitude = request.form.get('latitude')
        if longitude:
            current_user.longitude = float(longitude)
        if latitude:
            current_user.latitude = float(latitude)
        current_user.patent_category = request.form.get('patent_category') or None
        current_user.tech_keywords = request.form.get('tech_keywords') or None
        rd = request.form.get('rd_investment')
        current_user.rd_investment = float(rd) if rd else None
        current_user.industry_code = request.form.get('industry_code') or None
        
        db.session.commit()
        flash('企业信息已更新', 'success')
        return redirect(url_for('enterprise.profile'))
    
    return render_template('enterprise/edit.html', industry_codes=_get_industry_codes())

@enterprise.route('/products')
@role_required('enterprise')
def products():
    products = current_user.products.all()
    return render_template('enterprise/products.html', products=products)

@enterprise.route('/products/add', methods=['GET', 'POST'])
@role_required('enterprise')
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        industry_code = request.form.get('industry_code')
        
        if not name:
            flash('请填写产品名称', 'danger')
            return render_template('enterprise/add_product.html', industry_codes=_get_industry_codes())
        
        product = Product(name=name, category=category, industry_code=industry_code or None, enterprise_id=current_user.id)
        db.session.add(product)
        db.session.commit()
        
        flash('产品添加成功', 'success')
        return redirect(url_for('enterprise.products'))
    
    return render_template('enterprise/add_product.html', industry_codes=_get_industry_codes())

@enterprise.route('/products/<int:product_id>/delete', methods=['POST'])
@role_required('enterprise')
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.enterprise_id != current_user.id:
        flash('无权限操作', 'danger')
        return redirect(url_for('enterprise.products'))
    
    db.session.delete(product)
    db.session.commit()
    flash('产品已删除', 'success')
    return redirect(url_for('enterprise.products'))
