"""Tests du fournisseur SoleasPay v3 (sans appel réseau réel)."""
import hashlib

import pytest

from app.payments.providers.soleaspay import SoleasPayProvider


def test_soleaspay_normalize_status(app):
    p = SoleasPayProvider()
    with app.app_context():
        assert p.normalize_status("SUCCESS") == "successful"
        assert p.normalize_status("RECEIVED") == "processing"
        assert p.normalize_status("REFUND") == "failed"
        assert p.normalize_status("inconnu") == "pending"


def test_soleaspay_process_webhook(app):
    p = SoleasPayProvider()
    with app.app_context():
        payload = {
            "success": True,
            "status": "SUCCESS",
            "data": {
                "reference": "MLS123",
                "external_reference": "DEP-ABC",
                "amount": 1000,
                "currency": "XAF",
            },
        }
        ev = p.process_webhook(payload)
        assert ev["reference"] == "DEP-ABC"
        assert ev["external_ref"] == "MLS123"
        assert ev["status"] == "successful"
        assert ev["amount"] == 1000


def test_soleaspay_verify_signature(app):
    p = SoleasPayProvider()
    with app.app_context():
        app.config["SOLEASPAY_WEBHOOK_SECRET"] = "mon-secret"
        expected = hashlib.sha512(b"mon-secret").hexdigest()

        class ReqOK:
            headers = {"x-private-key": expected}

        class ReqBad:
            headers = {"x-private-key": "mauvais"}

        assert p.verify_signature(ReqOK()) is True
        assert p.verify_signature(ReqBad()) is False


def test_soleaspay_initiate_deposit(app, db, monkeypatch):
    import requests

    from app.models import Deposit

    captured = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "success": True,
                "code": 200,
                "status": "PROCESSING",
                "data": {"reference": "MLS2021B", "external_reference": "DEP-TEST", "amount": "3000", "currency": "XAF"},
                "message": "transaction processing",
            }

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(requests, "post", fake_post)

    with app.app_context():
        app.config["SOLEASPAY_API_KEY"] = "cle-test"
        deposit = Deposit(
            user_id=1, amount=3000, currency="XOF", country="Benin",
            operator="MTN", phone_number="690000001", provider="soleaspay",
            reference="DEP-TEST", status="pending", service_id=35,
        )
        p = SoleasPayProvider()
        result = p.initiate_deposit(deposit)

    assert result["external_ref"] == "MLS2021B"
    assert deposit.external_ref == "MLS2021B"
    assert deposit.status == "processing"
    assert captured["headers"]["x-api-key"] == "cle-test"
    assert captured["headers"]["service"] == "35"
    assert captured["json"]["order_id"] == "DEP-TEST"
    assert captured["json"]["wallet"] == "690000001"
