from datetime import datetime
import json
import re

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError
from app.models import Enterprise
from app import db
from app.authz import user_effective_role, user_session_role
from app.services.material_security import MAX_MATERIAL_BYTES, InvalidMaterial, MaterialInfected, MaterialScanUnavailable, scan_material
from app.services.registration_materials import extract_registration_material

auth = Blueprint('auth', __name__)


def _read_registration_material(uploaded) -> bytes:
    """Read at most one byte over policy before scanning/parsing.

    Registration endpoints are public.  A bounded read prevents an oversized
    multipart body from being copied into memory repeatedly before the common
    material-security policy can reject it.
    """
    content = uploaded.read(MAX_MATERIAL_BYTES + 1)
    if len(content) > MAX_MATERIAL_BYTES:
        raise InvalidMaterial("文件大小不能超过10MB")
    return content


@auth.post('/register/preview-material')
def preview_registration_material():
    """Extract a reviewable registration draft; never creates an account."""
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"ok": False, "error": "请选择营业执照材料"}), 400
    try:
        filename = uploaded.filename.strip()
        content = _read_registration_material(uploaded)
        scan_material(filename, content)
        draft = extract_registration_material(filename, content)
    except MaterialInfected as exc:
        return jsonify({"ok": False, "error": str(exc), "code": "material_infected"}), 422
    except MaterialScanUnavailable as exc:
        return jsonify({"ok": False, "error": str(exc), "code": "material_scan_unavailable"}), 503
    except InvalidMaterial as exc:
        return jsonify({"ok": False, "error": str(exc), "code": "invalid_material"}), 400
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "draft": draft})


