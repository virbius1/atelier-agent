"""The 'agent' part: interprets the client's words into an image prompt.

- If DEEPSEEK_API_KEY is set, DeepSeek Chat turns a free-form commission
  (and later, revision feedback) into a concrete illustration prompt.
- Otherwise the client's text is passed through unchanged.
"""
import json
import os
import urllib.error
import urllib.request

SYSTEM = (
    "You are an art-direction agent for an illustration commission service. "
    "Convert the client's request into one concrete, vivid image-generation "
    "prompt in English. Include subject, composition, style, lighting and "
    "mood. Output ONLY the prompt, no explanations."
)


class PassthroughBrain:
    name = "passthrough (no LLM configured)"

    def direct(self, client_text, revision_note=None, previous_prompt=None):
        if revision_note:
            return (previous_prompt or client_text) + f". Revision: {revision_note}"
        return client_text


class DeepSeekBrain:
    name = "DeepSeek Chat (art direction)"

    def __init__(self):
        self.key = os.environ["DEEPSEEK_API_KEY"]
        self.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    def direct(self, client_text, revision_note=None, previous_prompt=None):
        if revision_note and previous_prompt:
            user = (f"Original prompt: {previous_prompt}\n"
                    f"Client revision feedback: {revision_note}\n"
                    "Produce the revised image prompt.")
        else:
            user = "Client request: " + client_text
        body = {"model": self.model,
                "messages": [{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": user}],
                "temperature": 0.7}
        req = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self.key},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                res = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            raise RuntimeError(
                f"DeepSeek HTTP {e.code}: {detail}") from e
        return res["choices"][0]["message"]["content"].strip()


def get_brain():
    if os.environ.get("DEEPSEEK_API_KEY"):
        return DeepSeekBrain()
    return PassthroughBrain()
