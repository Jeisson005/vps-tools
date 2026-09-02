"""Minimal LLM helper for transparent AI calls inside tasks/services.

Reads the provider from env so agents/tasks never have to ask the user for keys:
  MCP_AI_BASE_URL  OpenAI-compatible endpoint (default https://api.openai.com/v1)
  MCP_AI_API_KEY   API key (required)
  MCP_AI_MODEL     model id (default gpt-4o-mini)
"""
import os
from typing import Optional
import httpx


def is_configured() -> bool:
    return bool(os.environ.get("MCP_AI_API_KEY") or "")


def complete(prompt: str, system: Optional[str] = None, max_tokens: int = 1024) -> str:
    """Run a single completion and return the assistant text."""
    base = (os.environ.get("MCP_AI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    api_key = os.environ.get("MCP_AI_API_KEY", "")
    model = os.environ.get("MCP_AI_MODEL") or "gpt-4o-mini"
    if not api_key:
        raise RuntimeError("MCP_AI_API_KEY no configurada.")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": messages, "max_tokens": max_tokens},
        timeout=120.0,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"AI error ({resp.status_code}): {resp.text[:300]}")
    return str(resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
