"""
Isolated Crontab Manager for Sentinel Tasks
Manages scheduled jobs in a dedicated isolated file (sentinel/cron/sentinel.tab)
and installs it to user crontab without interfering with system-wide crontab entries.
"""
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Optional
from .config import CRON_DIR, LOGS_DIR

logger = logging.getLogger("sentinel.cron")
SENTINEL_TAB = CRON_DIR / "sentinel.tab"


class CronManager:
    HEADER_MARKER = "# === SENTINEL ISOLATED MANAGED CRONTAB - DO NOT EDIT MANUALLY ==="
    FOOTER_MARKER = "# === END SENTINEL MANAGED CRONTAB ==="

    @classmethod
    def get_tasks_tab(cls) -> List[Dict[str, str]]:
        """Reads all managed cron entries from sentinel.tab."""
        if not SENTINEL_TAB.exists():
            return []
        
        entries = []
        with open(SENTINEL_TAB, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Line format: <cron_expr (5 fields)> <command> # TASK_ID:<id> TASK_NAME:<name>
                parts = line.split()
                if len(parts) >= 6:
                    cron_expr = " ".join(parts[0:5])
                    cmd = " ".join(parts[5:])
                    task_id = ""
                    task_name = ""
                    if "# TASK_ID:" in cmd:
                        cmd_part, meta_part = cmd.split("# TASK_ID:", 1)
                        cmd = cmd_part.strip()
                        if "TASK_NAME:" in meta_part:
                            t_id, t_name = meta_part.split("TASK_NAME:", 1)
                            task_id = t_id.strip()
                            task_name = t_name.strip()
                        else:
                            task_id = meta_part.strip()
                    entries.append({
                        "cron_expr": cron_expr,
                        "command": cmd,
                        "task_id": task_id,
                        "task_name": task_name,
                        "raw_line": line
                    })
        return entries

    @classmethod
    def sync_to_crontab(cls) -> bool:
        """
        Reads user's active crontab, replaces or appends the Sentinel isolated block,
        and applies it safely.
        """
        if not SENTINEL_TAB.exists():
            SENTINEL_TAB.write_text(f"{cls.HEADER_MARKER}\n{cls.FOOTER_MARKER}\n", encoding="utf-8")
            
        managed_content = SENTINEL_TAB.read_text(encoding="utf-8").strip()

        # Read existing user crontab
        res = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        current_crontab = res.stdout if res.returncode == 0 else ""

        # Strip existing Sentinel block from current crontab
        cleaned_lines = []
        inside_block = False
        for line in current_crontab.splitlines():
            if cls.HEADER_MARKER in line:
                inside_block = True
                continue
            if cls.FOOTER_MARKER in line:
                inside_block = False
                continue
            if not inside_block:
                cleaned_lines.append(line)

        # Assemble new crontab with updated Sentinel block
        new_crontab = "\n".join(cleaned_lines).rstrip()
        if new_crontab:
            new_crontab += "\n\n"
        new_crontab += f"{cls.HEADER_MARKER}\n{managed_content}\n{cls.FOOTER_MARKER}\n"

        # Apply new crontab atomically
        apply_proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
        if apply_proc.returncode == 0:
            logger.info("Crontab successfully synchronized with Sentinel tasks.")
            return True
        else:
            logger.error(f"Failed to apply crontab: {apply_proc.stderr}")
            return False

    @classmethod
    def add_or_update_task(cls, task_id: str, task_name: str, cron_expr: str, command: str) -> bool:
        """Adds or updates a task entry in sentinel.tab and syncs to crontab."""
        entries = cls.get_tasks_tab()
        updated = False
        new_entries = []

        log_file = LOGS_DIR / f"{task_id}.log"
        full_command = f"{command} >> {log_file} 2>&1"
        line_to_add = f"{cron_expr} {full_command} # TASK_ID:{task_id} TASK_NAME:{task_name}"

        for entry in entries:
            if entry["task_id"] == task_id:
                new_entries.append(line_to_add)
                updated = True
            else:
                new_entries.append(entry["raw_line"])

        if not updated:
            new_entries.append(line_to_add)

        SENTINEL_TAB.write_text("\n".join(new_entries) + "\n", encoding="utf-8")
        return cls.sync_to_crontab()

    @classmethod
    def remove_task(cls, task_id: str) -> bool:
        """Removes a task from sentinel.tab and syncs to crontab."""
        entries = cls.get_tasks_tab()
        new_entries = [e["raw_line"] for e in entries if e["task_id"] != task_id]
        SENTINEL_TAB.write_text("\n".join(new_entries) + "\n", encoding="utf-8")
        return cls.sync_to_crontab()
