"""Atelier Agent — AI illustration commissions with PayPal authorize/capture.

Single-file stdlib server. Run:  python3 app.py  (http://localhost:8000)

State machine per commission:
  CREATED (PayPal order, intent=AUTHORIZE)
  -> AUTHORIZED (buyer approved, funds held, NOT captured)
  -> GENERATED (AI draft ready for preview)
  -> CAPTURED (client approved the artwork; payment captured; full art released)
A revision loop (GENERATED -> GENERATED) keeps the authorization in place.
"""
import json
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _load_dotenv():
    """Load KEY=VALUE pairs from a .env file next to this script."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(),
                                  value.strip().strip('"').strip("'"))


_load_dotenv()

from paypal_client import PayPalClient
from generator import get_generator
from agent_brain import get_brain

PRICE_USD = float(os.environ.get("COMMISSION_PRICE_USD", "10.00"))

paypal = PayPalClient()
generator = get_generator()
brain = get_brain()
commissions = {}  # id -> dict


def public_view(c):
    return {
        "id": c["id"],
        "prompt": c["prompt"],
        "status": c["status"],
        "price_usd": PRICE_USD,
        "paypal_demo_mode": paypal.demo_mode,
        "generator": generator.name,
        "brain": brain.name,
        "image_prompt": c.get("image_prompt", ""),
        "order_id": c.get("order_id", ""),
        "approve_url": c.get("approve_url", ""),
        "authorization_id": c.get("authorization_id", ""),
        "capture_id": c.get("capture_id", ""),
        "has_preview": "art" in c,
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode())

    def log_message(self, *args):  # quiet
        pass

    def do_GET(self):
        if self.path.startswith("/return"):
            # Buyer approved on PayPal's site and was redirected back with
            # ?token=<order_id>. Authorize the order server-side, then go home.
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            order_id = (qs.get("token") or [""])[0]
            target = next((c for c in commissions.values()
                           if c.get("order_id") == order_id), None)
            if target and target["status"] == "CREATED":
                try:
                    res = paypal.authorize_order(order_id)
                    target["authorization_id"] = res["authorization_id"]
                    target["status"] = "AUTHORIZED"
                except Exception:
                    pass
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if self.path.startswith("/cancel"):
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if self.path in ("/", "/index.html"):
            path = os.path.join(os.path.dirname(__file__), "static", "index.html")
            with open(path, "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
            return
        if self.path.startswith("/api/commissions/"):
            cid = self.path.rsplit("/", 1)[-1]
            c = commissions.get(cid)
            if not c:
                self._send(404, {"error": "not found"})
                return
            self._send(200, public_view(c))
            return
        if self.path.startswith("/art/"):
            cid = self.path.split("/")[2]
            c = commissions.get(cid)
            if not c or "art" not in c:
                self._send(404, {"error": "no art"})
                return
            art = c["art"]
            ctype = "image/svg+xml" if art["kind"] == "svg" else "image/png"
            self._send(200, art["data"], ctype)
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        parts = self.path.strip("/").split("/")
        # /api/commissions  |  /api/commissions/<id>/<action>
        if parts[:2] != ["api", "commissions"]:
            self._send(404, {"error": "not found"})
            return
        if len(parts) == 2:
            body = self._json_body()
            prompt = (body.get("prompt") or "").strip()
            if not prompt:
                self._send(400, {"error": "prompt is required"})
                return
            order = paypal.create_order(PRICE_USD, "AI illustration commission")
            cid = uuid.uuid4().hex[:12]
            commissions[cid] = {
                "id": cid, "prompt": prompt, "status": "CREATED",
                "order_id": order["id"], "approve_url": order["approve_url"],
            }
            self._send(201, public_view(commissions[cid]))
            return
        cid, action = parts[2], parts[3] if len(parts) > 3 else ""
        c = commissions.get(cid)
        if not c:
            self._send(404, {"error": "not found"})
            return
        try:
            if action == "authorize":
                res = paypal.authorize_order(c["order_id"])
                c["authorization_id"] = res["authorization_id"]
                c["status"] = "AUTHORIZED"
            elif action == "generate":
                body = self._json_body()
                revision = body.get("revision_note")
                directed = brain.direct(c["prompt"], revision,
                                        c.get("image_prompt"))
                c["image_prompt"] = directed
                art = generator.generate(directed)
                c["art"] = art
                c["status"] = "GENERATED"
            elif action == "capture":
                if c["status"] != "GENERATED":
                    self._send(409, {"error": "artwork must be generated and approved first"})
                    return
                res = paypal.capture_authorization(c["authorization_id"], PRICE_USD)
                c["capture_id"] = res["capture_id"]
                c["status"] = "CAPTURED"
            else:
                self._send(404, {"error": "unknown action"})
                return
        except Exception as e:  # surface PayPal/API errors to the UI
            self._send(502, {"error": str(e)})
            return
        self._send(200, public_view(c))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"Atelier Agent on http://localhost:{port} "
          f"(PayPal demo mode: {paypal.demo_mode}, generator: {generator.name})")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
