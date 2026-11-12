# Feedback & Improvement Log — Atelier Agent

How to use this file: keep every piece of feedback, bug report, and
improvement idea here as a structured entry. At the start of a work
session, read the OPEN entries top-down, pick the next one, implement
it, then move it to DONE with the date and a one-line note on the fix.
Entries are written so a human or an AI agent can pick them up cold.

## Entry format

```
### [AREA] Short title
- Reported: YYYY-MM-DD
- Status: OPEN / IN PROGRESS / DONE
- What happened: (observed behavior, exact error text if any)
- Expected: (what should happen instead)
- Fix / notes: (root cause and what was changed, filled in when DONE)
```

Areas: PAYPAL / GENERATION / AGENT / UI / DOCS / PACKAGING

---

## OPEN

### [PAYPAL] Verify capture end-to-end with real generation
- Reported: 2026-11-13
- Status: IN PROGRESS
- What happened: authorize (sandbox) and image generation both verified
  live; the final capture click after a real generated artwork has not
  been confirmed yet.
- Expected: status becomes CAPTURED and a capture ID is shown.
- Fix / notes:

### [DOCS] Add a screenshot / demo GIF to the README
- Reported: 2026-11-13
- Status: OPEN
- What happened: README is text-only; judges skim visually first.
- Expected: one screenshot of the flow (payment hold + artwork) near
  the top of the README.
- Fix / notes:

### [UI] Show a "generating..." state while the image model runs
- Reported: 2026-11-13
- Status: OPEN
- What happened: image generation takes tens of seconds; the page gives
  no feedback during the wait, so it looks frozen.
- Expected: button disables and shows a progress label until the
  artwork renders.
- Fix / notes:

---

## DONE

### [GENERATION] Image models returned "does not exist"
- Reported: 2026-11-13
- Status: DONE (2026-11-13)
- What happened: gpt-image-1 and dall-e-3 both returned HTTP 400
  "The model ... does not exist". Listing /v1/models showed the
  account only exposes the gpt-image-2 generation of models.
- Expected: generation succeeds on current accounts.
- Fix / notes: model chain now tries gpt-image-2 -> gpt-image-1.5 ->
  gpt-image-1-mini -> chatgpt-image-latest -> gpt-image-1 -> dall-e-3
  -> dall-e-2. Verified live: watercolor artwork generated.

### [GENERATION] dall-e-3 rejected the response_format parameter
- Reported: 2026-11-13
- Status: DONE (2026-11-13)
- What happened: HTTP 400 "Unknown parameter: 'response_format'".
- Expected: request accepted.
- Fix / notes: stopped sending response_format; the default hosted-URL
  response is downloaded instead (base64 responses also handled).

### [GENERATION] API errors were opaque ("400 Bad Request")
- Reported: 2026-11-13
- Status: DONE (2026-11-13)
- What happened: failures showed only "HTTP Error 400: Bad Request",
  hiding the provider's actual message, which made debugging guesswork.
- Expected: the provider's error body is shown in the UI.
- Fix / notes: all provider clients now include the error body in the
  raised error; when every model/provider fails, all messages are
  listed together.

### [UI] Returning from PayPal looked like the app had duplicated
- Reported: 2026-11-13
- Status: DONE (2026-11-13)
- What happened: the approval link opened PayPal in a new tab; after
  approval the app loaded in that tab too, so two app pages existed
  and the original tab looked un-updated.
- Expected: one continuous flow in a single tab.
- Fix / notes: approval now navigates in the same tab; PayPal redirects
  back and the app restores the commission state (see next entry).

### [UI] Commission state was lost after the PayPal redirect
- Reported: 2026-11-13
- Status: DONE (2026-11-13)
- What happened: the server authorized the payment in /return, but the
  reloaded page had forgotten the commission ID and showed a fresh
  form, so the authorization never appeared in the UI.
- Expected: after returning, the page shows the AUTHORIZED commission.
- Fix / notes: the commission ID is kept in localStorage; on load the
  page re-fetches and renders its state. A "Start over" button clears
  it. Server state is in memory, so restarting the server mid-flow
  still resets commissions (acceptable for the prototype).

### [PACKAGING] .env was not loaded when running `python3 app.py`
- Reported: 2026-11-13
- Status: DONE (2026-11-13)
- What happened: the app started in DEMO mode even with a filled .env
  file, because nothing loaded it into the environment.
- Expected: placing a .env next to app.py is enough.
- Fix / notes: added a small built-in .env loader to app.py; no
  external dependency needed.
