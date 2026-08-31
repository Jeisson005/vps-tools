"""
Sentinel Polyglot Task Runner & Execution Harness
Executes scripts with scoped environment secrets, intercepts errors, and orchestrates auto-healing.
"""
import os
import sys
import subprocess
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .config import settings, TASKS_DIR, LOGS_DIR, load_env_file
from .git_manager import GitManager
from .classifier import ErrorClassifier, ErrorCategory
from .healer import Healer
from .telegram_hub import TelegramHub

logger = logging.getLogger("sentinel.runner")


class TaskRunner:
    @classmethod
    def load_task_meta(cls, task_id: str) -> Optional[Dict[str, Any]]:
        meta_file = TASKS_DIR / task_id / "task.json"
        if meta_file.exists():
            try:
                return json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    @classmethod
    def save_task_meta(cls, task_id: str, meta: Dict[str, Any]):
        task_dir = TASKS_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    @classmethod
    def run_task(cls, task_id: str, custom_script_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes a task by ID or path, managing environment variables, error classification,
        and the self-healing pipeline.
        """
        task_dir = TASKS_DIR / task_id
        meta = cls.load_task_meta(task_id) or {}
        task_name = meta.get("name", task_id)
        
        # Locate script
        script_path = None
        if custom_script_path and Path(custom_script_path).exists():
            script_path = Path(custom_script_path).resolve()
        elif meta.get("script_file") and (task_dir / meta["script_file"]).exists():
            script_path = (task_dir / meta["script_file"]).resolve()
        else:
            # Look for main.* or run.* in task directory
            for candidate in ["main.py", "main.sh", "main.js", "run.sh", "script.sh", "script.py"]:
                if (task_dir / candidate).exists():
                    script_path = (task_dir / candidate).resolve()
                    break

        if not script_path or not script_path.exists():
            err_msg = f"No se encontró el script ejecutable para la tarea '{task_name}' ({task_id})."
            logger.error(err_msg)
            TelegramHub.send_urgent(f"❌ *Error de Configuración:* {err_msg}")
            return {"success": False, "error": "script_not_found"}

        # Ensure execution permissions
        try:
            os.chmod(script_path, 0o755)
        except Exception:
            pass

        # Prepare scoped environment variables
        env = os.environ.copy()
        task_env_file = task_dir / ".env"
        if task_env_file.exists():
            scoped_vars = load_env_file(task_env_file)
            env.update(scoped_vars)

        # Inject Sentinel context vars
        env["SENTINEL_TASK_ID"] = task_id
        env["SENTINEL_TASK_NAME"] = task_name
        env["SENTINEL_API_URL"] = f"http://127.0.0.1:{settings.SENTINEL_PORT}"
        # Keep backwards compatibility vars
        env["CENTINELA_TASK_ID"] = task_id
        env["CENTINELA_TASK_NAME"] = task_name
        env["CENTINELA_API_URL"] = f"http://127.0.0.1:{settings.SENTINEL_PORT}"
        
        # Determine executable runner
        cmd = []
        ext = script_path.suffix.lower()
        if ext == ".py":
            cmd = [sys.executable, str(script_path)]
        elif ext == ".js":
            cmd = ["node", str(script_path)]
        elif ext == ".sh":
            cmd = ["bash", str(script_path)]
        else:
            cmd = [str(script_path)]

        start_time = time.time()
        logger.info(f"Running task '{task_name}' [{task_id}]...")

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(task_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=meta.get("timeout_seconds", 600)
            )
            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            stdout = ""
            stderr = "Execution timed out."
            exit_code = 124
        except Exception as e:
            stdout = ""
            stderr = f"Execution failed to start: {e}"
            exit_code = 1

        duration = round(time.time() - start_time, 2)

        # ---------------------------------------------------------------------
        # 1. SUCCESS PATH
        # ---------------------------------------------------------------------
        if exit_code == 0:
            Healer.record_run_success(task_id)
            logger.info(f"Task '{task_name}' completed successfully in {duration}s.")
            return {
                "success": True,
                "exit_code": 0,
                "duration": duration,
                "stdout": stdout
            }

        # ---------------------------------------------------------------------
        # 2. FAILURE PATH -> ERROR CLASSIFICATION
        # ---------------------------------------------------------------------
        logger.warning(f"Task '{task_name}' failed with exit code {exit_code}.")
        classification = ErrorClassifier.classify(exit_code, stdout, stderr)
        category = classification["category"]

        # Case A: Transient Network / External Service Glitch
        if category == ErrorCategory.TRANSIENT:
            Healer.record_failure(task_id, is_transient=True)
            notice = (
                f"⚠️ *Fallo Temporal Detectado*\n\n"
                f"📋 *Tarea:* `{task_name}`\n"
                f"🌐 *Diagnóstico:* {classification['reason']}\n"
                f"💡 *Sugerencia:* {classification['suggestion']}"
            )
            reschedule_prompt = f"Hermes, analiza la hora de ejecución de la tarea '{task_name}' y recomiéndame una mejor hora para evitar fallos de saturación en el servicio externo."
            btn = [TelegramHub.make_hermes_button("⏰ Ajustar horario con Hermes", reschedule_prompt)]
            TelegramHub.send_routine(notice, btn)
            return {"success": False, "category": category, "transient": True}

        # Case B: Human Action Required (Irrecoverable without human / credentials)
        if category == ErrorCategory.HUMAN_REQUIRED:
            Healer.record_failure(task_id)
            urgent = (
                f"🚨 *Atención Requerida en Tarea Programada*\n\n"
                f"📋 *Tarea:* `{task_name}`\n"
                f"🔐 *Problema:* {classification['reason']}\n"
                f"👉 *Acción requerida:* {classification['suggestion']}"
            )
            fix_prompt = f"Hermes, ayúdame a actualizar las credenciales de la tarea '{task_name}' usando Passbolt."
            btn = [TelegramHub.make_hermes_button("🔑 Gestionar con Hermes", fix_prompt)]
            TelegramHub.send_urgent(urgent, btn)
            return {"success": False, "category": category, "human_required": True}

        # Case C: Auto-Repairable by OpenCode
        repair_result = Healer.attempt_autorepair(
            task_id=task_id,
            task_name=task_name,
            task_dir=task_dir,
            script_path=script_path,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code
        )
        return {
            "success": repair_result.get("repaired", False),
            "category": category,
            "repair_result": repair_result
        }
