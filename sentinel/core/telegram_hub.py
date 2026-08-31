"""
Telegram Multi-Bot Hub for Sentinel
Routes messages and inline interactive action buttons to the appropriate bot:
🔴 Bot 1: Urgent (Action Required / Broken Tasks)
🟡 Bot 2: Routine (Info / Autofixes / Transient warnings)
🔵 Bot 3: Hermes Agent (Target of 1-click inline deep-link buttons)
🟢 Bot 4: Human-in-the-Loop (2FA / Live Browser Viewer & Timeout callbacks)
"""
import urllib.parse
import urllib.request
import json
import logging
from typing import List, Dict, Optional, Any
from .config import settings

logger = logging.getLogger("sentinel.telegram")


class TelegramHub:
    @staticmethod
    def _send_api(bot_token: str, method: str, payload: dict) -> Optional[dict]:
        """Low-level HTTPS JSON request to the Telegram Bot API."""
        if not bot_token or not settings.TELEGRAM_CHAT_ID:
            logger.warning("Telegram dispatch skipped: missing bot token or chat ID.")
            return None
        url = f"https://api.telegram.org/bot{bot_token}/{method}"
        headers = {"Content-Type": "application/json"}
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                res_body = response.read().decode("utf-8")
                return json.loads(res_body)
        except Exception as e:
            logger.error(f"Telegram API error ({method}): {e}")
            return None

    @classmethod
    def make_hermes_button(cls, label: str, prompt: str) -> Dict[str, str]:
        """
        Creates an Inline Keyboard Button that links directly to 🔵 Bot 3 (Hermes)
        with the suggested prompt pre-filled and ready to send with 1 tap.
        """
        username = settings.BOT_HERMES_USERNAME or "sofia005_hermes_bot"
        encoded_prompt = urllib.parse.quote(prompt)
        deep_link = f"https://t.me/{username}?text={encoded_prompt}"
        return {
            "text": label,
            "url": deep_link
        }

    @classmethod
    def send_urgent(cls, text: str, action_buttons: Optional[List[Dict[str, str]]] = None) -> bool:
        """
        🔴 Bot 1 (Red): Sends critical alerts for unhealed failures and tasks requiring human attention.
        """
        token = settings.BOT_URGENT_TOKEN or settings.BOT_ROUTINE_TOKEN
        reply_markup = None
        if action_buttons:
            reply_markup = {"inline_keyboard": [action_buttons]}

        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": f"🔴 *[SENTINEL URGENTE]*\n\n{text}",
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        res = cls._send_api(token, "sendMessage", payload)
        return bool(res and res.get("ok"))

    @classmethod
    def send_routine(cls, text: str, action_buttons: Optional[List[Dict[str, str]]] = None) -> bool:
        """
        🟡 Bot 2 (Yellow): Sends routine info, successful autofixes, transient notices, and suggestions.
        """
        token = settings.BOT_ROUTINE_TOKEN or settings.BOT_URGENT_TOKEN
        reply_markup = None
        if action_buttons:
            reply_markup = {"inline_keyboard": [action_buttons]}

        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": f"🟡 *[SENTINEL INFO]*\n\n{text}",
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        res = cls._send_api(token, "sendMessage", payload)
        return bool(res and res.get("ok"))

    @classmethod
    def send_hitl_request(cls, session_url: str, task_name: str, reason: str, session_id: str) -> Optional[int]:
        """
        🟢 Bot 4 (Green): Sends 2FA/CAPTCHA live viewer session request with interactive callback button.
        Returns the message_id for subsequent in-place updates.
        """
        token = settings.BOT_HITL_TOKEN or settings.BOT_ROUTINE_TOKEN or settings.BOT_URGENT_TOKEN
        text = (
            f"🟢 *[SENTINEL ACCESO 2FA REQUERIDO]*\n\n"
            f"📋 *Tarea:* `{task_name}`\n"
            f"🔐 *Motivo:* {reason}\n\n"
            f"Por favor abre el navegador en vivo, completa la verificación o 2FA y pulsa el botón de abajo cuando hayas ingresado:"
        )
        buttons = [
            [{"text": "🌐 Abrir Navegador en Vivo", "url": session_url}],
            [{"text": "✅ Ya completé el acceso", "callback_data": f"hitl_done:{session_id}"}]
        ]
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": buttons}
        }
        res = cls._send_api(token, "sendMessage", payload)
        if res and res.get("ok"):
            return res["result"]["message_id"]
        return None

    @classmethod
    def update_hitl_completed(cls, message_id: int, task_name: str) -> bool:
        """
        🟢 Bot 4: Updates the message in-place when user successfully approves the 2FA checkpoint.
        """
        token = settings.BOT_HITL_TOKEN or settings.BOT_ROUTINE_TOKEN
        text = (
            f"🟢 *[SENTINEL 2FA CONCEDIDO]*\n\n"
            f"📋 *Tarea:* `{task_name}`\n"
            f"✅ ¡Acceso verificado por el usuario! Continuando con el flujo automatizado..."
        )
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "message_id": message_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        res = cls._send_api(token, "editMessageText", payload)
        return bool(res and res.get("ok"))

    @classmethod
    def update_hitl_timeout(cls, message_id: int, task_name: str, next_schedule: str) -> bool:
        """
        🟢 Bot 4: Updates the message in-place when the 15-minute wait expires, providing retry & reschedule buttons to Bot 3 (Hermes).
        """
        token = settings.BOT_HITL_TOKEN or settings.BOT_ROUTINE_TOKEN
        text = (
            f"🟢 *[SENTINEL TAREA EN PAUSA]*\n\n"
            f"📋 *Tarea:* `{task_name}`\n"
            f"⏳ *Tiempo de espera agotado:* El flujo requería tu código 2FA pero no se recibió respuesta antes del límite de tiempo. La sesión de navegador se cerró para liberar memoria del servidor.\n\n"
            f"• *Próxima ejecución:* {next_schedule}\n"
            f"• *¿Quieres ejecutarla ahora o ajustar la hora?* Selecciona una opción:"
        )
        retry_prompt = f"Hermes, ejecuta la tarea programada '{task_name}' ahora mismo y abre la sesión de 2FA."
        reschedule_prompt = f"Hermes, recomiéndame a qué horas reprogramar la tarea '{task_name}' para que yo esté disponible para el 2FA y cámbiala."
        
        buttons = [
            [cls.make_hermes_button("▶️ Reintentar ahora con Hermes", retry_prompt)],
            [cls.make_hermes_button("⏰ Cambiar horario de la tarea", reschedule_prompt)]
        ]
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "message_id": message_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": buttons}
        }
        res = cls._send_api(token, "editMessageText", payload)
        return bool(res and res.get("ok"))
