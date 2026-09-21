"""
Sentinel <-> Hermes LLM bridge (single source of truth).

ALL Sentinel AI activity (classifier referee, healer via opencode, self-test)
must use the credential / model / endpoint currently configured in Hermes,
read DYNAMICALLY on every call — no caching — so rotating Hermes config
automatically propagates to Sentinel.

Sources (read fresh each time):
  - /home/jeisson/.hermes/.env        -> OPENCODE_GO_API_KEY
  - /home/jeisson/.hermes/config.yaml -> model.base_url / model.default /
                                         model.provider / model.api_mode /
                                         fallback_providers

Stdlib only (no PyYAML in sentinel venv): minimal parser for the small
subset of config.yaml we need.

Secrets are NEVER logged. Error messages are redacted.
"""
import json
import logging
import os
import re
import shutil
import subprocess
import urllib.request
import urllib.error
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("sentinel.hermes_ai")

HERMES_ENV_PATH = Path(os.getenv("HERMES_ENV_PATH", "/home/jeisson/.hermes/.env"))
HERMES_CONFIG_PATH = Path(os.getenv("HERMES_CONFIG_PATH", "/home/jeisson/.hermes/config.yaml"))

# Dedicated opencode provider id for Sentinel (isolated from the user's
# stored credentials: explicit apiKey in config content, never persisted).
SENTINEL_PROVIDER_ID = "sentinel-hermes"
REAL_OPENCODE_CANDIDATES = ("/usr/local/bin/opencode",)

_REDACT_RE = re.compile(r"(?i)(api[_-]?key|bearer|token|secret|password|passwd|passphrase)\s*[:=]\s*\S+")
_ERROR_MARKERS = (
    "invalid credential",
    "upstream request failed",
    "unauthorized",
    "unauthenticated",
    "forbidden",
    "401",
    "403",
    "invalid_api_key",
    "incorrect api key",
)


def redact(text: Any, limit: int = 2000) -> str:
    s = str(text or "")
    s = _REDACT_RE.sub(r"\1=***", s)
    # Mask long oc_sk_/sk- tokens that may appear without a label.
    s = re.sub(r"\b((?:oc_sk_|sk-)[A-Za-z0-9_\-.]{8,})\b", lambda m: m.group(1)[:6] + "***", s)
    if len(s) > limit:
        s = s[-limit:]
    return s


