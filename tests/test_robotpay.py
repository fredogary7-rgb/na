"""Tests du fournisseur RobotPay (WestPay) — sans appel réseau réel."""
import hashlib
import hmac
import json

from app.payments.providers.robotpay import RobotPayProvider


def test_robotpay_checkout_url(app):
    p = RobotPayProvider()
    with app.app_context():
        app.config["ROBOTPAY_MERCHANT_SLUG"] = "nectarpro"
        app.config["ROBOTPAY_RETURN_URL"] = "https://namara.win/payments/robotpay/return"
        url = p.checkout_url(3000, "Niger", "DEP-TEST")
        assert "checkout1.westpay.cfd/pay" in url
        assert "merchant=nectarpro" in url
        assert "amount=3000" in url
        assert "country=Niger" in url
        assert "DEP-TEST" in url  # la référence est dans l'URL de retour (encodée)


def test_robotpay_verify_signature(app):
    p = RobotPayProvider()
    with app.app_context():
        app.config["ROBOTPAY_WEBHOOK_SECRET"] = "59a804421308f3192d1c336fd62269f37edef2433acf44b7ec2317865bc4499d"
        body = json.dumps({"event": "payment.confirmed", "txId": "TM-1", "amount": 3000, "currency": "XOF"}).encode()
        parsed = json.loads(body)
        compact = json.dumps(parsed, separators=(",", ":"), ensure_ascii=True)
        expected = hmac.new(
            b"59a804421308f3192d1c336fd62269f37edef2433acf44b7ec2317865bc4499d",
            compact.encode(),
            hashlib.sha256,
        ).hexdigest()

        class ReqOK:
            headers = {"X-RobotPay-Signature": expected}

            def get_data(self):
                return body

        class ReqBad:
            headers = {"X-RobotPay-Signature": "wrong"}

            def get_data(self):
                return body

        assert p.verify_signature(ReqOK()) is True
        assert p.verify_signature(ReqBad()) is False


def test_robotpay_process_webhook(app):
    p = RobotPayProvider()
    with app.app_context():
        ev = p.process_webhook({"event": "payment.confirmed", "txId": "TM-1", "amount": 3000, "currency": "XOF"})
        assert ev["reference"] == "TM-1"
        assert ev["external_ref"] == "TM-1"
        assert ev["status"] == "successful"
        assert ev["amount"] == 3000
