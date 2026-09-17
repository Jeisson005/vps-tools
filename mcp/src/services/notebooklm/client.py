"""NotebookLM (Gemini Notebook) client for the MCP Gateway.

Wraps the community ``notebooklm-py`` CLI (teng-lin/notebooklm-py) as a
subprocess so the gateway reuses the same battle-tested business logic
(batchexecute RPC, cookie handling, JSON envelopes) instead of
re-implementing Google's undocumented protocol.

Auth model (headless-friendly, 100% panel-configurable):
  - Each gateway account maps to one ``notebooklm-py`` profile stored under
    ``<MCP_DATA_DIR>/notebooklm/profiles/<slug>/storage_state.json``.
  - The panel stores the full ``storage_state.json`` content as the
    ``auth_json`` secret (paste it from a local ``notebooklm login`` run).
  - No browser / Playwright is needed inside the container.

Obtaining ``auth_json`` (once, on any PC with a browser):
  1. ``uv tool install "notebooklm-py[browser]"``
  2. ``notebooklm login`` (or ``notebooklm login --browser-cookies chrome``)
  3. Copy ``~/.notebooklm/profiles/default/storage_state.json`` content
  4. Paste it into the gateway Admin Panel (NotebookLM -> Add account).

Unofficial API disclaimer: NotebookLM has no official consumer API; this
uses undocumented endpoints that Google can change without notice. Best
for personal projects and prototypes.
"""

import asyncio
import contextlib
import fcntl
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("mcp.notebooklm")

BASE_SUBDIR = "notebooklm"
DEFAULT_TIMEOUT = 120
ASK_TIMEOUT = 180
ADD_TIMEOUT = 180
#: How long a CLI invocation waits for the per-profile lock before failing.
#: notebooklm-py rotates ``__Secure-1PSIDTS`` on every request and writes the
#: jar back: two concurrent processes presenting the same rotating cookie make
#: Google treat the replay as a stolen session and sign the account out
#: ("Authentication expired or invalid" minutes after a burst of parallel
#: calls). Serialize every CLI run per profile instead of running them in
#: parallel — the lock is held for the whole subprocess lifetime.
LOCK_TIMEOUT = 600


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", (value or "").strip().lower()).strip("-")
    return slug or "account"


