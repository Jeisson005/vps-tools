"""Minimal LLM client for transparent AI calls.

Each AI "account" holds its own base_url/api_key/model (managed in the Admin
Panel), so tasks/agents never have to ask the user for keys.
"""
from typing import Optional
import httpx


class AiClient:
    def __init__(self, base_url: str = "", api_key: str = "", model: str = ""):
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or ""
        self.model = model or "gpt-4o-mini"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url)

    def complete(self, prompt: str, system: Optional[str] = None, max_tokens: int = 1024) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages, "max_tokens": max_tokens},
            timeout=120.0,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"AI error ({resp.status_code}): {resp.text[:300]}")
        return str(resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")).strip()

    async def test_connection(self) -> dict:
        try:
            sample = self.complete("Responde solo: ok", max_tokens=5)
            return {"ok": True, "message": "AI provider responde.", "details": {"model": self.model, "sample": sample[:40]}}
        except Exception as e:
            return {"ok": False, "message": f"Error de conexión con AI: {e}", "details": {"error": str(e)}}
