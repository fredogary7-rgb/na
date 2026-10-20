"""Tests du fournisseur DrimPay v2 (sans appel réseau réel)."""
import hashlib
import hmac
import time

from app.payments.providers.drimpay import DrimPayProvider


def test_drimpay_normalize_status(app):
    p = DrimPayProvider()
    with app.app_context():
        assert p.normalize_status("success") == "successful"
        assert p.normalize_status("pending") == "processing"
        assert p.normalize_status("expired") == "failed"
        assert p.normalize_status("inconnu") == "pending"


def test_drimpay_process_webhook(app):
    p = DrimPayProvider()
    with app.app_context():
        payload = {
            "event": "payin.success",
            "reference": "TG-ABC123",
            "order_id": "DEP-TEST",
            "status": "success",
            "amount": 5000,
            "currency": "XOF",
        }
        ev = p.process_webhook(payload)
        assert ev["reference"] == "DEP-TEST"
        assert ev["external_ref"] == "TG-ABC123"
        assert ev["status"] == "successful"
        assert ev["amount"] == 5000


def test_drimpay_verify_signature(app):
    p = DrimPayProvider()
    with app.app_context():
        app.config["DRIMPAY_WEBHOOK_SECRET"] = "whsec_test_secret"
        body = b'{"event":"payin.success","order_id":"DEP-1","reference":"TG-1","status":"success"}'
        timestamp = str(int(time.time()))
        expected = hmac.new(
            b"whsec_test_secret", f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()

        class ReqOK:
            headers = {"X-DrimPay-Signature": f"t={timestamp},v1={expected}"}

            def get_data(self):
                return body

        class ReqBad:
            headers = {"X-DrimPay-Signature": f"t={timestamp},v1=wrong"}

            def get_data(self):
                return body

        class ReqOld:
            headers = {"X-DrimPay-Signature": "t=1000,v1=whatever"}

            def get_data(self):
                return body

        assert p.verify_signature(ReqOK()) is True
        assert p.verify_signature(ReqBad()) is False
        assert p.verify_signature(ReqOld()) is False


def test_drimpay_initiate_deposit(app, monkeypatch):
    import requests

    from app.models import Deposit

    captured = {}

    class FakeResp:
        status_code = 201

        def json(self):
            return {
                "reference": "TG-ABC123",
                "order_id": "DEP-TEST",
                "status": "pending",
                "amount": 3000,
                "currency": "XOF",
            }

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(requests, "post", fake_post)

    with app.app_context():
        app.config["DRIMPAY_API_KEY"] = "dp_live_sk_test"
        app.config["DRIMPAY_WEBHOOK_URL"] = "https://namara.win/payments/webhook/drimpay"
        deposit = Deposit(
            user_id=1, amount=3000, currency="XOF", country="Togo",
            operator="Mix", phone_number="90000000", provider="drimpay",
            reference="DEP-TEST", status="pending", service_id=37,
        )
        p = DrimPayProvider()
        result = p.initiate_deposit(deposit)

    assert result["external_ref"] == "TG-ABC123"
    assert deposit.status == "processing"
    assert captured["headers"]["Authorization"] == "Bearer dp_live_sk_test"
    assert captured["json"]["order_id"] == "DEP-TEST"
    assert captured["json"]["country_code"] == "TG"
    assert captured["json"]["operator"] == "tmoney"
    assert captured["json"]["phone"] == "+22890000000"
    assert captured["json"]["webhook_url"] == "https://namara.win/payments/webhook/drimpay"