@auth.post('/register/submit-material')
def submit_registration_material():
    """Create a pending enterprise application from one confirmed license file.

    The file is parsed and scanned on the server again so the final submit is
    not dependent on an editable browser preview. No account is created until
    the caller explicitly sends ``confirm=true`` and supplies a password.
    """
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"ok": False, "error": "请选择营业执照材料"}), 400
    try:
        content = _read_registration_material(uploaded)
        scan_material(uploaded.filename.strip(), content)
        draft = extract_registration_material(uploaded.filename.strip(), content)
    except MaterialInfected as exc:
        return jsonify({"ok": False, "error": str(exc), "code": "material_infected"}), 422
    except MaterialScanUnavailable as exc:
        return jsonify({"ok": False, "error": str(exc), "code": "material_scan_unavailable"}), 503
    except InvalidMaterial as exc:
        return jsonify({"ok": False, "error": str(exc), "code": "invalid_material"}), 400
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    if draft.get("missing_required"):
        return jsonify({"ok": False, "error": "营业执照缺少必要字段，请补充清晰材料", "code": "needs_clarification", "draft": draft}), 422
    confirmed = str(request.form.get("confirm") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not confirmed:
        return jsonify({"ok": False, "error": "请确认识别结果后再提交入驻申请", "code": "confirmation_required", "draft": draft}), 400

    password = request.form.get("password") or ""
    password2 = request.form.get("password2") or password
    if len(password) < 6:
        return jsonify({"ok": False, "error": "密码长度至少 6 位"}), 400
    if password != password2:
        return jsonify({"ok": False, "error": "两次密码不一致"}), 400

    fields = draft.get("fields") if isinstance(draft.get("fields"), dict) else {}

    def value(name):
        field = fields.get(name)
        return field.get("value") if isinstance(field, dict) else None

    # The browser may send the values the user reviewed/edited.  They are
    # never trusted blindly: the uploaded material is still scanned and
    # parsed above, then the same normalization and uniqueness checks below
    # are applied to the reviewed values.
    reviewed_overrides: dict[str, object] = {}
    raw_overrides = request.form.get("overrides")
    if raw_overrides:
        try:
            candidate = json.loads(raw_overrides)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "识别结果修改格式无效", "code": "invalid_overrides"}), 400
        if not isinstance(candidate, dict):
            return jsonify({"ok": False, "error": "识别结果修改格式无效", "code": "invalid_overrides"}), 400
        allowed = {"name", "unified_social_credit_code", "legal_representative", "address", "registered_capital", "business_scope"}
        for key in allowed:
            if key not in candidate:
                continue
            raw_value = candidate[key]
            if raw_value is None:
                continue
            if key == "registered_capital":
                if isinstance(raw_value, str) and not raw_value.strip():
                    continue
                try:
                    normalized = float(raw_value)
                except (TypeError, ValueError):
                    return jsonify({"ok": False, "error": "注册资本格式不正确", "code": "invalid_overrides"}), 400
            else:
                normalized = str(raw_value).strip()
                if not normalized:
                    continue
            reviewed_overrides[key] = normalized
            fields[key] = {"value": normalized, "confidence": 1.0, "evidence": {"source": "user_review"}}

    name = str(value("name") or "").strip()[:200]
    credit_code = re.sub(r"\s+", "", str(value("unified_social_credit_code") or "")).upper()
    if not name or not re.fullmatch(r"[0-9A-Z]{18}", credit_code):
        return jsonify({"ok": False, "error": "企业名称或统一社会信用代码无法核验", "code": "needs_clarification", "draft": draft}), 422
    if Enterprise.query.filter_by(name=name).first():
        return jsonify({"ok": False, "error": "企业名称已存在", "code": "duplicate_enterprise"}), 409
    if Enterprise.query.filter_by(unified_social_credit_code=credit_code).first():
        return jsonify({"ok": False, "error": "统一社会信用代码已存在", "code": "duplicate_credit_code"}), 409

    address = str(value("address") or "").strip()[:500] or None
    region = re.match(r"^(.+?省)?(.+?市)", address or "")
    province = (region.group(1) or "").removesuffix("省") or None if region else None
    city = (region.group(2) or "").removesuffix("市") or None if region else None
    capital = value("registered_capital")
    try:
        registered_capital = float(capital) if capital is not None else None
    except (TypeError, ValueError):
        registered_capital = None
    evidence = {
        key: field.get("evidence")
        for key, field in fields.items()
        if isinstance(field, dict) and isinstance(field.get("evidence"), dict)
    }
    enterprise = Enterprise(
        name=name,
        address=address,
        province=province,
        city=city,
        business_scope=str(value("business_scope") or "").strip()[:2000] or None,
        registered_capital=registered_capital,
        unified_social_credit_code=credit_code,
        role="enterprise",
        verification_status="pending",
        is_verified=False,
        extras={
            "registration_material": {
                "unified_social_credit_code": credit_code,
                "legal_representative": str(value("legal_representative") or "").strip()[:100] or None,
                "source": "confirmed_uploaded_business_license",
                "schema_version": draft.get("schema_version"),
                "evidence": evidence,
                "reviewed_overrides": reviewed_overrides,
                "submitted_at": datetime.utcnow().isoformat(),
                "review_status": "pending",
            }
        },
    )
    enterprise.set_password(password)
    db.session.add(enterprise)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"ok": False, "error": "统一社会信用代码已存在", "code": "duplicate_credit_code"}), 409
    return jsonify({"ok": True, "message": "入驻申请已提交，等待管理员审核。", "status": "pending", "enterprise_id": enterprise.id})


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
        credit_code = re.sub(r"\s+", "", request.form.get("unified_social_credit_code") or "").upper()
        legal_representative = (request.form.get("legal_representative") or "").strip()[:100] or None

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

        if credit_code and not re.fullmatch(r"[0-9A-Z]{18}", credit_code):
            return fail('统一社会信用代码格式不正确')

        if Enterprise.query.filter_by(name=name).first():
            return fail('企业名称已存在', 409)
        if credit_code and Enterprise.query.filter_by(unified_social_credit_code=credit_code).first():
            return fail('统一社会信用代码已存在', 409)

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
            unified_social_credit_code=credit_code or None,
            role='enterprise',
            verification_status='pending',
            is_verified=False,
            extras={
                "registration_material": {
                    "unified_social_credit_code": credit_code or None,
                    "legal_representative": legal_representative,
                    "source": "uploaded_business_license" if credit_code or legal_representative else "manual_registration",
                    "submitted_at": datetime.utcnow().isoformat(),
                    "review_status": "pending",
                }
            },
        )
        enterprise.set_password(password)

        db.session.add(enterprise)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return fail('统一社会信用代码已存在', 409)

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

        if not name or not password:
            if spa_modal:
                return jsonify({'ok': False, 'error': '请填写企业名称与密码'}), 400
            flash('请填写企业名称与密码', 'danger')
            return redirect(url_for('main.index', login='1'))

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

@auth.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    if request.method == 'POST' and request.headers.get('X-Login-Modal') == '1':
        return jsonify({'ok': True})
    flash('已退出登录', 'info')
    return redirect(url_for('main.index'))
