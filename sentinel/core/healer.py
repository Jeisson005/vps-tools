"""
OpenCode Autonomous Healing Engine for Centinela Tasks
Manages headless auto-repair loops, rate limits, non-technical summaries, and safe git rollbacks.
"""
import subprocess
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from .config import settings, LOGS_DIR
from .git_manager import GitManager
from .telegram_hub import TelegramHub

logger = logging.getLogger("sentinel.healer")
STATE_FILE = LOGS_DIR / "healing_state.json"


class Healer:
    @classmethod
    def _load_state(cls) -> Dict[str, Any]:
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    @classmethod
    def _save_state(cls, state: Dict[str, Any]):
        try:
            STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Error saving healing state: {e}")

    @classmethod
    def is_rate_limited(cls, task_id: str) -> bool:
        """
        Checks if the task has exceeded max repair attempts or is in cooldown.
        Avoids attempting hourly fixes on permanently broken tasks.
        """
        state = cls._load_state().get(task_id, {})
        attempts = state.get("consecutive_failures", 0)
        last_attempt_ts = state.get("last_repair_ts", 0)
        now = time.time()
        
        # If already failed max times, check if reminder interval (12-24h) has elapsed
        if attempts >= settings.MAX_REPAIR_ATTEMPTS:
            cooldown_secs = settings.REMINDER_INTERVAL_HOURS * 3600
            if (now - last_attempt_ts) < cooldown_secs:
                return True
        return False

    @classmethod
    def should_send_reminder(cls, task_id: str) -> bool:
        """Determines if a 12-24h reminder should be dispatched to avoid alert spam."""
        state = cls._load_state().get(task_id, {})
        last_alert_ts = state.get("last_alert_ts", 0)
        now = time.time()
        cooldown_secs = settings.REMINDER_INTERVAL_HOURS * 3600
        return (now - last_alert_ts) >= cooldown_secs

    @classmethod
    def record_run_success(cls, task_id: str):
        """Resets failure counts on successful run."""
        state = cls._load_state()
        if task_id in state:
            state[task_id]["consecutive_failures"] = 0
            state[task_id]["status"] = "OK"
            state[task_id]["last_success_ts"] = time.time()
            cls._save_state(state)

    @classmethod
    def record_failure(cls, task_id: str, is_transient: bool = False):
        state = cls._load_state()
        task_state = state.get(task_id, {
            "consecutive_failures": 0,
            "status": "FAILING"
        })
        if not is_transient:
            task_state["consecutive_failures"] = task_state.get("consecutive_failures", 0) + 1
        task_state["last_failure_ts"] = time.time()
        task_state["last_alert_ts"] = time.time()
        state[task_id] = task_state
        cls._save_state(state)

    @classmethod
    def attempt_autorepair(
        cls,
        task_id: str,
        task_name: str,
        task_dir: Path,
        script_path: Path,
        stdout: str,
        stderr: str,
        exit_code: int
    ) -> Dict[str, Any]:
        """
        Executes OpenCode headless auto-repair loop:
        1. Snapshots git state.
        2. Invokes OpenCode with structured context and plain-language summary requirements.
        3. Re-runs the task to verify.
        4. Commits on fix or rolls back on failure.
        """
        if cls.is_rate_limited(task_id):
            logger.info(f"Task '{task_name}' is in auto-heal cooldown (already reached max attempts).")
            # Check if we should send a spaced reminder
            if cls.should_send_reminder(task_id):
                cls.record_failure(task_id)
                msg = (
                    f"⚠️ *Recordatorio de Tarea con Fallo Continuo*\n\n"
                    f"📋 *Tarea:* `{task_name}`\n"
                    f"Esta tarea sigue fallando y agotó los reintentos automáticos.\n"
                    f"¿Deseas que Hermes la analice o la repare manualmente?"
                )
                btn = [TelegramHub.make_hermes_button("🛠️ Diagnosticar con Hermes", f"Hermes, analiza por qué sigue fallando la tarea '{task_name}' y propón una solución.")]
                TelegramHub.send_urgent(msg, btn)
            return {"repaired": False, "reason": "rate_limited"}

        logger.info(f"Initiating OpenCode auto-repair for task '{task_name}' (ID: {task_id})...")
        GitManager.init_task_repo(task_dir)
        
        # Prepare context prompt for OpenCode
        error_context = f"STDOUT:\n{stdout[-1500:]}\n\nSTDERR:\n{stderr[-2000:]}"
        prompt = (
            f"Corrige el error en el script '{script_path.name}' de la tarea '{task_name}'.\n\n"
            f"CONTEXTO DEL ERROR:\n{error_context}\n\n"
            f"INSTRUCCIONES OBLIGATORIAS:\n"
            f"1. Analiza y repara el código del script o dependencias dentro de este directorio.\n"
            f"2. Asegúrate de que el script sea ejecutable y no falle.\n"
            f"3. En tu respuesta final, DEBES incluir una línea que empiece por 'EXPLICACION_RESUMIDA: ' "
            f"con una explicación corta, sencilla y NO TÉCNICA orientada al usuario sobre lo que se corrigió "
            f"(ej. 'Se ajustó el selector de la fecha en la página de pagos para adaptarlo al nuevo diseño')."
        )
        
        opencode_bin = settings.OPENCODE_BIN if Path(settings.OPENCODE_BIN).exists() else "opencode"
        
        try:
            # Run OpenCode in headless non-interactive mode
            cmd = [opencode_bin, "run", "--auto-approve", prompt]
            proc = subprocess.run(cmd, cwd=str(task_dir), capture_output=True, text=True, timeout=180)
            opencode_out = proc.stdout
        except Exception as e:
            logger.error(f"Failed to spawn OpenCode for task '{task_name}': {e}")
            cls.record_failure(task_id)
            return {"repaired": False, "reason": f"opencode_spawn_error: {e}"}

        # Extract non-technical summary
        summary = "Se corrigió un error en el flujo de ejecución de la tarea."
        for line in opencode_out.split("\n"):
            if "EXPLICACION_RESUMIDA:" in line:
                summary = line.split("EXPLICACION_RESUMIDA:", 1)[1].strip()
                break

        # Re-run task to verify fix
        verify_proc = subprocess.run([str(script_path)], cwd=str(task_dir), capture_output=True, text=True, timeout=120)
        
        if verify_proc.returncode == 0:
            # Repair SUCCEEDED! Commit changes and notify 🟡 Bot 2 (Routine)
            commit_hash = GitManager.commit_repair(task_dir, summary)
            cls.record_run_success(task_id)
            
            notice = (
                f"✅ *Tarea Auto-Reparada con Éxito*\n\n"
                f"📋 *Tarea:* `{task_name}`\n"
                f"🛠️ *Ajuste aplicado:* {summary}\n"
                f"🔖 *Versión Git:* `{commit_hash or 'actualizada'}`\n"
                f"📊 *Estado:* Verificación exitosa (el script volvió a funcionar normalmente)."
            )
            btn = [TelegramHub.make_hermes_button("🔍 Ver detalles con Hermes", f"Hermes, muéstrame los cambios que se le hicieron a la tarea '{task_name}'.")]
            TelegramHub.send_routine(notice, btn)
            logger.info(f"Auto-repair SUCCEEDED for task '{task_name}' ({commit_hash}).")
            return {"repaired": True, "summary": summary, "commit": commit_hash}
        else:
            # Repair FAILED! Roll back git modifications and notify 🔴 Bot 1 (Urgent)
            GitManager.rollback_task(task_dir)
            cls.record_failure(task_id)
            
            urgent_msg = (
                f"🚨 *Fallo Crítico No Resuelto en Tarea Programada*\n\n"
                f"📋 *Tarea:* `{task_name}`\n"
                f"❌ *Situación:* La tarea falló y el intento de auto-reparación no tuvo éxito. Se restauró el código original de forma segura para evitar estados corruptos.\n\n"
                f"¿Deseas que Hermes intervenga para investigar el problema a fondo?"
            )
            btn = [TelegramHub.make_hermes_button("🤖 Investigar con Hermes", f"Hermes, investiga el fallo crítico en la tarea '{task_name}' y ayúdame a resolverlo.")]
            TelegramHub.send_urgent(urgent_msg, btn)
            logger.warning(f"Auto-repair FAILED for task '{task_name}'. Rolled back working tree.")
            return {"repaired": False, "reason": "verification_failed_after_fix"}
