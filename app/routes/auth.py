from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.models import Enterprise
from app import db
from app.authz import user_effective_role, user_session_role

auth = Blueprint('auth', __name__)


def _safe_relative_path(candidate: str | None) -> str | None:
    if not candidate or not isinstance(candidate, str):
        return None
    s = candidate.strip()
    if not s.startswith("/") or s.startswith("//"):
        return None
    return s


def _default_spa_home(effective_role: str) -> str:
    return "/gov" if effective_role == "admin" else "/"


def _spa_home_for_user(user) -> str:
    r = user_session_role(user)
    if r == "government":
        return "/gov"
    if r == "admin":
        return "/admin/dashboard"
    return "/"


def _parse_optional_float(raw):
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


@auth.route('/register', methods=['GET', 'POST'])
def register():
    spa_modal = request.headers.get('X-Login-Modal') == '1'

    if current_user.is_authenticated:
        if request.method == 'POST' and spa_modal:
            return jsonify({'ok': False, 'error': '您已登录，无需注册'}), 400
        return redirect(_spa_home_for_user(current_user))

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        address = (request.form.get('address') or '').strip() or None
        contact = (request.form.get('contact') or '').strip() or None
        phone = (request.form.get('phone') or '').strip() or None
        password = request.form.get('password') or ''
        password2 = request.form.get('password2') or ''
        province = (request.form.get('province') or '').strip() or None
        city = (request.form.get('city') or '').strip() or None
        business_scope = (request.form.get('business_scope') or '').strip() or None
        industry_code = (request.form.get('industry_code') or '').strip() or None
        rc_raw = request.form.get('registered_capital')
        longitude = _parse_optional_float(request.form.get('longitude'))
        latitude = _parse_optional_float(request.form.get('latitude'))
        registered_capital = _parse_optional_float(rc_raw)

        def fail(msg: str, code: int = 400):
            if spa_modal:
                return jsonify({'ok': False, 'error': msg}), code
            flash(msg, 'danger')
            return render_template('auth/register.html')

        if not name or not password:
            return fail('请填写企业名称与密码')

        if len(password) < 6:
            return fail('密码长度至少 6 位')

        if password != password2:
            return fail('两次密码不一致')

        if Enterprise.query.filter_by(name=name).first():
            return fail('企业名称已存在', 409)

        enterprise = Enterprise(
            name=name,
            address=address,
            contact=contact,
            phone=phone,
            longitude=longitude,
            latitude=latitude,
            province=province,
            city=city,
            business_scope=business_scope,
            industry_code=industry_code,
            registered_capital=registered_capital,
            role='enterprise',
            verification_status='pending',
            is_verified=False,
        )
        enterprise.set_password(password)

        db.session.add(enterprise)
        db.session.commit()

        success_msg = '注册成功！您的账号正在等待管理员审核，审核通过后即可登录使用。'
        if spa_modal:
            return jsonify({'ok': True, 'message': success_msg})
        flash(success_msg, 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    spa_modal = request.headers.get('X-Login-Modal') == '1'

    if current_user.is_authenticated:
        # SPA 弹窗 POST 时避免返回 302 HTML，导致前端按 JSON 解析失败、误报「登录失败」
        if request.method == 'POST' and spa_modal:
            home = _spa_home_for_user(current_user)
            return jsonify({'ok': True, 'redirect': home, 'role': user_session_role(current_user)})
        return redirect(_spa_home_for_user(current_user))

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        password = request.form.get('password') or ''

        enterprise = Enterprise.query.filter_by(name=name).first()

        if enterprise is None or not enterprise.check_password(password):
            if spa_modal:
                return jsonify({'ok': False, 'error': '企业名称或密码错误'}), 401
            flash('企业名称或密码错误', 'danger')
            return redirect(url_for('main.index', login='1'))

        # 检查审核状态
        if enterprise.verification_status == 'pending':
            if spa_modal:
                return jsonify({'ok': False, 'error': '您的账号正在等待管理员审核，请耐心等待。'}), 403
            flash('您的账号正在等待管理员审核，请耐心等待。', 'warning')
            return redirect(url_for('main.index', login='1'))
        
        if enterprise.verification_status == 'rejected':
            reason = enterprise.rejection_reason or '信息不符'
            if spa_modal:
                return jsonify({'ok': False, 'error': f'您的注册申请已被驳回。原因：{reason}'}), 403
            flash(f'您的注册申请已被驳回。原因：{reason}', 'danger')
            return redirect(url_for('main.index', login='1'))

        login_user(enterprise)
        flash('登录成功', 'success')
        home = _spa_home_for_user(enterprise)
        next_page = _safe_relative_path(request.args.get('next'))
        dest = next_page or home
        if spa_modal:
            return jsonify({'ok': True, 'redirect': dest, 'role': user_session_role(enterprise)})
        return redirect(dest)

    return redirect(url_for('main.index', login='1'))

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('main.index'))
