import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("mcp.clickup")


class ClickUpClient:
    """Minimal ClickUp API v2 client using a personal API token (pk_...).

    Auth: ``Authorization: <api_token>`` header on every request.
    Docs: https://developer.clickup.com/reference
    Hierarchy: Workspace (team) -> Space -> Folder (optional) -> List -> Task.
    """

    BASE_URL = "https://api.clickup.com/api/v2"

    def __init__(self, api_token: str = "", default_team_id: str = ""):
        self.api_token = (api_token or "").strip()
        self.default_team_id = (default_team_id or "").strip()

    def is_configured(self) -> bool:
        return bool(self.api_token)

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": self.api_token, "Content-Type": "application/json"}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> Any:
        if not self.is_configured():
            raise RuntimeError("ClickUp account has no API token configured.")
        url = f"{self.BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.request(method, url, headers=self._headers(), params=params, json=json_body)
        if res.status_code in (200, 201):
            return res.json() if res.content else {}
        if res.status_code == 204:
            return {"ok": True}
        raise RuntimeError(f"ClickUp API error ({res.status_code} {method} {path}): {res.text[:500]}")

    # ---- auth / user ----
    async def get_user(self) -> dict:
        data = await self._request("GET", "/user")
        return data.get("user", data)

    async def test_connection(self) -> Dict[str, Any]:
        try:
            user = await self.get_user()
            teams = await self.list_workspaces()
            return {
                "ok": True,
                "message": f"ClickUp conectado como {user.get('username', '')} ({user.get('email', '')}) · {len(teams)} workspace(s).",
                "details": {"user": {k: user.get(k) for k in ("id", "username", "email")}, "workspaces": len(teams)},
            }
        except Exception as e:
            return {"ok": False, "message": f"Error de conexión con ClickUp: {e}", "details": {"error": str(e)}}

    # ---- workspaces (teams) ----
    async def list_workspaces(self) -> list:
        data = await self._request("GET", "/team")
        out = []
        for t in data.get("teams", []):
            members = []
            for m in t.get("members", []) or []:
                u = (m.get("user") or {}) if isinstance(m, dict) else {}
                if u.get("id") is not None:
                    members.append({
                        "id": u.get("id"),
                        "username": u.get("username", ""),
                        "email": u.get("email", ""),
                    })
            out.append({
                "id": str(t.get("id", "")),
                "name": t.get("name", ""),
                "color": t.get("color", ""),
                "avatar": t.get("avatar"),
                "members_count": len(t.get("members", []) or []),
                "members": members,
            })
        return out

    async def list_team_members(self, team_id: str = "") -> list:
        """Return workspace members (id, username, email) to resolve assignee IDs.

        Uses GET /team (which already embeds members) and filters by team_id
        when provided, so no hardcoded user data is needed in the repo.
        """
        tid = self._resolve_team(team_id)
        data = await self._request("GET", "/team")
        teams = data.get("teams", []) or []
        if tid:
            teams = [t for t in teams if str(t.get("id", "")) == str(tid)]
        members = []
        for t in teams:
            for m in t.get("members", []) or []:
                u = (m.get("user") or {}) if isinstance(m, dict) else {}
                if u.get("id") is None:
                    continue
                try:
                    uid = int(u.get("id"))
                except (TypeError, ValueError):
                    continue
                members.append({
                    "id": uid,
                    "username": u.get("username", ""),
                    "email": u.get("email", ""),
                    "team_id": str(t.get("id", "")),
                })
        # de-dup by id
        seen = set()
        uniq = []
        for m in members:
            if m["id"] in seen:
                continue
            seen.add(m["id"])
            uniq.append(m)
        return uniq

    def _resolve_team(self, team_id: str = "") -> str:
        return (team_id or self.default_team_id or "").strip()

    # ---- spaces ----
    async def list_spaces(self, team_id: str = "", archived: bool = False) -> list:
        tid = self._resolve_team(team_id)
        if not tid:
            raise ValueError("Se requiere 'team_id' (Workspace ID). Usa 'clickup_list_workspaces' para descubrirlo.")
        data = await self._request("GET", f"/team/{tid}/space", params={"archived": str(archived).lower()})
        return [self._fmt_space(s) for s in data.get("spaces", [])]

    async def get_space(self, space_id: str = "") -> dict:
        if not space_id:
            raise ValueError("Se requiere 'space_id'.")
        data = await self._request("GET", f"/space/{space_id}")
        return self._fmt_space(data)

    async def create_space(self, team_id: str = "", name: str = "", **opts) -> dict:
        tid = self._resolve_team(team_id)
        if not tid:
            raise ValueError("Se requiere 'team_id'. Usa 'clickup_list_workspaces' para descubrirlo.")
        if not name:
            raise ValueError("Se requiere 'name' para crear el Space.")
        body: Dict[str, Any] = {"name": name}
        for k in ("color", "private", "admin_can_manage", "multiple_assignees", "features"):
            if opts.get(k) is not None:
                body[k] = opts[k]
        data = await self._request("POST", f"/team/{tid}/space", json_body=body)
        return self._fmt_space(data)

    async def update_space(self, space_id: str = "", **fields) -> dict:
        if not space_id:
            raise ValueError("Se requiere 'space_id'.")
        body = {k: v for k, v in fields.items() if v is not None and k in (
            "name", "color", "private", "admin_can_manage", "archived",
            "multiple_assignees", "features")}
        if not body:
            raise ValueError("Nada que actualizar: provee al menos un campo (name, color, private, archived, ...).")
        data = await self._request("PUT", f"/space/{space_id}", json_body=body)
        return self._fmt_space(data)

    async def delete_space(self, space_id: str = "") -> dict:
        if not space_id:
            raise ValueError("Se requiere 'space_id'.")
        await self._request("DELETE", f"/space/{space_id}")
        return {"id": space_id, "status": "deleted"}

    # ---- folders ----
    async def list_folders(self, space_id: str = "", archived: bool = False) -> list:
        if not space_id:
            raise ValueError("Se requiere 'space_id'. Usa 'clickup_list_spaces' para descubrirlo.")
        data = await self._request("GET", f"/space/{space_id}/folder", params={"archived": str(archived).lower()})
        return [self._fmt_folder(f) for f in data.get("folders", [])]

    async def create_folder(self, space_id: str = "", name: str = "") -> dict:
        if not space_id or not name:
            raise ValueError("Se requieren 'space_id' y 'name'.")
        data = await self._request("POST", f"/space/{space_id}/folder", json_body={"name": name})
        return self._fmt_folder(data)

    # ---- lists ----
    async def list_lists(self, folder_id: str = "", space_id: str = "", archived: bool = False) -> list:
        if folder_id:
            data = await self._request("GET", f"/folder/{folder_id}/list", params={"archived": str(archived).lower()})
            return [self._fmt_list(l) for l in data.get("lists", [])]
        if space_id:
            data = await self._request("GET", f"/space/{space_id}/list", params={"archived": str(archived).lower()})
            return [self._fmt_list(l) for l in data.get("lists", [])]
        raise ValueError("Provee 'folder_id' (listas de un Folder) o 'space_id' (listas sin Folder).")

    async def get_list(self, list_id: str = "") -> dict:
        if not list_id:
            raise ValueError("Se requiere 'list_id'.")
        data = await self._request("GET", f"/list/{list_id}")
        return self._fmt_list(data)

    async def create_list(self, name: str = "", folder_id: str = "", space_id: str = "", **opts) -> dict:
        if not name:
            raise ValueError("Se requiere 'name' para crear la lista.")
        body: Dict[str, Any] = {"name": name}
        for k in ("content", "due_date", "due_date_time", "priority", "assignee", "status"):
            if opts.get(k) is not None:
                body[k] = opts[k]
        if folder_id:
            data = await self._request("POST", f"/folder/{folder_id}/list", json_body=body)
        elif space_id:
            data = await self._request("POST", f"/space/{space_id}/list", json_body=body)
        else:
            raise ValueError("Provee 'folder_id' o 'space_id' como padre de la lista.")
        return self._fmt_list(data)

    async def update_list(self, list_id: str = "", **fields) -> dict:
        if not list_id:
            raise ValueError("Se requiere 'list_id'.")
        body = {k: v for k, v in fields.items() if v is not None and k in (
            "name", "content", "due_date", "due_date_time", "priority",
            "assignee", "status", "archived")}
        if not body:
            raise ValueError("Nada que actualizar: provee al menos un campo (name, content, status, ...).")
        data = await self._request("PUT", f"/list/{list_id}", json_body=body)
        return self._fmt_list(data)

    async def delete_list(self, list_id: str = "") -> dict:
        if not list_id:
            raise ValueError("Se requiere 'list_id'.")
        await self._request("DELETE", f"/list/{list_id}")
        return {"id": list_id, "status": "deleted"}

    # ---- tasks ----
    async def list_tasks(
        self,
        list_id: str = "",
        archived: bool = False,
        page: int = 0,
        order_by: str = "created",
        reverse: bool = True,
        subtasks: bool = True,
        include_closed: bool = True,
        statuses: Optional[List[str]] = None,
    ) -> dict:
        if not list_id:
            raise ValueError("Se requiere 'list_id'.")
        params: Dict[str, Any] = {
            "archived": str(archived).lower(),
            "page": page,
            "order_by": order_by,
            "reverse": str(reverse).lower(),
            "subtasks": str(subtasks).lower(),
            "include_closed": str(include_closed).lower(),
        }
        if statuses:
            params["statuses[]"] = statuses
        data = await self._request("GET", f"/list/{list_id}/task", params=params)
        tasks = data.get("tasks", [])
        return {
            "list_id": list_id,
            "count": len(tasks),
            "last_page": data.get("last_page"),
            "tasks": [self._fmt_task(t) for t in tasks],
        }

    async def get_task(self, task_id: str = "", include_subtasks: bool = True) -> dict:
        if not task_id:
            raise ValueError("Se requiere 'task_id'.")
        data = await self._request(
            "GET", f"/task/{task_id}",
            params={"include_subtasks": str(include_subtasks).lower()},
        )
        return self._fmt_task(data, full=True)

    async def create_task(self, list_id: str = "", name: str = "", **fields) -> dict:
        if not list_id or not name:
            raise ValueError("Se requieren 'list_id' y 'name' para crear la tarea.")
        body: Dict[str, Any] = {"name": name}
        for k in ("description", "assignees", "tags", "status", "priority",
                  "due_date", "due_date_time", "time_estimate", "start_date",
                  "start_date_time", "notify_all", "parent", "links_to",
                  "check_required_custom_fields", "custom_fields"):
            if fields.get(k) is not None:
                body[k] = fields[k]
        # Auto-asignar al dueño del token si el agente no pasó assignees.
        # Evita tareas huérfanas sin hardcodear IDs personales en el repo:
        # el ID se resuelve en runtime vía GET /user.
        if body.get("assignees") is None:
            try:
                me = await self.get_user()
                me_id = me.get("id")
                if me_id is not None:
                    body["assignees"] = [int(me_id)]
            except Exception as e:
                logger.warning(f"clickup create_task auto-assign failed, leaving unassigned: {e}")
        data = await self._request("POST", f"/list/{list_id}/task", json_body=body)
        return self._fmt_task(data, full=True)

    async def update_task(self, task_id: str = "", **fields) -> dict:
        if not task_id:
            raise ValueError("Se requiere 'task_id'.")
        allowed = ("name", "description", "status", "priority", "due_date",
                   "due_date_time", "parent", "time_estimate", "start_date",
                   "start_date_time", "assignees", "archived")
        body = {k: v for k, v in fields.items() if v is not None and k in allowed}
        if not body:
            raise ValueError("Nada que actualizar: provee al menos un campo (name, description, status, priority, due_date, assignees, archived, ...).")
        data = await self._request("PUT", f"/task/{task_id}", json_body=body)
        return self._fmt_task(data, full=True)

    async def delete_task(self, task_id: str = "") -> dict:
        if not task_id:
            raise ValueError("Se requiere 'task_id'.")
        await self._request("DELETE", f"/task/{task_id}")
        return {"id": task_id, "status": "deleted"}

    # ---- comments ----
    async def list_task_comments(self, task_id: str = "") -> list:
        if not task_id:
            raise ValueError("Se requiere 'task_id'.")
        data = await self._request("GET", f"/task/{task_id}/comment")
        return [
            {"id": str(c.get("id", "")), "comment_text": c.get("comment_text", ""),
             "user": (c.get("user") or {}).get("username", ""), "date": c.get("date", "")}
            for c in data.get("comments", [])
        ]

    async def create_task_comment(self, task_id: str = "", comment_text: str = "",
                                  assignee: Optional[int] = None, notify_all: bool = True) -> dict:
        if not task_id or not comment_text:
            raise ValueError("Se requieren 'task_id' y 'comment_text'.")
        body: Dict[str, Any] = {"comment_text": comment_text, "notify_all": notify_all}
        if assignee is not None:
            body["assignee"] = assignee
        data = await self._request("POST", f"/task/{task_id}/comment", json_body=body)
        return {"id": str(data.get("id", "")), "comment_text": data.get("comment_text", ""), "date": data.get("date", "")}

    # ---- formatters (respuestas compactas para no saturar el contexto del LLM) ----
    @staticmethod
    def _fmt_space(s: dict) -> dict:
        return {
            "id": str(s.get("id", "")),
            "name": s.get("name", ""),
            "private": s.get("private"),
            "color": s.get("color"),
            "statuses": [{"status": st.get("status"), "type": st.get("type")} for st in s.get("statuses", []) or []],
        }

    @staticmethod
    def _fmt_folder(f: dict) -> dict:
        return {
            "id": str(f.get("id", "")),
            "name": f.get("name", ""),
            "hidden": f.get("hidden"),
            "lists": [{"id": str(l.get("id", "")), "name": l.get("name", "")} for l in f.get("lists", []) or []],
        }

    @staticmethod
    def _fmt_list(l: dict) -> dict:
        return {
            "id": str(l.get("id", "")),
            "name": l.get("name", ""),
            "content": (l.get("content") or "")[:500],
            "orderindex": l.get("orderindex"),
            "status": l.get("status"),
            "statuses": [{"status": st.get("status"), "type": st.get("type")} for st in l.get("statuses", []) or []],
            "task_count": l.get("task_count"),
            "space": {"id": str(((l.get("space") or {}).get("id")) or "")},
            "folder": {"id": str(((l.get("folder") or {}).get("id")) or "")},
        }

    @staticmethod
    def _fmt_task(t: dict, full: bool = False) -> dict:
        status = t.get("status") or {}
        assignees_raw = t.get("assignees", []) or []
        assignee_names = []
        assignee_ids = []
        assignees_full = []
        for a in assignees_raw:
            if not isinstance(a, dict):
                continue
            username = a.get("username") or a.get("email") or ""
            assignee_names.append(username)
            try:
                aid = int(a.get("id")) if a.get("id") is not None else None
            except (TypeError, ValueError):
                aid = None
            if aid is not None:
                assignee_ids.append(aid)
            assignees_full.append({
                "id": aid,
                "username": a.get("username", ""),
                "email": a.get("email", ""),
            })
        out: Dict[str, Any] = {
            "id": str(t.get("id", "")),
            "custom_id": t.get("custom_id"),
            "name": t.get("name", ""),
            "status": status.get("status", "") if isinstance(status, dict) else status,
            "orderindex": t.get("orderindex"),
            "date_created": t.get("date_created"),
            "date_updated": t.get("date_updated"),
            "due_date": t.get("due_date"),
            "due_date_time": t.get("due_date_time"),
            "start_date": t.get("start_date"),
            "time_estimate": t.get("time_estimate"),
            "parent": str(t.get("parent") or "") or None,
            "priority": (t.get("priority") or {}).get("priority") if isinstance(t.get("priority"), dict) else t.get("priority"),
            "assignees": assignee_names,
            "assignee_ids": assignee_ids,
            "assignees_full": assignees_full,
            "tags": [tg.get("name") for tg in t.get("tags", []) or []],
            "url": t.get("url", ""),
            "list": {"id": str(((t.get("list") or {}).get("id")) or "")},
            "space": {"id": str(((t.get("space") or {}).get("id")) or "")},
            "folder": {"id": str(((t.get("folder") or {}).get("id")) or "")},
        }
        desc = t.get("description") or t.get("text_content") or ""
        out["description"] = desc[:2000] if full else desc[:300]
        if full:
            out["custom_fields"] = [
                {"id": cf.get("id"), "name": cf.get("name"), "type": cf.get("type"), "value": cf.get("value")}
                for cf in t.get("custom_fields", []) or []
            ]
            out["subtasks"] = [{"id": str(s.get("id", "")), "name": s.get("name", "")} for s in t.get("subtasks", []) or []]
        return out
