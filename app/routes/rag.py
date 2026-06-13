"""RAG API routes for PDF ingestion and knowledge-base maintenance."""

from __future__ import annotations

import os
import shutil
import time
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

rag_bp = Blueprint("rag", __name__, url_prefix="/api/rag")


def _project_root() -> Path:
    return Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _get_upload_dir() -> Path:
    upload_dir = current_app.config.get("UPLOAD_FOLDER", str(_project_root() / "uploads"))
    rag_dir = Path(upload_dir) / "rag_pdfs"
    rag_dir.mkdir(parents=True, exist_ok=True)
    return rag_dir


def _get_chroma_dir() -> Path:
    chroma_dir = current_app.config.get("RAG_CHROMA_DIR", str(_project_root() / "data" / "chroma_db"))
    path = Path(chroma_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _import_rag_service():
    from app.services.rag_service import ingest_pdf

    return ingest_pdf


def _strict_admin_required():
    if not current_user.is_authenticated:
        return jsonify({"error": "请先登录"}), 401
    if getattr(current_user, "role", None) != "admin" and not getattr(current_user, "is_admin", False):
        return jsonify({"error": "权限不足，禁止访问"}), 403
    return None


@rag_bp.route("/ingest", methods=["POST"])
@login_required
def rag_ingest():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "请求中未包含 file 字段"}), 400

    file_storage = request.files["file"]
    filename = (file_storage.filename or "").strip()
    if not filename:
        return jsonify({"ok": False, "error": "未选择文件"}), 400

    if not filename.lower().endswith(".pdf"):
        return jsonify({"ok": False, "error": "仅支持 PDF 文件"}), 400

    safe_name = secure_filename(filename) or "document.pdf"
    upload_dir = _get_upload_dir()
    file_path = upload_dir / f"{int(time.time())}_{uuid.uuid4().hex[:12]}__{safe_name}"

    try:
        file_storage.save(str(file_path))
    except Exception as exc:
        current_app.logger.exception("rag_ingest: save failed")
        return jsonify({"ok": False, "error": f"文件保存失败：{exc}"}), 500

    try:
        ingest_pdf = _import_rag_service()
        result = ingest_pdf(
            file_path=str(file_path),
            persist_directory=str(_get_chroma_dir()),
        )
    except FileNotFoundError as exc:
        current_app.logger.warning("rag_ingest: file not found: %s", exc)
        return jsonify({"ok": False, "error": f"PDF 文件不存在或已损坏：{exc}"}), 400
    except ValueError as exc:
        current_app.logger.warning("rag_ingest: invalid pdf: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("rag_ingest: ingest failed")
        return jsonify({"ok": False, "error": f"RAG 入库失败：{exc}"}), 500
    finally:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass

    return jsonify(
        {
            "ok": True,
            "message": f"入库成功，共 {result.get('chunks', 0)} 个文本块",
            "data": result,
        }
    )


@rag_bp.route("/status", methods=["GET"])
@login_required
def rag_status():
    try:
        from app.services.rag_service import _load_vector_store

        vector_store = _load_vector_store(persist_directory=str(_get_chroma_dir()))
        count = vector_store._collection.count()
        return jsonify(
            {
                "ok": True,
                "data": {
                    "collection_name": vector_store._collection.name,
                    "document_count": count,
                    "persist_directory": str(_get_chroma_dir()),
                },
            }
        )
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "知识库尚未初始化，请先上传 PDF"}), 404
    except Exception as exc:
        current_app.logger.exception("rag_status")
        return jsonify({"ok": False, "error": str(exc)}), 500


@rag_bp.route("/clear", methods=["POST"])
@login_required
def rag_clear():
    err = _strict_admin_required()
    if err:
        return err

    chroma_dir = _get_chroma_dir()
    try:
        if chroma_dir.exists():
            shutil.rmtree(str(chroma_dir))
        chroma_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        current_app.logger.exception("rag_clear")
        return jsonify({"ok": False, "error": f"清空失败：{exc}"}), 500

    return jsonify({"ok": True, "message": "知识库已清空"})
