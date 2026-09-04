"""
Hybrid Error Classifier for Sentinel Tasks (v2.7)
Tier 0: deterministic regex + exit-code map (fast, offline, zero-cost).
Tier 1: optional AI referee (env-gated) only for ambiguous / low-confidence cases.

Categories:
  transient      - Temporary network/service glitch. Retry next cycle, no code fix.
  hitl_required  - 2FA / Captcha / human verification. Pause cleanly, no auto-repair.
  human_required - Invalid credentials, suspended account, billing. Needs human.
  infra          - Host-level problem (disk full, OOM, docker down, missing binary).
                   Do NOT auto-repair code; send runbook hint.
  repairable     - Logic bug, syntax, selector change, schema mismatch. OpenCode may fix.
"""
import json
import logging
import os
import re
import urllib.request
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("sentinel.classifier")


class ErrorCategory(str, Enum):
    TRANSIENT = "transient"
    HITL_REQUIRED = "hitl_required"
    HUMAN_REQUIRED = "human_required"
    INFRA = "infra"
    AUTO_REPAIRABLE = "repairable"


# ---------------------------------------------------------------------------
# Exit-code fast map (before text). 2 = HITL clean pause (handled in runner,
# listed here for completeness in unit tests).
# ---------------------------------------------------------------------------
EXIT_CODE_MAP = {
    2: (ErrorCategory.HITL_REQUIRED, "Pausa limpia HITL (exit 2): el script espero 2FA/Captcha y se pauso sin error."),
    124: (ErrorCategory.TRANSIENT, "Timeout de ejecucion (124): posible saturacion temporal."),
    137: (ErrorCategory.INFRA, "Proceso matado por OOM (137): memoria del VPS agotada."),
    126: (ErrorCategory.INFRA, "Comando no ejecutable (126): permiso o formato invalido."),
    127: (ErrorCategory.INFRA, "Comando no encontrado (127): dependencia o binario ausente."),
}

# Playwright selector timeouts look like network timeouts but are REPAIRABLE.
# If any of these match, NEVER classify as transient on timeout words alone.
SELECTOR_GUARD_PATTERNS = [
    r"waiting\s+for\s+(selector|locator)",
    r"locator\.",
    r"page\.(locator|getby|frame)",
    r"expect\(.*\)\.to",
    r"timeout\s+\d+ms\s+exceeded.*(selector|locator|expect)",
    r"strict\s+mode\s+violation",
    r"element\s+is\s+not\s+(visible|attached|stable)",
    r"target\s+closed",
]

TRANSIENT_PATTERNS = [
    r"timed?\s*out",
    r"connection\s*refused",
    r"connection\s*reset",
    r"network\s*is\s*unreachable",
    r"temporary\s*failure\s*in\s*name\s*resolution",
    r"getaddrinfo\s*EAI_AGAIN",
    r"\b502\b.*bad\s*gateway",
    r"\b503\b.*(unavailable|temporar)",
    r"\b504\b.*gateway\s*timeout",
    r"\b408\b.*request\s*timeout",
    r"\b429\b.*too\s*many\s*requests",
    r"rate\s*limit(ed|er)?",
    r"remote\s*end\s*closed\s*connection",
    r"max\s*retries\s*exceeded",
    r"socket\s*hang\s*up",
    r"econnreset|econnaborted|enotfound|eai_again",
    r"service\s+(temporarily\s+)?unavailable",
    r"server\s+overloaded|try\s+again\s+later|overloaded",
    r"tiempo\s+de\s+espera\s+agotado",
    r"conexi[oó]n\s+(restablecida|rechazada|reiniciada)",
    r"fallo\s+temporal|error\s+temporal|saturaci[oó]n",
    r"SSL:?\s*CERTIFICATE_VERIFY_FAILED",
]

HITL_PATTERNS = [
    r"two-factor",
    r"\b2fa\b",
    r"\botp\b",
    r"authenticator",
    r"turnstile",
    r"recaptcha|hcaptcha|cf[_-]?challenge",
    r"bot\s*detected|datadome|perimeterx|kasada",
    r"security\s*checkpoint",
    r"human\s*verification|verify\s+you\s+are\s+human",
    r"press\s*&\s*hold|i\s*am\s+not\s+a\s+robot",
    r"cloudflare.*(challenge|attention|block)",
    r"verificaci[oó]n\s+humana|captcha",
    r"c[oó]digo\s+de\s+verificaci[oó]n|ingresa\s+tu\s+c[oó]digo",
    r"acceso\s+2fa|doble\s+factor",
]

