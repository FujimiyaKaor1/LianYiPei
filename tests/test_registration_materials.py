import json
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image

from app.services.material_security import scan_material
from app.models import Enterprise
import app.services.registration_materials as registration_materials


def _license_docx() -> BytesIO:
    content = BytesIO()
    lines = [
        "名称：广东可信电子有限公司",
        "统一社会信用代码：91440300MA5F123456",
        "法定代表人：张三",
        "住所：广东省深圳市南山区科技园1号",
        "注册资本：1000.5万元",
        "经营范围：电子连接器及五金制品制造",
    ]
    with ZipFile(content, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>")
        body = "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in lines)
        archive.writestr("word/document.xml", f"<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body>{body}</w:body></w:document>")
    content.seek(0)
    return content


def test_business_license_creates_reviewable_draft_without_registering(client):
    response = client.post(
        "/auth/register/preview-material",
        data={"file": (_license_docx(), "营业执照.docx")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    draft = response.get_json()["draft"]
    assert draft["status"] == "draft"
    assert draft["fields"]["name"]["value"] == "广东可信电子有限公司"
    assert draft["fields"]["unified_social_credit_code"]["value"] == "91440300MA5F123456"
    assert draft["fields"]["registered_capital"]["value"] == 1000.5
    assert Enterprise.query.filter_by(name="广东可信电子有限公司").first() is None


def test_reviewed_license_fields_are_stored_for_admin_review(client):
    response = client.post(
        "/auth/register",
        data={
            "name": "广东可信电子有限公司",
            "address": "广东省深圳市南山区科技园1号",
            "business_scope": "电子连接器及五金制品制造",
            "registered_capital": "1000.5",
            "unified_social_credit_code": "91440300MA5F123456",
            "legal_representative": "张三",
            "password": "secure123",
            "password2": "secure123",
        },
        headers={"X-Login-Modal": "1"},
    )
    assert response.status_code == 200
    enterprise = Enterprise.query.filter_by(name="广东可信电子有限公司").one()
    assert enterprise.verification_status == "pending"
    assert enterprise.extras["registration_material"]["unified_social_credit_code"] == "91440300MA5F123456"
    assert enterprise.extras["registration_material"]["review_status"] == "pending"


def test_confirmed_license_material_submits_pending_application_without_manual_field_form(client):
    response = client.post(
        "/auth/register/submit-material",
        data={
            "file": (_license_docx(), "营业执照.docx"),
            "password": "secure123",
            "confirm": "true",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["status"] == "pending"
    enterprise = Enterprise.query.filter_by(name="广东可信电子有限公司").one()
    assert enterprise.verification_status == "pending"
    assert enterprise.address == "广东省深圳市南山区科技园1号"
    assert enterprise.province == "广东"
    assert enterprise.city == "深圳"
    assert enterprise.unified_social_credit_code == "91440300MA5F123456"
    assert enterprise.extras["registration_material"]["source"] == "confirmed_uploaded_business_license"
    assert enterprise.check_password("secure123")


def test_confirmed_license_material_persists_user_reviewed_overrides(client):
    response = client.post(
        "/auth/register/submit-material",
        data={
            "file": (_license_docx(), "营业执照.docx"),
            "password": "secure123",
            "confirm": "true",
            "overrides": json.dumps({"address": "广东省深圳市南山区人工核对路2号", "business_scope": "人工核对后的经营范围"}),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    enterprise = Enterprise.query.filter_by(name="广东可信电子有限公司").one()
    assert enterprise.address == "广东省深圳市南山区人工核对路2号"
    assert enterprise.business_scope == "人工核对后的经营范围"
    assert enterprise.extras["registration_material"]["reviewed_overrides"] == {"address": "广东省深圳市南山区人工核对路2号", "business_scope": "人工核对后的经营范围"}


def test_license_material_never_creates_account_without_explicit_confirmation(client):
    response = client.post(
        "/auth/register/submit-material",
        data={"file": (_license_docx(), "营业执照.docx"), "password": "secure123"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "confirmation_required"
    assert Enterprise.query.filter_by(name="广东可信电子有限公司").first() is None


def test_registration_rejects_duplicate_unified_social_credit_code(client):
    first = client.post(
        "/auth/register",
        data={
            "name": "已有统一代码企业",
            "unified_social_credit_code": "91440300MA5F123456",
            "password": "secure123",
            "password2": "secure123",
        },
        headers={"X-Login-Modal": "1"},
    )
    assert first.status_code == 200

    duplicate = client.post(
        "/auth/register",
        data={
            "name": "重复统一代码企业",
            "unified_social_credit_code": "91440300MA5F123456",
            "password": "secure123",
            "password2": "secure123",
        },
        headers={"X-Login-Modal": "1"},
    )
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"] == "统一社会信用代码已存在"
    assert Enterprise.query.filter_by(name="重复统一代码企业").first() is None


def test_license_material_with_missing_required_field_stays_as_draft(client):
    content = BytesIO()
    with ZipFile(content, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>")
        archive.writestr("word/document.xml", "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body><w:p><w:r><w:t>名称：缺少代码企业</w:t></w:r></w:p></w:body></w:document>")
    content.seek(0)
    response = client.post(
        "/auth/register/submit-material",
        data={"file": (content, "营业执照.docx"), "password": "secure123", "confirm": "true"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 422
    assert response.get_json()["code"] == "needs_clarification"
    assert Enterprise.query.filter_by(name="缺少代码企业").first() is None


def test_material_security_accepts_bounded_license_images():
    image = BytesIO()
    Image.new("RGB", (32, 32), "white").save(image, format="PNG")
    result = scan_material("营业执照.png", image.getvalue())
    assert result["status"] == "clean"


def test_image_material_uses_vision_agent_and_returns_confidence(monkeypatch):
    image = BytesIO()
    Image.new("RGB", (32, 32), "white").save(image, format="PNG")

    class FakeModel:
        def invoke(self, messages):
            assert messages[1].content[1]["type"] == "image_url"
            return type("Response", (), {"content": '{"name":{"value":"视觉识别企业","confidence":0.98},"unified_social_credit_code":{"value":"91440300MA5F123456","confidence":0.96}}'})()

    monkeypatch.setattr(registration_materials, "_vision_model_from_env", lambda: FakeModel())
    draft = registration_materials.extract_registration_material("营业执照.png", image.getvalue())

    assert draft["extraction_source"] == "vision_agent"
    assert draft["fields"]["name"]["confidence"] == 0.98
    assert draft["fields"]["unified_social_credit_code"]["evidence"]["source"] == "vision_agent"


def test_bundled_demo_license_prefills_the_realistic_demo_enterprise(client):
    license_path = Path(__file__).parents[1] / "app/static/demo/registration/business-license.jpg"
    response = client.post(
        "/auth/register/preview-material",
        data={"file": (license_path.open("rb"), "营业执照.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    draft = response.get_json()["draft"]
    assert draft["demo_fixture"] is True
    assert draft["extraction_source"] == "vision_agent"
    assert draft["fields"]["name"]["value"] == "长沙德远智造科技有限公司"
    assert draft["fields"]["unified_social_credit_code"]["value"] == "91430100MAK1QW4U4E"
    assert draft["fields"]["registered_capital"]["value"] == 200.0
    assert Enterprise.query.filter_by(name="长沙德远智造科技有限公司").first() is None


def test_registration_preview_rejects_infected_material(client):
    response = client.post(
        "/auth/register/preview-material",
        data={"file": (BytesIO(b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"), "营业执照.docx")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 422
    assert response.get_json()["code"] == "material_infected"


def test_registration_material_read_is_bounded(client):
    response = client.post(
        "/auth/register/preview-material",
        data={"file": (BytesIO(b"x" * (10 * 1024 * 1024 + 1)), "营业执照.docx")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "invalid_material"
