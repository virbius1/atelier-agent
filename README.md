# Atelier Agent

Commission an illustration from an AI agent — your payment is only captured
when you approve the artwork.

## What it does

Getting an illustration commissioned is awkward on both sides: clients do not
want to pay in full before seeing anything, and creators do not want to work
unpaid. Atelier Agent replaces the middleman with an AI agent plus PayPal's
authorize/capture flow:

1. A client describes the illustration they want in natural language.
2. The agent creates a PayPal order with `intent=AUTHORIZE` — funds are held,
   **not** captured.
3. The agent interprets the request and generates the artwork.
4. The client previews the result. On approval, the agent **captures** the
   payment and releases the artwork.
5. If the client asks for changes, the agent regenerates while the
   authorization stays in place.

The payment rail is not bolted on: authorize → generate → approve → capture
*is* the product — an escrow-like commission flow built entirely on PayPal's
developer platform.

## Run locally

Requirements: Python 3.10+ (standard library only, no dependencies).

```bash
cp .env.example .env   # fill in your own sandbox values, see below
set -a; source .env; set +a
python3 app.py         # http://localhost:8000
```

Environment variables:

- `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` — a **sandbox** app from
  [developer.paypal.com](https://developer.paypal.com) (Apps & Credentials).
  Without them the app runs in an explicitly labeled DEMO mode that simulates
  the same PayPal state machine locally.
- `OPENAI_API_KEY` — optional. With it, illustrations are really generated via
  the OpenAI Images API; without it, a clearly labeled placeholder generator
  is used so the flow can still be demonstrated.
- `COMMISSION_PRICE_USD` — default `10.00`.

## How it works

- `app.py` — HTTP server and the commission state machine
  (CREATED → AUTHORIZED → GENERATED → CAPTURED, with a revision loop).
- `paypal_client.py` — minimal PayPal Orders API v2 client: OAuth,
  create order (AUTHORIZE), authorize, capture.
- `generator.py` — pluggable generation (OpenAI Images API or placeholder).
- `static/index.html` — the single-page client UI.

## License

MIT — see `LICENSE`.