HUMAN_REQUIRED_PATTERNS = [
    r"authentication\s*failed\s*permanently",
    r"invalid\s*(api\s*key|token|credentials)",
    r"unauthorized[:\s]*401|forbidden[:\s]*403",
    r"token\s+(expired|revoked|invalid)",
    r"credentials\s+expired|session\s+expired\s+permanently",
    r"account\s+(suspended|banned|disabled|locked)",
    r"permission\s*denied\s*\(publickey\)",
    r"fatal:\s*authentication\s*failed",
    r"payment\s+required|billing|quota\s+exceeded|insufficient\s+funds",
    r"cuenta\s+suspendida|credencial\s+inv[aá]lida|no\s+autorizado",
]

INFRA_PATTERNS = [
    r"no\s+space\s+left|disk\s+quota\s+exceeded|enospc",
    r"read-?only\s+file\s+system|erofs",
    r"out\s+of\s+memory|memory\s+exhausted|java heap|killed\b.*oom|oom.?killed",
    r"cannot\s+connect\s+to\s+(the\s+)?docker\s+(daemon|socket)",
    r"docker\s+(daemon|socket).*not|is\s+the\s+docker\s+daemon\s+running",
    r"no\s+such\s+(container|image|volume)",
    r"command\s+not\s+found",
    r"sqlite.*(locked|corrupt|disk\s+i/o)|database\s+is\s+locked",
    r"disco\s+lleno|sin\s+espacio|memoria\s+agotada",
    r"docker\s+no\s+disponible|demonio\s+docker",
]

# Secrets redaction before any AI call / log.
REDACT_RE = re.compile(
    r"(?i)(token|api[_-]?key|bearer|passphrase|password|passwd|secret)\s*[:=]\s*\S+"
)


def redact(text: str, limit: int = 4000) -> str:
    text = REDACT_RE.sub(r"\1=***", text or "")
    if len(text) > limit:
        text = text[-limit:]
    return text


def _matches_any(text: str, patterns) -> Optional[str]:
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return pat
    return None


def _mcp_api_key() -> str:
    """Reuse the MCP gateway key (panel-managed AI). Never logged."""
    key = os.getenv("MCP_API_KEY", "").strip()
    if key:
        return key
    for cand in (
        Path("/home/jeisson/vps-tools/mcp/.env"),
        Path(__file__).resolve().parent.parent.parent / "mcp" / ".env",
    ):
        try:
            if cand.is_file():
                for line in cand.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line.startswith("MCP_API_KEY="):
                        return line.split("=", 1)[1].strip().strip("'\"")
        except Exception:
            continue
    return ""


def _ai_settings():
    """Direct-API fallback config (only if MCP gateway is unreachable)."""
    base = os.getenv("SENTINEL_AI_BASE_URL") or ""
    key = os.getenv("SENTINEL_AI_API_KEY") or ""
    model = os.getenv("SENTINEL_AI_MODEL") or ""
    flag = os.getenv("SENTINEL_AI_ENABLED", "").strip().lower()
    if not (base and key and model) or not flag:
        try:
            from .config import settings as _s

            base = base or (getattr(_s, "AI_BASE_URL", "") or "")
            key = key or (getattr(_s, "AI_API_KEY", "") or "")
            model = model or (getattr(_s, "AI_MODEL", "") or "")
            if not flag:
                flag = "true" if getattr(_s, "AI_ENABLED", False) else ""
        except Exception:
            pass
    return base, key, model, flag


def _ai_enabled() -> bool:
    """AI referee: ON by default reusing MCP panel AI; explicit opt-out wins."""
    flag = os.getenv("SENTINEL_AI_ENABLED", "").strip().lower()
    if not flag:
        try:
            from .config import settings as _s

            if getattr(_s, "AI_ENABLED", False):
                flag = "true"
        except Exception:
            pass
    if flag in ("0", "false", "no", "off"):
        return False
    # MCP gateway key present -> AI available (panel-managed, no extra keys).
    if _mcp_api_key():
        return True
    # Otherwise require direct-API credentials.
    base, key, model, _ = _ai_settings()
    if flag in ("1", "true", "yes", "on"):
        return bool(base and key and model)
    return bool(base and key and model)


def _call_mcp_ai(prompt: str, system: str, max_tokens: int, timeout: float = 20.0) -> Optional[str]:
    """Call panel-managed AI via local MCP gateway. Returns raw text or None."""
    api_key = _mcp_api_key()
    if not api_key:
        return None
    port = os.getenv("MCP_PORT", "8005").strip() or "8005"
    urls = [f"http://127.0.0.1:{port}/mcp", f"http://127.0.0.1:{port}/unified"]
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "sentinel-classify",
            "method": "tools/call",
            "params": {
                "name": "ai_complete",
                "arguments": {"prompt": prompt, "system": system, "max_tokens": max_tokens},
            },
        }
    ).encode("utf-8")
    for url in urls:
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json", "X-API-Key": api_key},
            )
            with urllib.request.urlopen(req, timeout=timeout) as res:
                body = json.loads(res.read().decode("utf-8", errors="replace"))
            result = body.get("result", {}) or {}
            content = result.get("content", []) or []
            if content and isinstance(content[0], dict):
                text = content[0].get("text", "") or ""
                try:
                    inner = json.loads(text)
                    if isinstance(inner, dict) and "text" in inner:
                        return str(inner["text"])
                except Exception:
                    pass
                return text
            return None
        except Exception as e:
            logger.debug(f"MCP AI call failed ({url}): {e}")
            continue
    return None


