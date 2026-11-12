"""Pluggable illustration generation.

Providers are tried in order, and the first success wins:
1. OpenAI Images API (if OPENAI_API_KEY is set) — models tried in order:
   the configured one (default gpt-image-1), then dall-e-3, then dall-e-2.
   Some accounts/projects simply have no image models enabled; in that
   case every model answers "does not exist" and we move on.
2. Google Gemini image model / "Nano Banana" (if GEMINI_API_KEY or
   GOOGLE_API_KEY is set) — model gemini-2.5-flash-image. A free key can
   be created instantly in Google AI Studio.
3. Placeholder generator — clearly labeled, keeps the payment flow
   demonstrable end to end even with no image provider at all.

API error bodies are included in raised errors so failures are diagnosable.
"""
import base64
import hashlib
import json
import os
import urllib.error
import urllib.request

_SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640">
<rect width="640" height="640" fill="{color}"/>
<text x="320" y="300" font-size="28" text-anchor="middle" fill="#ffffff"
 font-family="sans-serif">Placeholder preview</text>
<text x="320" y="340" font-size="16" text-anchor="middle" fill="#ffffff"
 font-family="sans-serif">{label}</text>
</svg>"""


def _post_json(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"HTTP {e.code} from {url}: {detail}") from e


class PlaceholderGenerator:
    name = "placeholder (no image API configured)"

    def generate(self, prompt, revision_note=None):
        seed = hashlib.sha256((prompt + (revision_note or "")).encode()).hexdigest()
        color = "#" + seed[:6]
        label = "revision" if revision_note else "draft"
        svg = _SVG_TEMPLATE.format(color=color, label=label)
        return {"kind": "svg", "data": svg.encode(), "model": self.name}


class OpenAIGenerator:
    name = "OpenAI Images API"
    # Order matters: newer accounts list gpt-image-2 / 1.5 / 1-mini and no
    # longer expose gpt-image-1 or dall-e at all, so try current models
    # first and keep the classic ones as last resorts.
    MODEL_CHAIN = ["gpt-image-2", "gpt-image-1.5", "gpt-image-1-mini",
                   "chatgpt-image-latest", "gpt-image-1", "dall-e-3",
                   "dall-e-2"]

    def __init__(self):
        self.key = os.environ["OPENAI_API_KEY"]
        self.model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2")

    def _try_model(self, model, prompt):
        # No response_format parameter: some accounts reject it, and the
        # defaults (b64 for gpt-image-1, hosted URL for dall-e) both work.
        body = {"model": model, "prompt": prompt, "size": "1024x1024"}
        res = _post_json("https://api.openai.com/v1/images/generations", body,
                         {"Content-Type": "application/json",
                          "Authorization": "Bearer " + self.key})
        item = res["data"][0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("url"):  # download the hosted image
            with urllib.request.urlopen(item["url"], timeout=120) as r:
                return r.read()
        raise RuntimeError("Images API returned neither b64_json nor url")

    def generate(self, prompt, revision_note=None):
        full_prompt = prompt
        if revision_note:
            full_prompt = prompt + "\nRevision requested by the client: " + revision_note
        models = []
        for m in [self.model] + self.MODEL_CHAIN:
            if m not in models:
                models.append(m)
        errors = []
        for model in models:
            try:
                data = self._try_model(model, full_prompt)
                return {"kind": "png", "data": data,
                        "model": "OpenAI " + model}
            except Exception as e:
                errors.append(f"{model}: {e}")
        raise RuntimeError(" | ".join(errors))


class GeminiGenerator:
    name = "Google Gemini (Nano Banana)"
    MODEL = "gemini-2.5-flash-image"

    def __init__(self):
        self.key = (os.environ.get("GEMINI_API_KEY")
                    or os.environ.get("GOOGLE_API_KEY"))

    def generate(self, prompt, revision_note=None):
        full_prompt = prompt
        if revision_note:
            full_prompt = prompt + "\nRevision requested by the client: " + revision_note
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               + self.MODEL + ":generateContent")
        body = {"contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {"responseModalities": ["IMAGE"]}}
        res = _post_json(url, body, {"Content-Type": "application/json",
                                     "x-goog-api-key": self.key})
        for candidate in res.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return {"kind": "png",
                            "data": base64.b64decode(inline["data"]),
                            "model": "Gemini " + self.MODEL}
        raise RuntimeError("Gemini returned no image data: "
                           + json.dumps(res)[:300])


class ChainedGenerator:
    """Try each configured provider in order; report all failures."""

    def __init__(self, providers):
        self.providers = providers
        self.name = " -> ".join(p.name for p in providers)

    def generate(self, prompt, revision_note=None):
        errors = []
        for provider in self.providers:
            try:
                return provider.generate(prompt, revision_note)
            except Exception as e:
                errors.append(f"{provider.name}: {e}")
        raise RuntimeError(" || ".join(errors))


def get_generator():
    providers = []
    if os.environ.get("OPENAI_API_KEY"):
        providers.append(OpenAIGenerator())
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        providers.append(GeminiGenerator())
    if not providers:
        return PlaceholderGenerator()
    if len(providers) == 1:
        return providers[0]
    return ChainedGenerator(providers)
