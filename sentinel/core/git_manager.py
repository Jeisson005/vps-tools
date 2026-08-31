"""
Git Repository & Change Tracking Manager for Sentinel Tasks
Tracks all task modifications and enables safe rollbacks on failed auto-repairs.
"""
import subprocess
from pathlib import Path
from typing import List, Dict, Optional


class GitManager:
    @staticmethod
    def _run_git(task_dir: Path, *args) -> subprocess.CompletedProcess:
        cmd = ["git", "-C", str(task_dir)] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True)

    @classmethod
    def init_task_repo(cls, task_dir: Path, initial_message: str = "Initial task creation") -> bool:
        """Initializes a local git repository inside the task directory if not already present."""
        task_dir.mkdir(parents=True, exist_ok=True)
        git_dir = task_dir / ".git"
        if not git_dir.exists():
            cls._run_git(task_dir, "init", "-q")
            cls._run_git(task_dir, "config", "user.name", "Sentinel AutoHeal")
            cls._run_git(task_dir, "config", "user.email", "sentinel@vps-tools.local")
            
            # Create standard .gitignore for secrets / temp files
            gitignore_path = task_dir / ".gitignore"
            if not gitignore_path.exists():
                gitignore_path.write_text(".env\n__pycache__/\n*.pyc\n*.log\nnode_modules/\n", encoding="utf-8")
            
            cls._run_git(task_dir, "add", "-A")
            cls._run_git(task_dir, "commit", "-m", initial_message, "--quiet")
            return True
        return False

    @classmethod
    def has_uncommitted_changes(cls, task_dir: Path) -> bool:
        """Checks if the working tree has any unstaged/staged modifications."""
        res = cls._run_git(task_dir, "status", "--porcelain")
        return bool(res.stdout.strip())

    @classmethod
    def get_head_commit(cls, task_dir: Path) -> Optional[str]:
        """Gets current HEAD commit hash."""
        res = cls._run_git(task_dir, "rev-parse", "--short", "HEAD")
        return res.stdout.strip() if res.returncode == 0 else None

    @classmethod
    def commit_repair(cls, task_dir: Path, non_technical_summary: str) -> Optional[str]:
        """Commits the auto-repaired code changes with a friendly message."""
        cls._run_git(task_dir, "add", "-A")
        msg = f"AutoHeal: {non_technical_summary}"
        res = cls._run_git(task_dir, "commit", "-m", msg, "--quiet")
        if res.returncode == 0:
            return cls.get_head_commit(task_dir)
        return None

    @classmethod
    def rollback_task(cls, task_dir: Path) -> bool:
        """Discards all working directory changes and restores to last committed HEAD."""
        cls._run_git(task_dir, "reset", "--hard", "HEAD")
        cls._run_git(task_dir, "clean", "-fd")
        return True

    @classmethod
    def get_history(cls, task_dir: Path, limit: int = 10) -> List[Dict[str, str]]:
        """Retrieves recent git commit log for the task."""
        res = cls._run_git(task_dir, "log", f"-n{limit}", "--pretty=format:%h|%ad|%s", "--date=short")
        history = []
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.strip().split("\n"):
                parts = line.split("|", 2)
                if len(parts) == 3:
                    history.append({
                        "commit": parts[0],
                        "date": parts[1],
                        "summary": parts[2]
                    })
        return history