def _ai_referee(
    exit_code: int,
    stdout_tail: str,
    stderr_tail: str,
    task_context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Tier 1 referee. Primary: panel-managed AI via local MCP gateway.
    Fallback: direct OpenAI-compatible API (SENTINEL_AI_*). None on any failure."""
    try:
        timeout = float(os.getenv("SENTINEL_AI_TIMEOUT", "") or "")
        max_tokens = int(os.getenv("SENTINEL_AI_MAX_TOKENS", "") or "")
    except ValueError:
        timeout, max_tokens = 20.0, 300
    if not timeout or not max_tokens:
        try:
            from .config import settings as _s2

            timeout = timeout or float(getattr(_s2, "AI_TIMEOUT", 20))
            max_tokens = max_tokens or int(getattr(_s2, "AI_MAX_TOKENS", 300))
        except Exception:
            timeout, max_tokens = 20.0, 300

    system = (
        "Eres el clasificador de errores de Sentinel. "
        "Devuelve SOLO JSON valido con claves: category, reason, fix_hint, confidence. "
        "category debe ser uno de: transient, hitl_required, human_required, infra, repairable. "
        "confidence: high, medium o low. reason y fix_hint en espanol, 1 linea cada uno."
    )
    prompt = json.dumps(
        {
            "task": {
                "name": task_context.get("task_name", ""),
                "description": (task_context.get("description", "") or "")[:800],
                "language": task_context.get("language", ""),
                "requires_browser": bool(task_context.get("requires_browser", False)),
            },
            "exit_code": exit_code,
            "stdout_tail": redact(stdout_tail, 1500),
            "stderr_tail": redact(stderr_tail, 2000),
            "hint": (
                "transient=saturacion/red temporal (reintentar); "
                "hitl_required=2FA/captcha; human_required=credencial/cuenta/facturacion; "
                "infra=disco/memoria/docker/binario ausente (NO editar codigo); "
                "repairable=bug/sintaxis/selector/esquema (si se puede arreglar codigo). "
                "Respeta 'description': si el fallo rompe el objetivo descrito, es repairable salvo infra/credencial."
            ),
        },
        ensure_ascii=False,
    )
    text: Optional[str] = _call_mcp_ai(prompt, system, max_tokens, timeout)
    if text is None:
        base_url, api_key, model, _flag = _ai_settings()
        base_url = (base_url or "").rstrip("/")
        if not (base_url and api_key and model):
            return None
        payload = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": 0,
            }
        ).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as res:
                body = json.loads(res.read().decode("utf-8", errors="replace"))
            text = (
                body.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
            ).strip()
        except Exception as e:
            logger.debug(f"AI referee skipped/failed: {e}")
            return None
    try:
        text = (text or "").strip()
        # Tolerate ```json fences.
        if "```" in text:
            m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if m:
                text = m.group(1)
        data = json.loads(text)
        cat = str(data.get("category", "")).strip().lower()
        allowed = {c.value for c in ErrorCategory}
        if cat not in allowed:
            return None
        conf = str(data.get("confidence", "medium")).strip().lower()
        if conf not in ("high", "medium", "low"):
            conf = "medium"
        return {
            "category": ErrorCategory(cat),
            "reason": str(data.get("reason", ""))[:300] or "Clasificacion por IA.",
            "fix_hint": str(data.get("fix_hint", ""))[:300],
            "confidence": conf,
            "source": "ai",
        }
    except Exception as e:
        logger.debug(f"AI referee skipped/failed: {e}")
        return None


class ErrorClassifier:
    @classmethod
    def classify(
        cls,
        exit_code: int,
        stdout: str,
        stderr: str,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        task_context = task_context or {}
        combined = f"{stdout or ''}\n{stderr or ''}"
        low = combined.lower()

        # 0. Exit-code fast map (except 2 which runner treats as pause).
        if exit_code in EXIT_CODE_MAP and exit_code != 2:
            cat, reason = EXIT_CODE_MAP[exit_code]
            # 127 with explicit selector text is still repairable, not infra.
            if not (exit_code == 127 and _matches_any(low, SELECTOR_GUARD_PATTERNS)):
                return {
                    "category": cat,
                    "reason": reason,
                    "suggestion": cls._suggestion_for(cat),
                    "confidence": "high",
                    "source": "exit_code",
                    "fix_hint": "",
                }

        # 1. HITL first (never auto-repair a human checkpoint).
        if _matches_any(low, HITL_PATTERNS):
            return {
                "category": ErrorCategory.HITL_REQUIRED,
                "reason": "Se detecto un punto de verificacion humana (2FA / Captcha).",
                "suggestion": "Completar la autenticacion interactiva con el helper HITL (exit 2 en pausa).",
                "confidence": "high",
                "source": "regex",
                "fix_hint": "Usar sentinel_hitl.wait_for_user y salir con codigo 2 si expira.",
            }

        # 2. INFRA before transient (disk/docker/OOM must not be retried as code bugs).
        infra_hit = _matches_any(low, INFRA_PATTERNS)
        if infra_hit:
            # "command not found" pointing at a page selector variable is code, not host.
            if "command not found" in infra_hit and _matches_any(low, SELECTOR_GUARD_PATTERNS):
                pass
            else:
                return {
                    "category": ErrorCategory.INFRA,
                    "reason": "Problema de infraestructura del VPS (disco, memoria, Docker o binario ausente).",
                    "suggestion": "Revisar host: `df -h`, `free -h`, `docker ps`. No editar el script.",
                    "confidence": "high",
                    "source": "regex",
                    "fix_hint": "Liberar disco/memoria o instalar la dependencia faltante.",
                }

        # 3. HUMAN_REQUIRED (credentials / account / billing).
        if _matches_any(low, HUMAN_REQUIRED_PATTERNS):
            return {
                "category": ErrorCategory.HUMAN_REQUIRED,
                "reason": "Credencial invalida, cuenta suspendida o facturacion del servicio externo.",
                "suggestion": "Actualiza las credenciales en Passbolt o en el .env de la tarea.",
                "confidence": "high",
                "source": "regex",
                "fix_hint": "",
            }

        # 4. TRANSIENT — but never when a selector guard matches.
        if _matches_any(low, SELECTOR_GUARD_PATTERNS):
            base = {
                "category": ErrorCategory.AUTO_REPAIRABLE,
                "reason": "Timeout en selector de pagina (Playwright): probable cambio de DOM o espera insuficiente.",
                "suggestion": "OpenCode intentara diagnosticar y auto-reparar el codigo.",
                "confidence": "medium",
                "source": "regex",
                "fix_hint": "Actualizar el selector/localizador y usar esperas explicitas.",
            }
        elif _matches_any(low, TRANSIENT_PATTERNS):
            return {
                "category": ErrorCategory.TRANSIENT,
                "reason": "Fallo temporal de conexion o saturacion en el servicio externo.",
                "suggestion": "La tarea se reintentara en el proximo ciclo. Si persiste, pide a Hermes cambiar la hora.",
                "confidence": "medium",
                "source": "regex",
                "fix_hint": "",
            }
        else:
            base = {
                "category": ErrorCategory.AUTO_REPAIRABLE,
                "reason": "Error en la logica, formato o dependencias del script.",
                "suggestion": "OpenCode intentara diagnosticar y auto-reparar el codigo.",
                "confidence": "low",
                "source": "regex",
                "fix_hint": "",
            }

        # 5. Tier 1: AI referee only for ambiguous (repairable/low) cases.
        if _ai_enabled():
            ai = _ai_referee(exit_code, stdout or "", stderr or "", task_context)
            if ai:
                # Safety rail: AI may never downgrade a guarded selector case to transient.
                if _matches_any(low, SELECTOR_GUARD_PATTERNS) and ai["category"] == ErrorCategory.TRANSIENT:
                    ai["category"] = ErrorCategory.AUTO_REPAIRABLE
                    ai["confidence"] = "low"
                ai.setdefault("suggestion", cls._suggestion_for(ai["category"]))
                return ai

        return base

    @staticmethod
    def _suggestion_for(cat: ErrorCategory) -> str:
        return {
            ErrorCategory.TRANSIENT: "La tarea se reintentara en el proximo ciclo.",
            ErrorCategory.HITL_REQUIRED: "Completar la verificacion interactiva (HITL).",
            ErrorCategory.HUMAN_REQUIRED: "Actualiza credenciales en Passbolt o .env de la tarea.",
            ErrorCategory.INFRA: "Revisar host: `df -h`, `free -h`, `docker ps`. No editar el script.",
            ErrorCategory.AUTO_REPAIRABLE: "OpenCode intentara diagnosticar y auto-reparar el codigo.",
        }[cat]
