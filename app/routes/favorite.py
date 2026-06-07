"""
收藏 API 路由
===============

提供收藏供应商的完整 REST API。

URL 前缀：/api/favorites/*
"""
from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.authz import role_required
from app.services.favorite_service import favorite_service

favorite_bp = Blueprint("favorite", __name__, url_prefix="/api/favorites")


def _current_enterprise_id() -> int | None:
    """从 Flask-Login 当前用户获取企业 ID"""
    if current_user.is_authenticated:
        return current_user.id
    return None


def _require_login():
    eid = _current_enterprise_id()
    if not eid:
        return jsonify({"error": "请先登录"}), 401
    return None


# ── 收藏管理 ────────────────────────────────────────────────────────────────

@favorite_bp.route("/add", methods=["POST"])
@role_required("enterprise")
def api_add_favorite():
    """
    POST /api/favorites/add

    添加收藏。

    请求体：
    {
        "supplier_id": int,        # 必填
        "product_name": str,        # 可选，收藏时的产品需求
        "match_score": float,       # 可选，收藏时的匹配分数
        "notes": str,               # 可选，用户备注
    }

    返回：
    {
        "success": true,
        "favorite_id": int,
        "message": "收藏成功"
    }
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}
    supplier_id = data.get("supplier_id")
    
    if not supplier_id:
        return jsonify({"error": "缺少 supplier_id"}), 400

    try:
        supplier_id = int(supplier_id)
    except (TypeError, ValueError):
        return jsonify({"error": "supplier_id 无效"}), 400

    current_id = _current_enterprise_id()
    
    favorite, error = favorite_service.add_favorite(
        collector_id=current_id,
        supplier_id=supplier_id,
        product_name=data.get("product_name"),
        match_score=data.get("match_score"),
        notes=data.get("notes"),
    )

    if error:
        return jsonify({"error": error}), 400

    return jsonify({
        "success": True,
        "favorite_id": favorite.id,
        "message": "收藏成功",
    })


@favorite_bp.route("/remove", methods=["POST"])
@role_required("enterprise")
def api_remove_favorite():
    """
    POST /api/favorites/remove

    取消收藏。

    请求体：
    {
        "supplier_id": int,        # 必填
    }

    返回：
    {
        "success": true,
        "message": "已取消收藏"
    }
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}
    supplier_id = data.get("supplier_id")

    if not supplier_id:
        return jsonify({"error": "缺少 supplier_id"}), 400

    try:
        supplier_id = int(supplier_id)
    except (TypeError, ValueError):
        return jsonify({"error": "supplier_id 无效"}), 400

    current_id = _current_enterprise_id()
    success, error = favorite_service.remove_favorite(current_id, supplier_id)

    if not success:
        return jsonify({"error": error}), 400

    return jsonify({
        "success": True,
        "message": "已取消收藏",
    })


@favorite_bp.route("/list", methods=["GET"])
@role_required("enterprise")
def api_get_favorites():
    """
    GET /api/favorites/list?limit=50&offset=0

    获取收藏列表。

    返回：
    {
        "success": true,
        "total": int,
        "favorites": [{...}, ...]
    }
    """
    err = _require_login()
    if err:
        return err

    current_id = _current_enterprise_id()
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    favorites = favorite_service.get_favorite_list(
        collector_id=current_id,
        limit=limit,
        offset=offset,
    )
    total = favorite_service.get_favorite_count(current_id)

    return jsonify({
        "success": True,
        "total": total,
        "favorites": favorites,
    })


@favorite_bp.route("/check/<int:supplier_id>", methods=["GET"])
@role_required("enterprise")
def api_check_favorite(supplier_id: int):
    """
    GET /api/favorites/check/<supplier_id>

    检查是否已收藏。

    返回：
    {
        "success": true,
        "is_favorited": bool
    }
    """
    err = _require_login()
    if err:
        return err

    current_id = _current_enterprise_id()
    is_favorited = favorite_service.is_favorited(current_id, supplier_id)

    return jsonify({
        "success": True,
        "is_favorited": is_favorited,
    })


@favorite_bp.route("/notes", methods=["PUT"])
@role_required("enterprise")
def api_update_notes():
    """
    PUT /api/favorites/notes

    更新收藏备注。

    请求体：
    {
        "supplier_id": int,
        "notes": str,
    }

    返回：
    {
        "success": true,
        "message": "备注已更新"
    }
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}
    supplier_id = data.get("supplier_id")
    notes = data.get("notes", "")

    if not supplier_id:
        return jsonify({"error": "缺少 supplier_id"}), 400

    current_id = _current_enterprise_id()
    success, error = favorite_service.update_notes(current_id, supplier_id, notes)

    if not success:
        return jsonify({"error": error}), 400

    return jsonify({
        "success": True,
        "message": "备注已更新",
    })


@favorite_bp.route("/batch-inquiry", methods=["POST"])
@role_required("enterprise")
def api_batch_inquiry():
    """
    POST /api/favorites/batch-inquiry

    批量发起询价。

    请求体：
    {
        "supplier_ids": [int, ...],
        "product_name": str,
    }

    返回：
    {
        "success": true,
        "results": {
            "success": int,
            "failed": int,
            "errors": [str, ...]
        }
    }
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}
    supplier_ids = data.get("supplier_ids", [])
    product_name = data.get("product_name", "")

    if not supplier_ids:
        return jsonify({"error": "请选择要询价的供应商"}), 400

    if not product_name:
        return jsonify({"error": "请填写产品名称"}), 400

    current_id = _current_enterprise_id()
    results = favorite_service.batch_add_inquiry(
        collector_id=current_id,
        supplier_ids=supplier_ids,
        product_name=product_name,
    )

    return jsonify({
        "success": True,
        "results": results,
    })


@favorite_bp.route("/supplier-count/<int:supplier_id>", methods=["GET"])
@role_required("enterprise")
def api_supplier_favorite_count(supplier_id: int):
    """
    GET /api/favorites/supplier-count/<supplier_id>

    获取供应商被收藏次数。

    返回：
    {
        "success": true,
        "count": int
    }
    """
    count = favorite_service.get_supplier_favorited_count(supplier_id)
    return jsonify({
        "success": True,
        "count": count,
    })