def _read_dotenv(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return out
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip("'\"")
        if k:
            out[k] = v
    return out


def _parse_hermes_model_config(path: Path) -> Dict[str, Any]:
    """Minimal parser: top-level `model:` mapping + `fallback_providers:` list."""
    cfg: Dict[str, Any] = {"provider": "", "model": "", "base_url": "", "api_mode": ""}
    fallbacks: List[Dict[str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return {**cfg, "fallbacks": fallbacks}
    section: Optional[str] = None
    current_fb: Optional[Dict[str, str]] = None
    for raw in lines:
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if indent == 0 and stripped.endswith(":"):
            if section == "fallback_providers" and current_fb:
                fallbacks.append(current_fb)
            section = stripped[:-1]
            current_fb = None
            continue
        if section == "model" and indent == 2 and ":" in stripped:
            k, v = stripped.split(":", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k == "default":
                k = "model"
            if k in cfg:
                cfg[k] = v
        elif section == "fallback_providers":
            if stripped.startswith("- "):
                if current_fb:
                    fallbacks.append(current_fb)
                current_fb = {}
                rest = stripped[2:].strip()
                if ":" in rest:
                    k, v = rest.split(":", 1)
                    current_fb[k.strip()] = v.strip().strip("'\"")
            elif current_fb is not None and ":" in stripped:
                k, v = stripped.split(":", 1)
                current_fb[k.strip()] = v.strip().strip("'\"")
    if current_fb:
        fallbacks.append(current_fb)
    cfg["fallbacks"] = fallbacks
    return cfg


def get_llm_config() -> Dict[str, Any]:
    """Read Hermes LLM config fresh from disk. Raises RuntimeError if incomplete."""
    env = _read_dotenv(HERMES_ENV_PATH)
    model_cfg = _parse_hermes_model_config(HERMES_CONFIG_PATH)
    api_key = env.get("OPENCODE_GO_API_KEY", "").strip().strip("'\"")
    base_url = (model_cfg.get("base_url", "") or "").strip().rstrip("/")
    model = (model_cfg.get("model", "") or "").strip().strip("'\"")
    provider = (model_cfg.get("provider", "") or "").strip()
    missing = []
    if not api_key:
        missing.append("OPENCODE_GO_API_KEY (en %s)" % HERMES_ENV_PATH)
    if not base_url:
        missing.append("model.base_url (en %s)" % HERMES_CONFIG_PATH)
    if not model:
        missing.append("model.default (en %s)" % HERMES_CONFIG_PATH)
    if missing:
        raise RuntimeError("Configuracion LLM de Hermes incompleta: %s" % ", ".join(missing))
    return {
        "provider": provider or "opencode-go",
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "api_mode": model_cfg.get("api_mode", "") or "chat_completions",
        "fallbacks": model_cfg.get("fallbacks", []),
    }


def is_configured() -> bool:
    try:
        get_llm_config()
        return True
    except Exception:
        return False


def describe() -> str:
    """Non-secret summary for logs (model/provider/endpoint only)."""
    try:
        c = get_llm_config()
        return "%s/%s @ %s" % (c["provider"], c["model"], c["base_url"])
    except Exception as e:
        return "no configurado (%s)" % redact(e, 200)


def _http_json(
    url: str,
    api_key: str,
    payload: Optional[dict] = None,
    timeout: float = 20.0,
    extra_headers: Optional[Dict[str, str]] = None,
) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer %s" % api_key,
        "User-Agent": "SentinelHermesBridge/1.0",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            body = ""
        if e.code in (401, 403):
            raise RuntimeError("Credencial de Hermes rechazada por el proveedor (HTTP %s)" % e.code)
        raise RuntimeError("Proveedor LLM HTTP %s: %s" % (e.code, redact(body, 300)))


def check_models(timeout: float = 15.0) -> List[str]:
    """GET {base_url}/models — validates credential + endpoint."""
    c = get_llm_config()
    body = _http_json("%s/models" % c["base_url"], c["api_key"], None, timeout)
    data = body.get("data", []) if isinstance(body, dict) else []
    return [str(m.get("id", "")) for m in data if isinstance(m, dict) and m.get("id")]


def _chat_once(
    c: Dict[str, Any],
    messages: List[Dict[str, str]],
    max_tokens: int,
    timeout: float,
    temperature: float,
) -> str:
    """Single chat request. Returns stripped content (may be empty)."""
    body = _http_json(
        "%s/chat/completions" % c["base_url"],
        c["api_key"],
        {"model": c["model"], "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
        timeout,
        {"x-opencode-session": "sentinel-%s" % uuid.uuid4().hex[:12]},
    )
    try:
        text = body["choices"][0]["message"]["content"] or ""
    except Exception:
        raise RuntimeError("Respuesta inesperada del proveedor: %s" % redact(body, 300))
    return text.strip()


def chat_complete(
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 300,
    timeout: float = 20.0,
    temperature: float = 0,
) -> str:
    """Direct OpenAI-compatible chat completion against Hermes endpoint.

    Robust against reasoning models (e.g. deepseek-v4.1-flash): part of the
    max_tokens budget is spent on reasoning tokens BEFORE any `content` is
    emitted, so a small budget can yield an empty reply non-deterministically
    (finish_reason="length"). We retry with a larger budget before failing.
    """
    c = get_llm_config()
    messages: List[Dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    attempts = (max_tokens, max(max_tokens * 4, 512), max(max_tokens * 8, 1024))
    empty = True
    last_text = ""
    for i, budget in enumerate(attempts):
        # Give reasoning room: only a timeout-hung call stays empty.
        eff_timeout = timeout if i == 0 else max(timeout, timeout * (i + 1) * 0.5)
        last_text = _chat_once(c, messages, budget, eff_timeout, temperature)
        if last_text:
            empty = False
            break
    if empty:
        raise RuntimeError("Respuesta vacia del proveedor (se agoto el presupuesto de tokens)")
    return last_text


def build_opencode_config(llm: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    """Build OPENCODE_CONFIG_CONTENT JSON with a dedicated provider carrying
    the live Hermes credential. Returns (config_json, model_ref)."""
    llm = llm or get_llm_config()
    model_id = llm["model"]
    cfg = {
        "provider": {
            SENTINEL_PROVIDER_ID: {
                "npm": "@ai-sdk/openai-compatible",
                "name": "Sentinel Hermes (dinamico)",
                "options": {"baseURL": llm["base_url"], "apiKey": llm["api_key"]},
                "models": {
                    model_id: {
                        "name": "%s (via Hermes)" % model_id,
                        "tool_call": True,
                        "reasoning": True,
                        "attachment": True,
                        "limit": {"context": 1000000, "output": 32000},
                        "modalities": {"input": ["text"], "output": ["text"]},
                    }
                },
            }
        }
    }
    return json.dumps(cfg), "%s/%s" % (SENTINEL_PROVIDER_ID, model_id)


def find_opencode_bin() -> str:
    for cand in REAL_OPENCODE_CANDIDATES:
        if Path(cand).is_file() and os.access(cand, os.X_OK):
            return cand
    found = shutil.which("opencode")
    if found:
        return found
    raise RuntimeError("Binario opencode no encontrado")


def run_opencode(
    prompt: str,
    cwd: Optional[Path] = None,
    timeout: int = 180,
    model_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """Run headless `opencode run` with the LIVE Hermes credential via a
    dedicated provider (OPENCODE_CONFIG_CONTENT) on a private server
    (--standalone). Deterministic: ignores background daemon + user store.
    Never persists credentials. Returns {ok, returncode, stdout, stderr, model_ref}."""
    llm = get_llm_config()
    config_json, ref = build_opencode_config(llm)
    ref = model_ref or ref
    binary = find_opencode_bin()
    env = {k: v for k, v in os.environ.items() if k != "OPENCODE_API_KEY"}
    env["OPENCODE_CONFIG_CONTENT"] = config_json
    cmd = [binary, "run", "--standalone", "--auto", "-m", ref, prompt]
    logger.info("opencode heal via %s (provider dedicado, server privado)", redact(ref, 120))
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout, stderr, rc = proc.stdout or "", proc.stderr or "", proc.returncode
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": 124, "stdout": "", "stderr": "timeout", "model_ref": ref}
    except Exception as e:
        return {"ok": False, "returncode": 1, "stdout": "", "stderr": redact(e, 300), "model_ref": ref}
    combined = (stdout + "\n" + stderr).lower()
    if rc != 0 or any(m in combined for m in _ERROR_MARKERS):
        logger.warning("opencode heal fallo rc=%s: %s", rc, redact(stderr or stdout, 400))
        return {"ok": False, "returncode": rc, "stdout": stdout, "stderr": stderr, "model_ref": ref}
    return {"ok": True, "returncode": rc, "stdout": stdout, "stderr": stderr, "model_ref": ref}
