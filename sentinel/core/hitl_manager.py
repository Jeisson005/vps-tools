"""
Human-in-the-Loop (HITL) Session Waiter & Timeout Manager for Bot 4 (Green)
Listens for user confirmation on 2FA checkpoints via Telegram Long-Polling and manages clean pauses.
"""
import time
import subprocess
import logging
import urllib.request
import json
from typing import Optional, Dict, Any
from .config import settings
from .telegram_hub import TelegramHub

logger = logging.getLogger("sentinel.hitl")


class HitlManager:
    @classmethod
    def wait_for_user_approval(
        cls,
        session_id: str,
        session_url: str,
        task_name: str = "Tarea de Navegación",
        reason: str = "Se requiere verificación 2FA / Login",
        timeout_minutes: Optional[int] = None,
        next_schedule: str = "En el próximo ciclo programado"
    ) -> bool:
        """
        Pauses the script, sends the Live Viewer link to Bot 4 (Green),
        and waits for the user to click 'Ya completé el acceso'.
        Returns True if approved, False if timeout.
        """
        timeout_secs = (timeout_minutes or settings.HITL_TIMEOUT_MINUTES) * 60
        start_time = time.time()
        
        # 1. Send Interactive Message to Bot 4
        msg_id = TelegramHub.send_hitl_request(
            session_url=session_url,
            task_name=task_name,
            reason=reason,
            session_id=session_id
        )
        if not msg_id:
            logger.error("Failed to send HITL message to Telegram Bot 4.")
            return False

        logger.info(f"HITL session {session_id} waiting up to {timeout_minutes or settings.HITL_TIMEOUT_MINUTES} minutes for user approval...")
        
        token = settings.BOT_HITL_TOKEN or settings.BOT_ROUTINE_TOKEN or settings.BOT_URGENT_TOKEN
        offset = None
        target_callback = f"hitl_done:{session_id}"
        
        # 2. Long-polling loop to wait for callback click
        while (time.time() - start_time) < timeout_secs:
            try:
                # Query updates from Telegram with long-polling
                url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=10"
                if offset:
                    url += f"&offset={offset}"
                
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=15) as res:
                    data = json.loads(res.read().decode("utf-8"))
                    
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        
                        # Check callback_query
                        if "callback_query" in update:
                            cb = update["callback_query"]
                            cb_data = cb.get("data", "")
                            cb_id = cb.get("id")
                            
                            if cb_data == target_callback:
                                # Acknowledge callback immediately in Telegram
                                ack_url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
                                ack_payload = json.dumps({
                                    "callback_query_id": cb_id,
                                    "text": "¡Acceso confirmado! Continuando la tarea..."
                                }).encode("utf-8")
                                req_ack = urllib.request.Request(ack_url, data=ack_payload, headers={"Content-Type": "application/json"})
                                urllib.request.urlopen(req_ack, timeout=5)
                                
                                # Update original message in Bot 4
                                TelegramHub.update_hitl_completed(msg_id, task_name)
                                logger.info(f"HITL session {session_id} approved by user.")
                                return True
            except Exception as e:
                logger.debug(f"HITL polling tick exception (retrying): {e}")
                time.sleep(2)
                
            time.sleep(2)
            
        # 3. Timeout handling (Pausa Limpia)
        logger.warning(f"HITL session {session_id} timed out after {timeout_minutes or settings.HITL_TIMEOUT_MINUTES} minutes.")
        
        # Release Steel session to free RAM
        cls._release_steel_session(session_id)
        
        # Update Bot 4 message with explanation and Hermes action buttons
        TelegramHub.update_hitl_timeout(msg_id, task_name, next_schedule)
        
        return False

    @staticmethod
    def _release_steel_session(session_id: str):
        """Releases the Steel Chromium session from memory."""
        try:
            subprocess.run(["steel-session", "release", session_id], capture_output=True, timeout=10)
        except Exception:
            pass
