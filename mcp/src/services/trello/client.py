import logging
import re
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

    def _redacted(self, text: str) -> str:
        # Trello error bodies echo the request URL including credentials.
        # Never propagate key/token into logs or tool outputs.
        out = text or ""
        out = re.sub(r"([?&](?:key|token)=)[^&\s]*", r"\1<redacted>", out)
        return out

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
        raise RuntimeError(
            f"Trello API error ({res.status_code} {method} {path}): {self._redacted(res.text[:500])}"
        )

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
                    "members": "all", "member_fields": "id,fullName,username"},
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
                    "attachments": "true", "attachment_fields": "id,name,url,mimeType,date",
                    "actions": "commentCard", "actions_limit": 20},
        )
        out = self._fmt_card(data, full=True)
        out["members"] = [self._fmt_member(m) for m in data.get("members", []) or []]
        out["checklists"] = [self._fmt_checklist(cl) for cl in data.get("checklists", []) or []]
        out["attachments"] = [self._fmt_attachment(a) for a in data.get("attachments", []) or []]
        out["recent_comments"] = [self._fmt_comment(a) for a in data.get("actions", []) or []]
        return out

    async def create_card(
        self, list_id: str = "", name: str = "", desc: str = "",
        due: str = "", pos: str = "bottom",
        member_ids: Optional[List[str]] = None,
        label_ids: Optional[List[str]] = None,
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
        if label_ids:
            params["idLabels"] = ",".join(label_ids)
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
        label_ids = fields.get("label_ids", fields.get("idLabels"))
        if label_ids is not None:
            params["idLabels"] = ",".join(label_ids) if isinstance(label_ids, list) else label_ids
        if not params:
            raise ValueError(
                "Nada que actualizar: provee al menos un campo "
                "(name, desc, due, dueComplete, closed, idList, pos, member_ids, label_ids)."
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

    async def update_card_comment(self, card_id: str = "", comment_id: str = "", text: str = "") -> dict:
        if not card_id or not comment_id or not text:
            raise ValueError("Se requieren 'card_id', 'comment_id' y 'text'.")
        data = await self._request(
            "PUT", f"/cards/{card_id}/actions/{comment_id}/comments", params={"text": text},
        )
        return self._fmt_comment(data)

    async def delete_card_comment(self, card_id: str = "", comment_id: str = "") -> dict:
        if not card_id or not comment_id:
            raise ValueError("Se requieren 'card_id' y 'comment_id'.")
        await self._request("DELETE", f"/cards/{card_id}/actions/{comment_id}/comments")
        return {"id": comment_id, "status": "deleted"}

    async def delete_attachment(self, card_id: str = "", attachment_id: str = "") -> dict:
        if not card_id or not attachment_id:
            raise ValueError("Se requieren 'card_id' y 'attachment_id'.")
        await self._request("DELETE", f"/cards/{card_id}/attachments/{attachment_id}")
        return {"id": attachment_id, "status": "deleted"}

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
        include_closed: bool = True,
    ) -> dict:
        if not query:
            raise ValueError("Se requiere 'query'.")
        data = await self._request(
            "GET", "/search",
            params={"query": query, "modelTypes": model_types or "cards,boards",
                    "cards_limit": cards_limit or 20, "boards_limit": boards_limit or 10,
                    "card_fields": "id,name,url,closed,idBoard,idList",
                    "board_fields": "id,name,url"},
        )
        cards = [{"id": c.get("id", ""), "name": c.get("name", ""), "url": c.get("url", ""),
                  "closed": c.get("closed"), "idBoard": c.get("idBoard", ""),
                  "idList": c.get("idList", "")}
                 for c in (data.get("cards", []) or [])]
        if not include_closed:
            cards = [c for c in cards if not c.get("closed")]
        return {
            "query": query,
            "cards": cards,
            "boards": [{"id": b.get("id", ""), "name": b.get("name", ""), "url": b.get("url", "")}
                       for b in (data.get("boards", []) or [])],
        }

    # ---- delete (permanent; lists can only be archived, there is no list delete endpoint) ----
    async def delete_card(self, card_id: str = "") -> dict:
        if not card_id:
            raise ValueError("Se requiere 'card_id'.")
        await self._request("DELETE", f"/cards/{card_id}")
        return {"id": card_id, "status": "deleted"}

    async def delete_board(self, board_id: str = "") -> dict:
        if not board_id:
            raise ValueError("Se requiere 'board_id'.")
        await self._request("DELETE", f"/boards/{board_id}")
        return {"id": board_id, "status": "deleted"}

    async def archive_list(self, list_id: str = "") -> dict:
        """Archive a list AND all its cards (archiving a list alone leaves cards active).

        NOTE: POST archiveAllCards does not return a usable count, so the
        archived total is measured directly: open cards before vs after.
        """
        if not list_id:
            raise ValueError("Se requiere 'list_id'.")
        before = await self._request(
            "GET", f"/lists/{list_id}/cards", params={"fields": "id,closed"},
        )
        open_before = [c for c in before or [] if not c.get("closed")]
        await self._request("POST", f"/lists/{list_id}/archiveAllCards")
        await self._request("PUT", f"/lists/{list_id}/closed", params={"value": "true"})
        after = await self._request(
            "GET", f"/lists/{list_id}/cards", params={"fields": "id,closed"},
        )
        open_after = [c for c in after or [] if not c.get("closed")]
        data = await self._request("GET", f"/lists/{list_id}", params={"fields": "id,name,closed,pos,idBoard"})
        out = self._fmt_list(data)
        out["cards_archived"] = len(open_before) - len(open_after)
        out["cards_archived_verified"] = len(open_after) == 0
        return out

    # ---- labels ----
    LABEL_COLORS = ("green", "yellow", "orange", "red", "purple",
                    "blue", "sky", "lime", "pink", "black")

    async def list_labels(self, board_id: str = "") -> list:
        if not board_id:
            raise ValueError("Se requiere 'board_id'.")
        data = await self._request(
            "GET", f"/boards/{board_id}/labels", params={"fields": "all", "limit": 1000},
        )
        return [self._fmt_label(l) for l in data or []]

    async def create_label(self, board_id: str = "", name: str = "", color: str = "") -> dict:
        if not board_id or not name or not color:
            raise ValueError("Se requieren 'board_id', 'name' y 'color'.")
        if color not in self.LABEL_COLORS:
            raise ValueError(f"Color inválido '{color}'. Válidos: {', '.join(self.LABEL_COLORS)}.")
        data = await self._request(
            "POST", f"/boards/{board_id}/labels", params={"name": name, "color": color},
        )
        return self._fmt_label(data)

    async def update_label(
        self, label_id: str = "", name: Optional[str] = None, color: Optional[str] = None,
    ) -> dict:
        if not label_id:
            raise ValueError("Se requiere 'label_id'.")
        params: Dict[str, Any] = {}
        if name is not None:
            params["name"] = name
        if color is not None:
            if color not in self.LABEL_COLORS:
                raise ValueError(f"Color inválido '{color}'. Válidos: {', '.join(self.LABEL_COLORS)}.")
            params["color"] = color
        if not params:
            raise ValueError("Nada que actualizar: provee 'name' y/o 'color'.")
        data = await self._request("PUT", f"/labels/{label_id}", params=params)
        return self._fmt_label(data)

    async def delete_label(self, label_id: str = "") -> dict:
        if not label_id:
            raise ValueError("Se requiere 'label_id'.")
        await self._request("DELETE", f"/labels/{label_id}")
        return {"id": label_id, "status": "deleted"}

    # ---- checklists (read already included in get_card) ----
    async def create_checklist(self, card_id: str = "", name: str = "", pos: str = "bottom") -> dict:
        if not card_id or not name:
            raise ValueError("Se requieren 'card_id' y 'name'.")
        data = await self._request(
            "POST", "/checklists",
            params={"idCard": card_id, "name": name, "pos": pos or "bottom"},
        )
        return self._fmt_checklist(data)

    async def create_checkitem(
        self, checklist_id: str = "", name: str = "", pos: str = "bottom",
    ) -> dict:
        if not checklist_id or not name:
            raise ValueError("Se requieren 'checklist_id' y 'name'.")
        data = await self._request(
            "POST", f"/checklists/{checklist_id}/checkItems",
            params={"name": name, "pos": pos or "bottom"},
        )
        return {"id": str(data.get("id", "")), "name": data.get("name", ""),
                "state": "incomplete", "pos": data.get("pos")}

    async def update_checkitem(
        self, card_id: str = "", checklist_id: str = "", checkitem_id: str = "",
        state: Optional[str] = None, name: Optional[str] = None,
    ) -> dict:
        if not card_id or not checklist_id or not checkitem_id:
            raise ValueError("Se requieren 'card_id', 'checklist_id' y 'checkitem_id'.")
        params: Dict[str, Any] = {}
        if state is not None:
            if state not in ("complete", "incomplete"):
                raise ValueError("state debe ser 'complete' o 'incomplete'.")
            params["state"] = state
        if name is not None:
            params["name"] = name
        if not params:
            raise ValueError("Nada que actualizar: provee 'state' y/o 'name'.")
        # NOTE: singular 'checklist'/'checkItem' — plural variants 404.
        data = await self._request(
            "PUT", f"/cards/{card_id}/checklist/{checklist_id}/checkItem/{checkitem_id}",
            params=params,
        )
        return {"id": checkitem_id, "name": data.get("name", name or ""),
                "state": data.get("state", state or ""), "pos": data.get("pos")}

    async def delete_checklist(self, checklist_id: str = "") -> dict:
        if not checklist_id:
            raise ValueError("Se requiere 'checklist_id'.")
        await self._request("DELETE", f"/checklists/{checklist_id}")
        return {"id": checklist_id, "status": "deleted"}

    # ---- attachments (list included in get_card; attach by URL, no binary upload) ----
    async def add_attachment_url(self, card_id: str = "", url: str = "", name: str = "") -> dict:
        if not card_id or not url:
            raise ValueError("Se requieren 'card_id' y 'url'.")
        params: Dict[str, Any] = {"url": url}
        if name:
            params["name"] = name
        data = await self._request("POST", f"/cards/{card_id}/attachments", params=params)
        return self._fmt_attachment(data)

    # ---- custom fields ----
    async def list_custom_fields(self, board_id: str = "") -> list:
        if not board_id:
            raise ValueError("Se requiere 'board_id'.")
        data = await self._request("GET", f"/boards/{board_id}/customFields")
        return [self._fmt_custom_field(f) for f in data or []]

    async def set_custom_field(
        self, card_id: str = "", field_id: str = "",
        field_type: str = "text", value: str = "",
    ) -> dict:
        if not card_id or not field_id:
            raise ValueError("Se requieren 'card_id' y 'field_id'.")
        t = (field_type or "text").lower()
        if t == "text":
            payload = {"value": {"text": value}}
        elif t == "number":
            try:
                payload = {"value": {"number": float(value)}}
            except (TypeError, ValueError):
                raise ValueError(f"value '{value}' no es un número válido.")
        elif t == "checkbox":
            payload = {"value": {"checked": str(value).lower() in ("true", "1", "yes", "checked")}}
        elif t == "date":
            payload = {"value": {"date": value}}
        elif t == "list":
            payload = {"idValue": value}
        else:
            raise ValueError("field_type debe ser text, number, checkbox, date o list (value=option id).")
        await self._request(
            "PUT", f"/cards/{card_id}/customField/{field_id}/item", json_body=payload,
        )
        return {"card_id": card_id, "field_id": field_id, "status": "updated"}

    # ---- formatters (respuestas compactas para no saturar el contexto del LLM) ----
    @staticmethod
    def _fmt_label(l: dict) -> dict:
        return {"id": str(l.get("id", "")), "name": l.get("name", ""),
                "color": l.get("color", "")}

    @staticmethod
    def _fmt_checklist(cl: dict) -> dict:
        return {
            "id": str(cl.get("id", "")),
            "name": cl.get("name", ""),
            "idCard": str(cl.get("idCard", "") or ""),
            "items": [{"id": str(it.get("id", "")), "name": it.get("name", ""),
                       "state": it.get("state", ""), "pos": it.get("pos")}
                      for it in cl.get("checkItems", []) or []],
        }

    @staticmethod
    def _fmt_attachment(a: dict) -> dict:
        return {"id": str(a.get("id", "")), "name": a.get("name", ""),
                "url": a.get("url", ""), "mimeType": a.get("mimeType", ""),
                "date": a.get("date", "")}

    @staticmethod
    def _fmt_custom_field(f: dict) -> dict:
        display = f.get("display") or {}
        return {"id": str(f.get("id", "")), "name": display.get("name", ""),
                "type": f.get("type", ""),
                "options": [{"id": str(o.get("id", "")), "value": (o.get("value") or {}).get("text", ""),
                             "color": o.get("color", "")}
                            for o in display.get("options", []) or []]}

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
