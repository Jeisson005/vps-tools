"""
Intelligent Error Classifier for Centinela Tasks
Distinguishes transient network glitches from code/logic bugs and human checkpoints.
"""
import re
from enum import Enum
from typing import Dict, Any


class ErrorCategory(str, Enum):
    TRANSIENT = "transient"          # Temporary network/server outage, rate limits (no code fix)
    HITL_REQUIRED = "hitl_required"  # 2FA, Captcha, human credential input
    HUMAN_REQUIRED = "human_required"# Irrecoverable system failure or missing secret
    AUTO_REPAIRABLE = "repairable"   # Syntax, DOM selector changed, schema mismatch, unhandled logic


TRANSIENT_PATTERNS = [
    r"timed?\s*out",
    r"connection\s*refused",
    r"connection\s*reset",
    r"network\s*is\s*unreachable",
    r"temporary\s*failure\s*in\s*name\s*resolution",
    r"getaddrinfo\s*EAI_AGAIN",
    r"502\s*Bad\s*Gateway",
    r"503\s*Service\s*Unavailable",
    r"504\s*Gateway\s*Timeout",
    r"429\s*Too\s*Many\s*Requests",
    r"rate\s*limit(ed)?",
    r"remote\s*end\s*closed\s*connection",
    r"SSL:?\s*CERTIFICATE_VERIFY_FAILED",
    r"max\s*retries\s*exceeded",
    r"ResourceTemporarilyUnavailable"
]

HITL_PATTERNS = [
    r"two-factor",
    r"2fa",
    r"otp",
    r"authenticator",
    r"turnstile",
    r"recaptcha",
    r"hcaptcha",
    r"bot\s*detected",
    r"security\s*checkpoint",
    r"human\s*verification"
]

HUMAN_REQUIRED_PATTERNS = [
    r"authentication\s*failed\s*permanently",
    r"invalid\s*api\s*key",
    r"account\s*suspended",
    r"permission\s*denied\s*\(publickey\)",
    r"fatal:\s*Authentication\s*failed"
]


class ErrorClassifier:
    @classmethod
    def classify(cls, exit_code: int, stdout: str, stderr: str) -> Dict[str, Any]:
        combined_text = f"{stdout}\n{stderr}".lower()
        
        # 1. Check for Human In The Loop (HITL) checkpoints
        for pattern in HITL_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                return {
                    "category": ErrorCategory.HITL_REQUIRED,
                    "reason": "Se detectó un punto de verificación humana (2FA / Captcha).",
                    "suggestion": "Completar la autenticación interactiva en vivo."
                }
                
        # 2. Check for Transient Network / External Service Glitches
        for pattern in TRANSIENT_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                return {
                    "category": ErrorCategory.TRANSIENT,
                    "reason": "Fallo temporal de conexión o saturación en el servicio externo.",
                    "suggestion": "La tarea se reintentará en el próximo ciclo. Si persiste, puedes pedirle a Hermes cambiar la hora de ejecución."
                }
                
        # 3. Check for Fatal Human-Required failures
        for pattern in HUMAN_REQUIRED_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                return {
                    "category": ErrorCategory.HUMAN_REQUIRED,
                    "reason": "Credencial inválida o cuenta remota suspendida.",
                    "suggestion": "Actualiza las credenciales en Passbolt o en el archivo .env de la tarea."
                }

        # 4. Default to Auto-Repairable by OpenCode
        return {
            "category": ErrorCategory.AUTO_REPAIRABLE,
            "reason": "Error en la lógica, formato o dependencias del script.",
            "suggestion": "OpenCode intentará diagnosticar y auto-reparar el código."
        }
