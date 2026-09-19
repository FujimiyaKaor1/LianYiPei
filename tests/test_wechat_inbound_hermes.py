import hashlib
import base64
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

from app import db
from app.models import Alert, ExternalCallbackReceipt, HermesPendingAction, IntentQuote
from app.models_chain_xiaoyi import (
    ChainXiaoYiOutboundRecord,
    ChainXiaoYiSession,
    ChainXiaoYiTask,
)
from app.services.work_wechat_crypto import WorkWeChatCrypto
from app.services.callback_receipts import cleanup_callback_receipts


OPENID = "oBhEk3OO5SlRw8TUSQsckhxKA3So"
TOKEN = "test-wechat-token"


def _signature(timestamp: str = "1", nonce: str = "2") -> str:
    return hashlib.sha1("".join(sorted([TOKEN, timestamp, nonce])).encode("utf-8")).hexdigest()


def _callback_url() -> str:
    return f"/api/wechat/callback/service-account?signature={_signature()}&timestamp=1&nonce=2"


def _wechat_xml(content: str, *, msg_type: str = "text", msg_id: str = "123") -> bytes:
    return f"""
<xml>
  <ToUserName><![CDATA[gh_chainyipei]]></ToUserName>
  <FromUserName><![CDATA[{OPENID}]]></FromUserName>
  <CreateTime>1781234393</CreateTime>
  <MsgType><![CDATA[{msg_type}]]></MsgType>
  <Content><![CDATA[{content}]]></Content>
  <MsgId>{msg_id}</MsgId>
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


def test_wechat_callbacks_fail_closed_without_tokens(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "WECHAT_CALLBACK_TOKEN", "")
    monkeypatch.setitem(app.config, "WORK_WECHAT_CALLBACK_TOKEN", "")
    monkeypatch.setitem(app.config, "WORK_WECHAT_ENCODING_AES_KEY", "")
    monkeypatch.setitem(app.config, "WORK_WECHAT_CORPID", "")

    service_response = client.get(
        "/api/wechat/callback/service-account?echostr=should-not-echo"
    )
    work_response = client.get(
        "/api/wechat/callback/work-wechat?echostr=should-not-echo"
    )

    assert service_response.status_code == 503
    assert service_response.data != b"should-not-echo"
    assert work_response.status_code == 503
    assert work_response.data != b"should-not-echo"


def test_unbound_openid_never_falls_back_to_admin(client, app, _db, test_admin):
    app.config["WECHAT_CALLBACK_TOKEN"] = TOKEN
    alert = _create_alert()

    response = client.post(
        _callback_url(),
        data=_wechat_xml(f"关闭 {alert.id} 未绑定用户测试"),
        content_type="application/xml",
    )

    assert response.status_code == 200
    assert "未绑定" in _reply_content(response)
    assert HermesPendingAction.query.count() == 0


def test_work_wechat_url_verification_decrypts_echo(client, app, monkeypatch):
    token = "work-token"
    corp_id = "ww-test-corp"
    aes_key = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode().rstrip("=")
    monkeypatch.setitem(app.config, "WORK_WECHAT_CALLBACK_TOKEN", token)
    monkeypatch.setitem(app.config, "WORK_WECHAT_ENCODING_AES_KEY", aes_key)
    monkeypatch.setitem(app.config, "WORK_WECHAT_CORPID", corp_id)
    crypto = WorkWeChatCrypto(token=token, encoding_aes_key=aes_key, corp_id=corp_id)
    envelope = crypto.encrypt("verified-echo", timestamp="100", nonce="200")

    response = client.get(
        "/api/wechat/callback/work-wechat",
        query_string={
            "msg_signature": envelope["signature"],
            "timestamp": envelope["timestamp"],
            "nonce": envelope["nonce"],
            "echostr": envelope["encrypted"],
        },
    )
    denied = client.get(
        "/api/wechat/callback/work-wechat",
        query_string={
            "msg_signature": "bad",
            "timestamp": envelope["timestamp"],
            "nonce": envelope["nonce"],
            "echostr": envelope["encrypted"],
        },
    )

    assert response.status_code == 200
    assert response.data.decode() == "verified-echo"
    assert denied.status_code == 403


def test_work_wechat_encrypted_message_round_trip(client, app, _db, monkeypatch):
    token = "work-token"
    corp_id = "ww-test-corp"
    aes_key = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode().rstrip("=")
    monkeypatch.setitem(app.config, "WORK_WECHAT_CALLBACK_TOKEN", token)
    monkeypatch.setitem(app.config, "WORK_WECHAT_ENCODING_AES_KEY", aes_key)
    monkeypatch.setitem(app.config, "WORK_WECHAT_CORPID", corp_id)
    _create_alert()
    crypto = WorkWeChatCrypto(token=token, encoding_aes_key=aes_key, corp_id=corp_id)
    incoming = crypto.encrypt(
        _wechat_xml("查预警").decode("utf-8"),
        timestamp="101",
        nonce="201",
    )
    outer_xml = (
        "<xml>"
        f"<Encrypt><![CDATA[{incoming['encrypted']}]]></Encrypt>"
        "</xml>"
    )

    response = client.post(
        "/api/wechat/callback/work-wechat",
        query_string={
            "msg_signature": incoming["signature"],
            "timestamp": incoming["timestamp"],
            "nonce": incoming["nonce"],
        },
        data=outer_xml.encode("utf-8"),
        content_type="application/xml",
    )

    assert response.status_code == 200
    response_root = ET.fromstring(response.data.decode("utf-8"))
    encrypted_reply = response_root.findtext("Encrypt") or ""
    reply_signature = response_root.findtext("MsgSignature") or ""
    reply_timestamp = response_root.findtext("TimeStamp") or ""
    reply_nonce = response_root.findtext("Nonce") or ""
    plaintext_reply = crypto.decrypt(
        encrypted_reply,
        reply_signature,
        reply_timestamp,
        reply_nonce,
    )
    reply_root = ET.fromstring(plaintext_reply)
    assert "最新红色预警" in (reply_root.findtext("Content") or "")


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
        data=_wechat_xml("确认执行", msg_id="124"),
        content_type="application/xml",
    )

    assert confirmed.status_code == 200
    assert "已执行：关闭预警" in _reply_content(confirmed)
    db.session.refresh(alert)
    assert alert.is_active is False
    db.session.refresh(pending)
    assert pending.status == "executed"


def test_service_account_duplicate_callback_executes_once(client, app, _db, monkeypatch):
    app.config["WECHAT_CALLBACK_TOKEN"] = TOKEN
    calls = []

    def fake_handle(message):
        calls.append(message)
        return "幂等回复"

    monkeypatch.setattr(
        "app.services.wechat_inbound_service.handle_wechat_message",
        fake_handle,
    )
    payload = _wechat_xml("重复投递", msg_id="service-duplicate-1")

    first = client.post(_callback_url(), data=payload, content_type="application/xml")
    second = client.post(_callback_url(), data=payload, content_type="application/xml")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.data == second.data
    assert len(calls) == 1
    receipt = ExternalCallbackReceipt.query.one()
    assert receipt.provider == "wechat_service_account"
    assert receipt.status == "completed"


def test_work_wechat_duplicate_callback_executes_once(client, app, _db, monkeypatch):
    token = "work-token"
    corp_id = "ww-test-corp"
    aes_key = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode().rstrip("=")
    monkeypatch.setitem(app.config, "WORK_WECHAT_CALLBACK_TOKEN", token)
    monkeypatch.setitem(app.config, "WORK_WECHAT_ENCODING_AES_KEY", aes_key)
    monkeypatch.setitem(app.config, "WORK_WECHAT_CORPID", corp_id)
    calls = []

    def fake_handle(message):
        calls.append(message)
        return "企业微信幂等回复"

    monkeypatch.setattr(
        "app.services.wechat_inbound_service.handle_wechat_message",
        fake_handle,
    )
    crypto = WorkWeChatCrypto(token=token, encoding_aes_key=aes_key, corp_id=corp_id)
    incoming = crypto.encrypt(
        _wechat_xml("重复投递", msg_id="work-duplicate-1").decode("utf-8"),
        timestamp="301",
        nonce="401",
    )
    outer_xml = f"<xml><Encrypt><![CDATA[{incoming['encrypted']}]]></Encrypt></xml>"
    query = {
        "msg_signature": incoming["signature"],
        "timestamp": incoming["timestamp"],
        "nonce": incoming["nonce"],
    }

    first = client.post(
        "/api/wechat/callback/work-wechat",
        query_string=query,
        data=outer_xml.encode("utf-8"),
        content_type="application/xml",
    )
    second = client.post(
        "/api/wechat/callback/work-wechat",
        query_string=query,
        data=outer_xml.encode("utf-8"),
        content_type="application/xml",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(calls) == 1
    for response in (first, second):
        response_root = ET.fromstring(response.data.decode("utf-8"))
        plaintext = crypto.decrypt(
            response_root.findtext("Encrypt") or "",
            response_root.findtext("MsgSignature") or "",
            response_root.findtext("TimeStamp") or "",
            response_root.findtext("Nonce") or "",
        )
        assert "企业微信幂等回复" in plaintext
    receipt = ExternalCallbackReceipt.query.one()
    assert receipt.provider == "work_wechat"
    assert receipt.status == "completed"


def test_supplier_can_preview_then_confirm_structured_quote_over_wechat(
    client,
    app,
    _db,
    test_enterprise,
    test_supplier,
):
    app.config["WECHAT_CALLBACK_TOKEN"] = TOKEN
    test_supplier.wechat_service_openid = OPENID
    test_supplier.wechat_bound = True
    quote = IntentQuote(
        buyer_id=test_enterprise.id,
        seller_id=test_supplier.id,
        product_name="精密连接器",
        quantity=1000,
        unit="件",
        status="pending",
        buyer_confirmed=True,
    )
    db.session.add_all([test_supplier, quote])
    session = ChainXiaoYiSession(
        owner_id=test_enterprise.id,
        access_token=ChainXiaoYiSession.issue_token(),
        title="微信报价归集测试",
    )
    db.session.add(session)
    db.session.flush()
    task = ChainXiaoYiTask(
        session_id=session.id,
        task_type="rfq",
        status="sent",
        requires_approval=True,
    )
    db.session.add(task)
    db.session.flush()
    outbound = ChainXiaoYiOutboundRecord(
        task_id=task.id,
        supplier_id=test_supplier.id,
        intent_quote_id=quote.id,
        status="sent",
        channel="wechat",
        channel_status_json={"channels": {"wechat": {"status": "sent"}}},
    )
    db.session.add(outbound)
    db.session.commit()
    content = (
        f"报价 #{quote.id} 单价12.8元 含税13% MOQ500 "
        "交期25天 模具费1200元 运费0元 付款30%预付 有效期30天"
    )

    preview = client.post(
        _callback_url(),
        data=_wechat_xml(content, msg_id="quote-preview-1"),
        content_type="application/xml",
    )

    assert preview.status_code == 200
    preview_text = _reply_content(preview)
    assert "报价预览" in preview_text
    assert "12.8" in preview_text
    assert "确认报价" in preview_text
    db.session.refresh(quote)
    assert quote.status == "pending"

    confirmed = client.post(
        _callback_url(),
        data=_wechat_xml("确认" + content, msg_id="quote-confirm-1"),
        content_type="application/xml",
    )

    assert confirmed.status_code == 200
    assert "报价已提交" in _reply_content(confirmed)
    db.session.refresh(quote)
    assert quote.status == "accepted"
    assert quote.seller_reply_price == 12.8
    assert quote.seller_reply_details["tax_included"] is True
    assert quote.seller_reply_details["tax_rate"] == 13
    assert quote.seller_reply_details["moq"] == 500
    assert quote.seller_reply_details["delivery_days"] == 25
    assert quote.seller_reply_details["mold_fee"] == 1200
    assert quote.seller_reply_details["freight"] == 0
    assert quote.seller_reply_details["payment_terms"] == "30%预付"
    assert quote.seller_reply_details["currency"] == "CNY"
    assert quote.seller_reply_details["valid_until"]
    db.session.refresh(outbound)
    assert outbound.status == "replied"
    assert outbound.channel_status_json["channels"]["wechat"]["status"] == "replied"
    assert "site" not in outbound.channel_status_json["channels"]


def test_unbound_wechat_user_cannot_submit_supplier_quote(
    client,
    app,
    _db,
    test_enterprise,
    test_supplier,
):
    app.config["WECHAT_CALLBACK_TOKEN"] = TOKEN
    quote = IntentQuote(
        buyer_id=test_enterprise.id,
        seller_id=test_supplier.id,
        product_name="精密连接器",
        status="pending",
        buyer_confirmed=True,
    )
    db.session.add(quote)
    db.session.commit()

    response = client.post(
        _callback_url(),
        data=_wechat_xml(
            f"确认报价 #{quote.id} 单价12.8元 含税13% 交期25天",
            msg_id="quote-unbound-1",
        ),
        content_type="application/xml",
    )

    assert response.status_code == 200
    assert "未绑定" in _reply_content(response)
    db.session.refresh(quote)
    assert quote.status == "pending"


def test_callback_receipt_cleanup_removes_only_expired_rows(app, _db):
    now = datetime.utcnow()
    db.session.add_all(
        [
            ExternalCallbackReceipt(
                provider="wechat_service_account",
                event_key="old-completed",
                status="completed",
                created_at=now - timedelta(days=45),
                completed_at=now - timedelta(days=45),
            ),
            ExternalCallbackReceipt(
                provider="work_wechat",
                event_key="stale-processing",
                status="processing",
                created_at=now - timedelta(hours=30),
            ),
            ExternalCallbackReceipt(
                provider="wechat_service_account",
                event_key="recent-completed",
                status="completed",
                created_at=now - timedelta(days=2),
                completed_at=now - timedelta(days=2),
            ),
            ExternalCallbackReceipt(
                provider="work_wechat",
                event_key="active-processing",
                status="processing",
                created_at=now - timedelta(minutes=5),
            ),
        ]
    )
    db.session.commit()

    removed = cleanup_callback_receipts(completed_days=30, processing_hours=24, now=now)

    assert removed == 2
    assert {row.event_key for row in ExternalCallbackReceipt.query.all()} == {
        "recent-completed",
        "active-processing",
    }
