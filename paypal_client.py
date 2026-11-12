"""Minimal PayPal Orders API v2 client (sandbox) using only the stdlib.

Flow used by this app:
  create_order(intent="AUTHORIZE") -> buyer approves -> authorize_order
  -> (artwork approved by client) -> capture_authorization

If PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are not set, the client runs in
an explicit DEMO mode that simulates the same state machine locally so the
app flow can be exercised end to end. Demo mode never talks to PayPal.
"""
import base64
import json
import os
import urllib.error
import urllib.request
import uuid

SANDBOX_BASE = "https://api-m.sandbox.paypal.com"


class PayPalClient:
    def __init__(self):
        self.client_id = os.environ.get("PAYPAL_CLIENT_ID", "")
        self.client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "")
        self.base = os.environ.get("PAYPAL_BASE", SANDBOX_BASE)
        self.demo_mode = not (self.client_id and self.client_secret)
        self._token = None

    # -- low level ------------------------------------------------------
    def _request(self, method, path, body=None, basic_auth=False):
        url = self.base + path
        data = None
        headers = {"Content-Type": "application/json"}
        if basic_auth:
            raw = f"{self.client_id}:{self.client_secret}".encode()
            headers["Authorization"] = "Basic " + base64.b64encode(raw).decode()
            data = b"grant_type=client_credentials"
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            headers["Authorization"] = "Bearer " + self._access_token()
            if body is not None:
                data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = resp.read().decode()
                return json.loads(payload) if payload else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            raise RuntimeError(f"PayPal HTTP {e.code} on {path}: {detail}") from e

    def _access_token(self):
        if not self._token:
            res = self._request("POST", "/v1/oauth2/token", basic_auth=True)
            self._token = res["access_token"]
        return self._token

    # -- orders ---------------------------------------------------------
    def create_order(self, amount_usd, description):
        if self.demo_mode:
            order_id = "DEMO-ORDER-" + uuid.uuid4().hex[:12].upper()
            return {"id": order_id, "status": "CREATED",
                    "approve_url": "(demo mode: approval simulated in-app)"}
        body = {
            "intent": "AUTHORIZE",
            "purchase_units": [{
                "amount": {"currency_code": "USD", "value": f"{amount_usd:.2f}"},
                "description": description[:127],
            }],
            "application_context": {
                "return_url": "http://localhost:8000/return",
                "cancel_url": "http://localhost:8000/cancel",
            },
        }
        res = self._request("POST", "/v2/checkout/orders", body)
        approve = next((l["href"] for l in res.get("links", [])
                        if l.get("rel") == "approve"), "")
        return {"id": res["id"], "status": res.get("status", ""), "approve_url": approve}

    def authorize_order(self, order_id):
        if self.demo_mode:
            return {"authorization_id": "DEMO-AUTH-" + uuid.uuid4().hex[:12].upper(),
                    "status": "AUTHORIZED"}
        res = self._request("POST", f"/v2/checkout/orders/{order_id}/authorize", {})
        units = res.get("purchase_units", [])
        auth_id = ""
        if units:
            auths = units[0].get("payments", {}).get("authorizations", [])
            if auths:
                auth_id = auths[0].get("id", "")
        return {"authorization_id": auth_id, "status": res.get("status", "")}

    def capture_authorization(self, authorization_id, amount_usd):
        if self.demo_mode:
            return {"capture_id": "DEMO-CAPTURE-" + uuid.uuid4().hex[:12].upper(),
                    "status": "COMPLETED"}
        body = {"amount": {"currency_code": "USD", "value": f"{amount_usd:.2f}"},
                "final_capture": True}
        res = self._request(
            "POST", f"/v2/payments/authorizations/{authorization_id}/capture", body)
        return {"capture_id": res.get("id", ""), "status": res.get("status", "")}
