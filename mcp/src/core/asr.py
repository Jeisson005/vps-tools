"""Speech-to-text (ASR) helper.

Mirrors Hermes' ``stt`` config so the MCP uses the SAME transcription backend by
default. Hermes defaults to local ``faster-whisper`` (model ``base``); the MCP
defaults to that too and can be pointed to any OpenAI-compatible endpoint.

Env overrides (all optional):
  MCP_ASR_PROVIDER  local|openai   (default: local)
  MCP_ASR_MODEL     e.g. base | whisper-1 (default: base)
  MCP_ASR_BASE_URL  e.g. https://api.openai.com/v1 (for provider=openai)
  MCP_ASR_API_KEY   api key (for provider=openai)
  MCP_ASR_LANGUAGE  e.g. es (optional hint)
"""
import os
import tempfile
from typing import Optional

_whisper_model = None  # lazy singleton for local provider


def _local_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        model = os.environ.get("MCP_ASR_MODEL", "base")
        _whisper_model = WhisperModel(model, device="cpu", compute_type="int8")
    return _whisper_model


def _transcribe_local(audio_bytes: bytes, language: str = "") -> str:
    model = _local_model()
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    try:
        segments, info = model.transcribe(path, language=language or None)
        return "".join(segment.text for segment in segments).strip()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _transcribe_openai(audio_bytes: bytes, filename: str = "audio.m4a", language: str = "") -> str:
    import base64
    import json
    import httpx

    base_url = (os.environ.get("MCP_ASR_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    api_key = os.environ.get("MCP_ASR_API_KEY", "")
    model = os.environ.get("MCP_ASR_MODEL", "whisper-1")
    if not api_key:
        raise RuntimeError("MCP_ASR_API_KEY no configurada para transcribir (provider=openai).")

    data = {"model": model}
    if language:
        data["language"] = language
    resp = httpx.post(
        f"{base_url}/audio/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        data=data,
        files={"file": (filename, audio_bytes, "audio/mpeg")},
        timeout=120.0,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"ASR error ({resp.status_code}): {resp.text[:300]}")
    return str(resp.json().get("text", "")).strip()


def transcribe(audio_bytes: bytes, filename: str = "audio.m4a", language: str = "") -> str:
    """Transcribe audio bytes to text using the configured provider."""
    if not audio_bytes:
        return ""
    provider = (os.environ.get("MCP_ASR_PROVIDER") or "local").strip().lower()
    lang = language or os.environ.get("MCP_ASR_LANGUAGE", "")
    if provider == "openai":
        return _transcribe_openai(audio_bytes, filename, lang)
    return _transcribe_local(audio_bytes, lang)


def is_configured() -> bool:
    provider = (os.environ.get("MCP_ASR_PROVIDER") or "local").strip().lower()
    if provider == "openai":
        return bool(os.environ.get("MCP_ASR_API_KEY"))
    return True  # local always "configured" (model downloads on first use)