def _base_dir() -> str:
    root = os.environ.get("MCP_DATA_DIR", "./data")
    path = os.path.join(root, BASE_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def _profile_for(instance_id: str) -> str:
    return _slugify(instance_id)[:40]


class NotebookLMClient:
    """Thin async wrapper around one stored NotebookLM auth profile."""

    def __init__(
        self,
        auth_json: str = "",
        email: str = "",
        language: str = "",
        profile: str = "default",
        instance_id: str = "",
    ):
        self.auth_json = (auth_json or "").strip()
        self.email = (email or "").strip()
        self.language = (language or "").strip()
        self.profile = _slugify(profile) or "default"
        self.instance_id = (instance_id or "").strip()
        self._binary_warned = False

    # -- lifecycle ------------------------------------------------------
    def is_configured(self) -> bool:
        if not self.auth_json:
            return False
        try:
            payload = json.loads(self.auth_json)
            cookies = payload.get("cookies", [])
            return isinstance(cookies, list) and len(cookies) > 0
        except Exception:
            return False

    def ensure_profile(self) -> str:
        """Materialize storage_state.json for this profile. Returns profile dir.

        The CLI OWNS this file after the first write: notebooklm-py rotates
        ``__Secure-1PSIDTS`` server-side and persists the rotated jar. Rewriting the
        file from the panel's stored ``auth_json`` on every call reverts that rotation,
        and Google then rejects the stale cookie with
        "Authentication expired or invalid" (orphaning a login that was fine).
        So the panel copy is only a **bootstrap**: it is written when the profile is
        empty, or when the panel's ``auth_json`` changed while the CLI had not touched
        the file since our last write here (sidecar hash + mtime guard).
        """
        base = _base_dir()
        prof_dir = os.path.join(base, "profiles", self.profile)
        os.makedirs(prof_dir, exist_ok=True)
        try:
            os.chmod(prof_dir, 0o700)
        except Exception:
            pass
        target = os.path.join(prof_dir, "storage_state.json")
        stamp = os.path.join(prof_dir, ".panel_auth_hash")
        try:
            payload = json.loads(self.auth_json) if self.auth_json else {}
        except Exception as e:
            raise RuntimeError(f"auth_json no es un JSON válido: {e}")
        # Only rewrite when content changed (avoid churning mtime).
        new_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        incoming = hashlib.sha256(new_bytes).hexdigest()
        last_written = ""
        try:
            with open(stamp, "r", encoding="utf-8") as f:
                last_written = f.read().strip()
        except FileNotFoundError:
            pass
        if os.path.exists(target) and incoming == last_written:
            # Auth unchanged in the panel: leave the CLI-refreshed jar alone.
            return prof_dir
        # The CLI owns this file. It rotates __Secure-1PSIDTS on every call and persists
        # the jar, and `scripts/notebooklm-login.sh` writes it from inside the container
        # on a fresh login. Rewriting it from the panel's snapshot would revert a live
        # session (Google answers "Authentication expired or invalid") — so only
        # materialise the panel copy when the file carries nothing newer than our last
        # write here.
        if os.path.exists(target):
            try:
                stamp_mtime = os.path.getmtime(stamp)
            except OSError:
                stamp_mtime = 0.0
            try:
                if os.path.getmtime(target) > stamp_mtime:
                    logger.info(
                        "notebooklm profile='%s': el jar del CLI es más reciente que el panel; no se reescribe",
                        self.profile,
                    )
                    return prof_dir
                with open(target, "rb") as f:
                    if f.read() == new_bytes:
                        self._write_stamp(stamp, incoming)
                        return prof_dir
            except OSError:
                return prof_dir
        with open(target, "wb") as f:
            f.write(new_bytes)
        try:
            os.chmod(target, 0o600)
        except Exception:
            pass
        self._write_stamp(stamp, incoming)
        return prof_dir

    @staticmethod
    def _write_stamp(path: str, value: str) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(value)
            os.chmod(path, 0o600)
        except Exception:
            pass

    @staticmethod
    def _find_binary() -> Optional[str]:
        return shutil.which("notebooklm")

    # -- session ownership ----------------------------------------------
    @contextlib.contextmanager
    def _profile_lock(self, prof_dir: str):
        """One CLI process at a time per profile.

        notebooklm-py rotates ``__Secure-1PSIDTS`` on every request and writes the
        jar back. Two concurrent processes present the same rotating cookie, so
        Google sees a replay, treats it as a stolen session and signs the account
        out minutes later ("Authentication expired or invalid"). The lock covers
        the whole subprocess lifetime, not just the spawn.
        """
        lock_path = os.path.join(prof_dir, "cli.lock")
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        deadline = time.time() + LOCK_TIMEOUT
        waited = False
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if not waited:
                        logger.info("notebooklm profile='%s' esperando el lock del CLI", self.profile)
                        waited = True
                    if time.time() > deadline:
                        raise RuntimeError(
                            f"NotebookLM ocupado: otra llamada lleva más de {LOCK_TIMEOUT}s con este perfil. "
                            "Reintenta cuando termine."
                        )
                    time.sleep(0.4)
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def _sync_panel_snapshot(self, prof_dir: str) -> None:
        """Mirror the CLI-rotated jar back into the panel secret (best effort).

        The stored ``auth_json`` is a bootstrap snapshot: if it ever drifts from the
        live jar, ``ensure_profile`` would rewrite the profile with the stale copy
        and Google would reject the reverted rotation. Keeping them equal means a
        rewrite can never revert a valid session.
        """
        if not self.instance_id:
            return
        try:
            target = os.path.join(prof_dir, "storage_state.json")
            with open(target, "r", encoding="utf-8") as f:
                live = f.read().strip()
            if not live or live == self.auth_json:
                return
            payload = json.loads(live)
            if not payload.get("cookies"):
                return
            stamp = os.path.join(prof_dir, ".panel_auth_hash")
            incoming = hashlib.sha256(
                json.dumps(payload, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            from ...core.registry import registry  # local import: avoid cycles

            inst = next(
                (i for i in registry.get_instances("notebooklm")
                 if i.get("instance_id") == self.instance_id),
                None,
            )
            if not inst:
                return
            secrets = dict(inst.get("secrets", {}))
            secrets["auth_json"] = live
            registry.save_instance(
                "notebooklm", self.instance_id, inst.get("enabled", True),
                inst.get("config", {}), secrets,
                is_default=inst.get("is_default", False), name=inst.get("name", ""),
            )
            self._write_stamp(stamp, incoming)
            self.auth_json = live
            logger.info("notebooklm profile='%s' auth_json del panel sincronizado con el jar rotado", self.profile)
        except Exception as e:  # never break a working call over bookkeeping
            logger.debug("notebooklm snapshot sync omitido: %s", e)

    def _env(self) -> Dict[str, str]:
        env = dict(os.environ)
        env["NOTEBOOKLM_HOME"] = _base_dir()
        env.pop("NOTEBOOKLM_AUTH_JSON", None)  # profile files are authoritative
        env.pop("NOTEBOOKLM_PROFILE", None)
        if self.language:
            env["NOTEBOOKLM_HL"] = self.language
        return env

    def _run_sync(
        self,
        args: List[str],
        timeout: int = DEFAULT_TIMEOUT,
        stdin_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        binary = self._find_binary()
        if not binary:
            raise RuntimeError(
                "El binario 'notebooklm' no está instalado en el contenedor. "
                "Reconstruye la imagen (requirements incluye notebooklm-py) con: bash scripts/update.sh"
            )
        prof_dir = self.ensure_profile()
        cmd = [binary, "--quiet", "-p", self.profile] + args
        logger.info(f"notebooklm profile='{self.profile}' cmd={' '.join(args[:3])}...")
        with self._profile_lock(prof_dir):
            try:
                proc = subprocess.run(
                    cmd,
                    input=stdin_text,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=self._env(),
                )
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"NotebookLM tardó más de {timeout}s (timeouts de Google o rate-limit). Reintenta.")
        self._sync_panel_snapshot(prof_dir)
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        if proc.returncode != 0:
            detail = stdout or stderr or f"exit {proc.returncode}"
            raise RuntimeError(f"NotebookLM error: {detail[:800]}")
        if not stdout:
            return {"ok": True}
        try:
            parsed = json.loads(stdout)
            return parsed if isinstance(parsed, dict) else {"result": parsed}
        except json.JSONDecodeError:
            # Last line is sometimes JSON with prose before it.
            for line in reversed(stdout.splitlines()):
                line = line.strip()
                if line.startswith("{") or line.startswith("["):
                    try:
                        parsed = json.loads(line)
                        return parsed if isinstance(parsed, dict) else {"result": parsed}
                    except json.JSONDecodeError:
                        continue
            return {"output": stdout[-4000:]}

    async def _run(
        self,
        args: List[str],
        timeout: int = DEFAULT_TIMEOUT,
        stdin_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(self._run_sync, args, timeout, stdin_text)

    # -- diagnostics ----------------------------------------------------
    async def test_connection(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "ok": False,
                "message": "Cuenta sin auth_json. Pega el contenido de storage_state.json en el panel.",
                "details": {},
            }
        try:
            res = await self._run(["auth", "check", "--test", "--json"], timeout=60)
            err = res.get("error")
            if err is True or res.get("code") in ("AUTH", "UNEXPECTED"):
                return {"ok": False, "message": res.get("message", "Auth inválida"), "details": res}
            # Lightweight second probe: listing notebooks proves end-to-end RPC.
            try:
                nb = await self._run(["list", "--limit", "1", "--json"], timeout=60)
                count = nb.get("count", "?")
                email = self.email or res.get("email", "")
                return {
                    "ok": True,
                    "message": f"NotebookLM conectado ({email or self.profile}). Listado OK (count={count}).",
                    "details": {"auth": res, "list_sample": nb},
                }
            except Exception as e:
                return {"ok": True, "message": f"Auth válida pero 'list' falló: {e}", "details": {"auth": res}}
        except Exception as e:
            msg = str(e)
            hint = ""
            if "AUTH" in msg or "cookie" in msg.lower() or "login" in msg.lower():
                hint = " Re-autentica en tu PC (notebooklm login) y actualiza auth_json en el panel."
            return {"ok": False, "message": f"Error de conexión con NotebookLM: {msg[:400]}.{hint}", "details": {"error": msg[:800]}}

    # -- notebooks ------------------------------------------------------
    async def list_notebooks(self, limit: int = 50) -> Any:
        args = ["list", "--json"]
        if limit and int(limit) > 0:
            args += ["--limit", str(int(limit))]
        return await self._run(args)

    async def create_notebook(self, title: str) -> Any:
        if not (title or "").strip():
            raise ValueError("Se requiere 'title'.")
        return await self._run(["create", title.strip(), "--json"])

    async def _use(self, notebook_id: str) -> Any:
        return await self._run(["use", notebook_id, "--json"])

    async def rename_notebook(self, notebook_id: str, new_title: str) -> Any:
        if not notebook_id or not (new_title or "").strip():
            raise ValueError("Se requieren 'notebook_id' y 'new_title'.")
        return await self._run(["rename", new_title.strip(), "-n", notebook_id, "--json"])

    async def delete_notebook(self, notebook_id: str) -> Any:
        if not notebook_id:
            raise ValueError("Se requiere 'notebook_id'.")
        return await self._run(["delete", "-n", notebook_id, "-y", "--json"])

    async def describe_notebook(self, notebook_id: str) -> Any:
        if not notebook_id:
            raise ValueError("Se requiere 'notebook_id'.")
        try:
            return await self._run(["metadata", "-n", notebook_id, "--json"])
        except Exception:
            # Fallback: notebook list + source list give an equivalent picture.
            notebooks = await self._run(["list", "--json"])
            match = None
            items = notebooks.get("notebooks") or notebooks.get("result") or []
            for nb in items if isinstance(items, list) else []:
                if str(nb.get("id", "")) == notebook_id or str(nb.get("id", "")).startswith(notebook_id):
                    match = nb
                    break
            sources = await self.list_sources(notebook_id)
            return {"notebook": match or {"id": notebook_id}, "sources": sources}

    # -- sources --------------------------------------------------------
    async def list_sources(self, notebook_id: str, limit: int = 50, status: str = "") -> Any:
        if not notebook_id:
            raise ValueError("Se requiere 'notebook_id'.")
        args = ["source", "list", "-n", notebook_id, "--json"]
        if limit and int(limit) > 0:
            args += ["--limit", str(int(limit))]
        if (status or "").strip():
            args += ["--status", status.strip()]
        return await self._run(args)

    async def get_source(self, notebook_id: str, source_id: str) -> Any:
        if not notebook_id or not source_id:
            raise ValueError("Se requieren 'notebook_id' y 'source_id'.")
        return await self._run(["source", "get", source_id, "-n", notebook_id, "--json"])

    async def fulltext_source(self, notebook_id: str, source_id: str, max_chars: int = 15000) -> Any:
        if not notebook_id or not source_id:
            raise ValueError("Se requieren 'notebook_id' y 'source_id'.")
        cap = max(1000, min(int(max_chars or 15000), 60000))
        res = await self._run(
            ["source", "fulltext", source_id, "-n", notebook_id, "--json"],
            timeout=ADD_TIMEOUT,
        )
        text = (
            res.get("fulltext")
            or res.get("text")
            or res.get("content")
            or res.get("result")
            or ""
        )
        if isinstance(text, (dict, list)):
            text = json.dumps(text, ensure_ascii=False)
        text = str(text or "")
        truncated = len(text) > cap
        return {
            "notebook_id": res.get("notebook_id", notebook_id),
            "source_id": source_id,
            "title": res.get("title", ""),
            "char_count": len(text),
            "truncated": truncated,
            "text": text[:cap],
            "raw": {k: v for k, v in res.items() if k not in ("fulltext", "text", "content")} if isinstance(res, dict) else {},
        }

    async def search_sources(self, notebook_id: str, query: str, limit: int = 5) -> Any:
        if not notebook_id or not (query or "").strip():
            raise ValueError("Se requieren 'notebook_id' y 'query'.")
        args = ["source", "search", query.strip(), "-n", notebook_id, "--json"]
        if limit and int(limit) > 0:
            args += ["--limit", str(int(limit))]
        return await self._run(args)

    @staticmethod
    def _extract_source_id(add_result: Any) -> str:
        """Best-effort source-id extraction from `source add --json` output."""
        if isinstance(add_result, dict):
            for key in ("source_id", "id"):
                val = add_result.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            for key in ("source", "result"):
                nested = add_result.get(key)
                if isinstance(nested, dict):
                    for sub in ("source_id", "id"):
                        val = nested.get(sub)
                        if isinstance(val, str) and val.strip():
                            return val.strip()
        return ""

    async def add_source_url(
        self, notebook_id: str, url: str, title: str = "", wait: bool = True
    ) -> Any:
        if not notebook_id or not (url or "").strip():
            raise ValueError("Se requieren 'notebook_id' y 'url'.")
        args = ["source", "add", url.strip(), "-n", notebook_id, "--json"]
        if (title or "").strip():
            args += ["--title", title.strip()]
        added = await self._run(args, timeout=ADD_TIMEOUT)
        if not wait:
            return added
        sid = self._extract_source_id(added)
        if not sid:
            return {"added": added, "wait": "skipped (no source id in add output)"}
        try:
            waited = await self._run(
                ["source", "wait", sid, "-n", notebook_id, "--timeout", "120", "--json"],
                timeout=ADD_TIMEOUT,
            )
            return {"added": added, "wait": waited}
        except Exception as e:
            return {"added": added, "wait_error": str(e)[:400]}

    async def add_source_text(self, notebook_id: str, text: str, title: str) -> Any:
        if not notebook_id or not (text or "").strip() or not (title or "").strip():
            raise ValueError("Se requieren 'notebook_id', 'text' y 'title'.")
        body = text.strip()
        # Long pastes go via stdin ("-") to avoid argv limits.
        if len(body) > 8000:
            return await self._run(
                ["source", "add", "-", "-n", notebook_id, "--title", title.strip(), "--json"],
                timeout=ADD_TIMEOUT,
                stdin_text=body,
            )
        return await self._run(
            ["source", "add", body, "-n", notebook_id, "--title", title.strip(), "--json"],
            timeout=ADD_TIMEOUT,
        )

    # -- chat -----------------------------------------------------------
    async def ask(
        self,
        notebook_id: str,
        question: str,
        source_ids: Optional[List[str]] = None,
        conversation_id: str = "",
    ) -> Any:
        if not notebook_id or not (question or "").strip():
            raise ValueError("Se requieren 'notebook_id' y 'question'.")
        q = question.strip()
        use_stdin = len(q) > 8000
        args = ["ask", "-n", notebook_id, "--json"]
        for sid in source_ids or []:
            if str(sid).strip():
                args += ["-s", str(sid).strip()]
        if (conversation_id or "").strip():
            args += ["-c", conversation_id.strip()]
        args += ["-" if use_stdin else q]
        return await self._run(args, timeout=ASK_TIMEOUT, stdin_text=q if use_stdin else None)

    async def history(self, notebook_id: str, limit: int = 10) -> Any:
        if not notebook_id:
            raise ValueError("Se requiere 'notebook_id'.")
        args = ["history", "-n", notebook_id, "--json"]
        if limit and int(limit) > 0:
            args += ["-l", str(int(limit))]
        return await self._run(args)

    async def suggest_prompts(self, notebook_id: str) -> Any:
        if not notebook_id:
            raise ValueError("Se requiere 'notebook_id'.")
        return await self._run(["suggest-prompts", "-n", notebook_id, "--json"])

    # -- misc -----------------------------------------------------------
    @staticmethod
    def export_template() -> str:
        """Helper printed in docs: how to dump storage_state.json on a PC."""
        return (
            "En tu PC: uv tool install \"notebooklm-py[browser]\" && notebooklm login "
            "&& cat ~/.notebooklm/profiles/default/storage_state.json"
        )

    def diagnose(self) -> Dict[str, Any]:
        """Offline checks (no network): binary present, profile files, cookie names."""
        binary = self._find_binary()
        info: Dict[str, Any] = {
            "binary": binary or "",
            "binary_found": bool(binary),
            "profile": self.profile,
            "configured": self.is_configured(),
        }
        try:
            prof_dir = self.ensure_profile() if self.is_configured() else ""
            info["profile_dir"] = prof_dir
            if prof_dir:
                with open(os.path.join(prof_dir, "storage_state.json"), "r", encoding="utf-8") as f:
                    payload = json.load(f)
                names = [c.get("name", "") for c in payload.get("cookies", []) or []]
                info["cookie_count"] = len(names)
                info["has_SID"] = "SID" in names
                info["has_1PSIDTS"] = "__Secure-1PSIDTS" in names
        except Exception as e:
            info["profile_error"] = str(e)[:300]
        with tempfile.TemporaryDirectory():
            pass
        return info
