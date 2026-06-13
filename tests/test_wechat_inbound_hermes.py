import hashlib
from datetime import datetime
from xml.etree import ElementTree as ET

from app import db
from app.models import Alert, HermesPendingAction


OPENID = "oBhEk3OO5SlRw8TUSQsckhxKA3So"
TOKEN = "test-wechat-token"


def _signature(timestamp: str = "1", nonce: str = "2") -> str:
    return hashlib.sha1("".join(sorted([TOKEN, timestamp, nonce])).encode("utf-8")).hexdigest()


def _callback_url() -> str:
    return f"/api/wechat/callback/service-account?signature={_signature()}&timestamp=1&nonce=2"


def _wechat_xml(content: str, *, msg_type: str = "text") -> bytes:
    return f"""
<xml>
  <ToUserName><![CDATA[gh_chainyipei]]></ToUserName>
  <FromUserName><![CDATA[{OPENID}]]></FromUserName>
  <CreateTime>1781234393</CreateTime>
  <MsgType><![CDATA[{msg_type}]]></MsgType>
  <Content><![CDATA[{content}]]></Content>
  <MsgId>123</MsgId>
</xml>
""".encode("utf-8")


def _reply_content(response) -> str:
    root = ET.fromstring(response.data.decode("utf-8"))
    return root.findtext("Content") or ""


def _create_alert(**overrides) -> Alert:
    payload = {
        "product_name": "成都云工工业软件有限公司",
        "message": "信用分 7 天内下降 18 分，触发红色预警",
        "level": "red",
        "dimension": "credit",
        "alert_type": "credit_anomaly",
        "severity_score": 0.9,
        "suggestion": "建议立即核查履约异常并联系企业。",
        "is_active": True,
        "analysis_data": {
            "risk_reason": "连续履约异常导致信用分下降",
            "impact_scope": "影响平台匹配权重和报价成功率",
            "ai_suggestions": ["核查异常订单", "联系企业补充材料"],
        },
        "created_at": datetime.utcnow(),
    }
    payload.update(overrides)
    alert = Alert(**payload)
    db.session.add(alert)
    db.session.commit()
    return alert


def test_wechat_callback_verifies_get_signature(client, app):
    app.config["WECHAT_CALLBACK_TOKEN"] = TOKEN

    ok = client.get(_callback_url() + "&echostr=hello")
    denied = client.get("/api/wechat/callback/service-account?signature=bad&timestamp=1&nonce=2&echostr=hello")

    assert ok.status_code == 200
    assert ok.data.decode("utf-8") == "hello"
    assert denied.status_code == 403


def test_wechat_can_list_active_red_alerts(client, app, _db):
    app.config["WECHAT_CALLBACK_TOKEN"] = TOKEN
    _create_alert()

    response = client.post(
        _callback_url(),
        data=_wechat_xml("查预警"),
        content_type="application/xml",
    )

    assert response.status_code == 200
    content = _reply_content(response)
    assert "最新红色预警" in content
    assert "成都云工工业软件有限公司" in content


def test_wechat_close_alert_requires_then_accepts_confirmation(
    client,
    app,
    _db,
    test_admin,
):
    app.config["WECHAT_CALLBACK_TOKEN"] = TOKEN
    app.config["HERMES_ACTION_CONFIRM_TTL_SECONDS"] = 300
    test_admin.wechat_service_openid = OPENID
    test_admin.wechat_bound = True
    db.session.add(test_admin)
    db.session.commit()
    alert = _create_alert()

    preview = client.post(
        _callback_url(),
        data=_wechat_xml(f"关闭 {alert.id} 微信确认测试"),
        content_type="application/xml",
    )

    assert preview.status_code == 200
    preview_text = _reply_content(preview)
    assert "已生成待确认动作" in preview_text
    assert "确认执行" in preview_text

    pending = HermesPendingAction.query.filter_by(status="pending").one()
    assert pending.action == "close_alert"
    db.session.refresh(alert)
    assert alert.is_active is True

    confirmed = client.post(
        _callback_url(),
        data=_wechat_xml("确认执行"),
        content_type="application/xml",
    )

    assert confirmed.status_code == 200
    assert "已执行：关闭预警" in _reply_content(confirmed)
    db.session.refresh(alert)
    assert alert.is_active is False
    db.session.refresh(pending)
    assert pending.status == "executed"
