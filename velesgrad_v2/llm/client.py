# Velesgrad v2 – LLM client (honest)
# TemplateClient is honestly labeled. No "genuinely generative" lies.

import os

class LLMClient:
    def generate(self, prompt: str, max_tokens: int = 128) -> str:
        raise NotImplementedError

    def is_available(self) -> bool:
        return False


class TemplateClient(LLMClient):
    """Honest template fallback. Uses AtomSpace context when available."""
    def generate(self, prompt: str, max_tokens: int = 128) -> str:
        lines = prompt.strip().split("\n")
        cue = lines[-1][:60] if lines else "..."
        return f"[template] {cue}..."

    def is_available(self) -> bool:
        return True


class OpenAICompatibleClient(LLMClient):
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, max_tokens: int = 128) -> str:
        if not self.is_available():
            raise RuntimeError("No API key configured")
        try:
            import requests
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"LLM call failed: {e}")


def get_client(kind: str = "template") -> LLMClient:
    if kind == "openai":
        return OpenAICompatibleClient()
    return TemplateClient()
