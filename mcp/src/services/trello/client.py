import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("mcp.trello")


class TrelloClient:
    """Minimal Trello REST API client using API key + user token.

    Auth: ``key`` + ``token`` as query params on every request
    (header ``Authorization: OAuth oauth_consumer_key=..., oauth_token=...``
    is equivalent, but query params are the documented simple path).
    Docs: https://developer.atlassian.com/cloud/trello/guides/rest-api/api-introduction/
    Hierarchy: Workspace (organization) -> Board -> List -> Card (+ comments/members).

    Get credentials: create a Power-Up at https://trello.com/power-ups/admin,
    generate an API key, then a token via
    ``/1/authorize?expiration=never&scope=read,write&response_type=token&key={key}``.
    """

    BASE_URL = "https://api.trello.com/1"

    CARD_FIELDS = (
        "id,name,desc,closed,dateLastActivity,due,dueComplete,pos,"
        "url,shortUrl,idList,idBoard,idMembers,labels"
    )

    def __init__(self, api_key: str = "", api_token: str = ""):
        self.api_key = (api_key or "").strip()
        self.api_token = (api_token or "").strip()

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_token)

    def _auth_params(self, extra: Optional[dict] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"key": self.api_key, "token": self.api_token}
        if extra:
            for k, v in extra.items():
                if v is not None:
                    params[k] = v
        return params

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> Any:
        if not self.is_configured():
            raise RuntimeError("Trello account has no API key/token configured.")
        url = f"{self.BASE_URL}{path}"
        query = self._auth_params(params)
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.request(method, url, params=query, json=json_body)
        if res.status_code in (200, 201):
            return res.json() if res.content else {}
        if res.status_code == 204:
            return {"ok": True}
        if res.status_code in (401, 403):
            raise RuntimeError(
                "Trello auth failed (401/403): API key/token invalid or revoked. "
                "Regenerate the token and update the account in the panel."
            )
        if res.status_code == 429:
            raise RuntimeError("Trello rate limit exceeded (429, ~100 req/10s per key). Retry in a few seconds.")
        raise RuntimeError(f"Trello API error ({res.status_code} {method} {path}): {res.text[:500]}")

    # ---- auth / user ----
    async def get_user(self) -> dict:
        data = await self._request(
            "GET", "/members/me",
            params={"fields": "id,fullName,username,avatarUrl,initials,url"},
        )
        return self._fmt_member(data)

    async def test_connection(self) -> Dict[str, Any]:
        try:
            user = await self.get_user()
            boards = await self.list_boards()
            return {
                "ok": True,
                "message": f"Trello conectado como {user.get('fullName', '')} (@{user.get('username', '')}) · {len(boards)} tablero(s).",
                "details": {"user": user, "boards": len(boards)},
            }
        except Exception as e:
            return {"ok": False, "message": f"Error de conexión con Trello: {e}", "details": {"error": str(e)}}

    # ---- boards ----
    async def list_boards(self, filter: str = "open") -> list:
        data = await self._request(
            "GET", "/members/me/boards",
            params={"filter": filter or "open",
                    "fields": "id,name,url,shortUrl,closed,dateLastActivity,prefs"},
        )
        return [self._fmt_board(b) for b in data or []]

    async def get_board(self, board_id: str = "") -> dict:
        if not board_id:
            raise ValueError("Se requiere 'board_id'. Usa 'trello_list_boards' para descubrirlo.")
        data = await self._request(
            "GET", f"/boards/{board_id}",
            params={"fields": "id,name,desc,url,shortUrl,closed,dateLastActivity,prefs",
                    "lists": "open", "list_fields": "id,name,closed,pos",
                    "members": "true", "member_fields": "id,fullName,username"},
        )
        out = self._fmt_board(data)
        out["lists"] = [
            {"id": l.get("id", ""), "name": l.get("name", ""),
             "closed": l.get("closed"), "pos": l.get("pos")}
            for l in data.get("lists", []) or []
        ]
        out["members"] = [self._fmt_member(m) for m in data.get("members", []) or []]
        return out

    async def create_board(self, name: str = "", desc: str = "") -> dict:
        if not name:
            raise ValueError("Se requiere 'name' para crear el tablero.")
        params: Dict[str, Any] = {"name": name, "defaultLists": "true"}
        if desc:
            params["desc"] = desc
        data = await self._request("POST", "/boards", params=params)
        return self._fmt_board(data)

    # ---- lists ----
    async def list_lists(self, board_id: str = "", filter: str = "open") -> list:
        if not board_id:
            raise ValueError("Se requiere 'board_id'. Usa 'trello_list_boards' para descubrirlo.")
        data = await self._request(
            "GET", f"/boards/{board_id}/lists",
            params={"cards": "none", "filter": filter or "open",
                    "fields": "id,name,closed,pos"},
        )
        return [self._fmt_list(l) for l in data or []]

    async def create_list(self, board_id: str = "", name: str = "", pos: str = "bottom") -> dict:
        if not board_id or not name:
            raise ValueError("Se requieren 'board_id' y 'name'.")
        data = await self._request(
            "POST", "/lists",
            params={"name": name, "idBoard": board_id, "pos": pos or "bottom"},
        )
        return self._fmt_list(data)

    async def update_list(
        self, list_id: str = "", name: Optional[str] = None,
        closed: Optional[bool] = None,
    ) -> dict:
        if not list_id:
            raise ValueError("Se requiere 'list_id'.")
        if name is not None:
            await self._request("PUT", f"/lists/{list_id}/name", params={"value": name})
        if closed is not None:
            await self._request(
                "PUT", f"/lists/{list_id}/closed",
                params={"value": str(bool(closed)).lower()},
            )
        if name is None and closed is None:
            raise ValueError("Nada que actualizar: provee 'name' y/o 'closed'.")
        data = await self._request("GET", f"/lists/{list_id}", params={"fields": "id,name,closed,pos,idBoard"})
        return self._fmt_list(data)

    # ---- cards ----
    async def list_cards(
        self, board_id: str = "", list_id: str = "",
        filter: str = "open",
    ) -> dict:
        if list_id:
            data = await self._request(
                "GET", f"/lists/{list_id}/cards",
                params={"fields": self.CARD_FIELDS},
            )
            cards = data or []
            scope = {"list_id": list_id}
        elif board_id:
            data = await self._request(
                "GET", f"/boards/{board_id}/cards",
                params={"filter": filter or "open", "fields": self.CARD_FIELDS},
            )
            cards = data or []
            scope = {"board_id": board_id}
        else:
            raise ValueError("Provee 'list_id' (tarjetas de una lista) o 'board_id' (todas las del tablero).")
        return {**scope, "count": len(cards), "cards": [self._fmt_card(c) for c in cards]}

    async def get_card(self, card_id: str = "") -> dict:
        if not card_id:
            raise ValueError("Se requiere 'card_id'.")
        data = await self._request(
            "GET", f"/cards/{card_id}",
            params={"fields": self.CARD_FIELDS,
                    "members": "true", "member_fields": "id,fullName,username",
                    "checklists": "all", "checkItems": "all", "checkItemStates": "true",
                    "attachments": "false",
                    "actions": "commentCard", "actions_limit": 20},
        )
        out = self._fmt_card(data, full=True)
        out["members"] = [self._fmt_member(m) for m in data.get("members", []) or []]
        out["checklists"] = [
            {"id": cl.get("id", ""), "name": cl.get("name", ""),
             "items": [{"id": it.get("id", ""), "name": it.get("name", ""),
                        "state": it.get("state", "")} for it in cl.get("checkItems", []) or []]}
            for cl in data.get("checklists", []) or []
        ]
        out["recent_comments"] = [self._fmt_comment(a) for a in data.get("actions", []) or []]
        return out

    async def create_card(
        self, list_id: str = "", name: str = "", desc: str = "",
        due: str = "", pos: str = "bottom",
        member_ids: Optional[List[str]] = None,
    ) -> dict:
        if not list_id or not name:
            raise ValueError("Se requieren 'list_id' y 'name' para crear la tarjeta.")
        params: Dict[str, Any] = {"idList": list_id, "name": name, "pos": pos or "bottom"}
        if desc:
            params["desc"] = desc
        if due:
            params["due"] = due
        if member_ids:
            params["idMembers"] = ",".join(member_ids)
        data = await self._request("POST", "/cards", params=params)
        return self._fmt_card(data, full=True)

    async def update_card(self, card_id: str = "", **fields) -> dict:
        if not card_id:
            raise ValueError("Se requiere 'card_id'.")
        allowed = ("name", "desc", "due", "dueComplete", "closed", "idList", "pos")
        params: Dict[str, Any] = {}
        for k in allowed:
            v = fields.get(k)
            if v is None:
                continue
            if k in ("closed", "dueComplete"):
                params[k] = str(bool(v)).lower()
            else:
                params[k] = v
        member_ids = fields.get("member_ids", fields.get("idMembers"))
        if member_ids is not None:
            params["idMembers"] = ",".join(member_ids) if isinstance(member_ids, list) else member_ids
        if not params:
            raise ValueError(
                "Nada que actualizar: provee al menos un campo "
                "(name, desc, due, dueComplete, closed, idList, pos, member_ids)."
            )
        data = await self._request("PUT", f"/cards/{card_id}", params=params)
        return self._fmt_card(data, full=True)

    async def archive_card(self, card_id: str = "") -> dict:
        if not card_id:
            raise ValueError("Se requiere 'card_id'.")
        await self._request("PUT", f"/cards/{card_id}/closed", params={"value": "true"})
        return {"id": card_id, "status": "archived"}

    # ---- comments ----
    async def list_card_comments(self, card_id: str = "", limit: int = 50) -> list:
        if not card_id:
            raise ValueError("Se requiere 'card_id'.")
        data = await self._request(
            "GET", f"/cards/{card_id}/actions",
            params={"filter": "commentCard", "limit": limit or 50},
        )
        return [self._fmt_comment(a) for a in data or []]

    async def create_card_comment(self, card_id: str = "", text: str = "") -> dict:
        if not card_id or not text:
            raise ValueError("Se requieren 'card_id' y 'text'.")
        data = await self._request(
            "POST", f"/cards/{card_id}/actions/comments", params={"text": text},
        )
        return self._fmt_comment(data)

    # ---- members & search ----
    async def list_board_members(self, board_id: str = "") -> list:
        if not board_id:
            raise ValueError("Se requiere 'board_id'.")
        data = await self._request(
            "GET", f"/boards/{board_id}/members",
            params={"fields": "id,fullName,username,avatarUrl"},
        )
        return [self._fmt_member(m) for m in data or []]

    async def search(
        self, query: str = "", model_types: str = "cards,boards",
        cards_limit: int = 20, boards_limit: int = 10,
    ) -> dict:
        if not query:
            raise ValueError("Se requiere 'query'.")
        data = await self._request(
            "GET", "/search",
            params={"query": query, "modelTypes": model_types or "cards,boards",
                    "cards_limit": cards_limit or 20, "boards_limit": boards_limit or 10,
                    "card_fields": "id,name,url,idBoard,idList",
                    "board_fields": "id,name,url"},
        )
        return {
            "query": query,
            "cards": [{"id": c.get("id", ""), "name": c.get("name", ""), "url": c.get("url", ""),
                       "idBoard": c.get("idBoard", ""), "idList": c.get("idList", "")}
                      for c in (data.get("cards", []) or [])],
            "boards": [{"id": b.get("id", ""), "name": b.get("name", ""), "url": b.get("url", "")}
                       for b in (data.get("boards", []) or [])],
        }

    # ---- formatters (respuestas compactas para no saturar el contexto del LLM) ----
    @staticmethod
    def _fmt_board(b: dict) -> dict:
        prefs = b.get("prefs") or {}
        return {
            "id": str(b.get("id", "")),
            "name": b.get("name", ""),
            "desc": (b.get("desc") or "")[:500],
            "url": b.get("url", ""),
            "shortUrl": b.get("shortUrl", ""),
            "closed": b.get("closed"),
            "dateLastActivity": b.get("dateLastActivity", ""),
            "background": prefs.get("background") if isinstance(prefs, dict) else None,
        }

    @staticmethod
    def _fmt_list(l: dict) -> dict:
        return {
            "id": str(l.get("id", "")),
            "name": l.get("name", ""),
            "closed": l.get("closed"),
            "pos": l.get("pos"),
            "idBoard": str(l.get("idBoard", "") or ""),
        }

    @staticmethod
    def _fmt_card(c: dict, full: bool = False) -> dict:
        labels = []
        for lb in c.get("labels", []) or []:
            if isinstance(lb, dict):
                labels.append({"id": lb.get("id", ""), "name": lb.get("name", ""), "color": lb.get("color", "")})
        out: Dict[str, Any] = {
            "id": str(c.get("id", "")),
            "name": c.get("name", ""),
            "closed": c.get("closed"),
            "due": c.get("due"),
            "dueComplete": c.get("dueComplete"),
            "pos": c.get("pos"),
            "url": c.get("url", ""),
            "shortUrl": c.get("shortUrl", ""),
            "idList": str(c.get("idList", "") or ""),
            "idBoard": str(c.get("idBoard", "") or ""),
            "member_ids": c.get("idMembers", []) or [],
            "labels": labels,
            "dateLastActivity": c.get("dateLastActivity", ""),
        }
        desc = c.get("desc") or ""
        out["desc"] = desc[:2000] if full else desc[:300]
        return out

    @staticmethod
    def _fmt_member(m: dict) -> dict:
        return {
            "id": str(m.get("id", "")),
            "fullName": m.get("fullName", "") or m.get("username", ""),
            "username": m.get("username", ""),
            "avatarUrl": m.get("avatarUrl", ""),
            "url": m.get("url", ""),
        }

    @staticmethod
    def _fmt_comment(a: dict) -> dict:
        data = a.get("data") or {}
        text = (data.get("text") or "") if isinstance(data, dict) else ""
        member = a.get("memberCreator") or {}
        return {
            "id": str(a.get("id", "")),
            "text": text,
            "date": a.get("date", ""),
            "author": member.get("fullName", "") or member.get("username", ""),
            "author_id": str(member.get("id", "") or ""),
        }
