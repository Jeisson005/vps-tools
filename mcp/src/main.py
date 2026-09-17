import os
import json
import uuid
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, Response, HTTPException, Depends, Header, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .core.db import init_db, get_recent_activity, log_activity
from .core.registry import registry
from .core.mcp_protocol import McpProtocolHandler
from .services import AVAILABLE_SERVICES
from .services.passbolt.client import PassboltClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mcp.main")

ADMIN_PASSWORD = os.environ.get("MCP_ADMIN_PASSWORD", "admin")
MCP_API_KEY = os.environ.get("MCP_API_KEY", "").strip()


def _generate_instance_id(user_email: str = "") -> str:
    """Build a stable, human-friendly account id from an email or fall back to a short uuid."""
    local = (user_email or "").split("@")[0].strip()
    if local:
        safe = "".join(c for c in local if c.isalnum() or c in "_-").lower()
        if safe:
            return safe
    return "account-" + uuid.uuid4().hex[:8]


def _instance_status(it: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitized account summary for the Admin Panel (never includes secrets)."""
    config = it.get("config", {}) or {}
    secrets = it.get("secrets", {}) or {}
    has_secrets = any(str(v) for v in secrets.values() if v)
    return {
        "instance_id": it.get("instance_id"),
        "name": it.get("name") or "",
        "enabled": bool(it.get("enabled")),
        "is_default": bool(it.get("is_default")),
        "configured": bool(has_secrets),
        "base_url": config.get("base_url", ""),
        "user_email": config.get("user_email", "") or config.get("email", ""),
        "fingerprint": config.get("fingerprint", "") or secrets.get("fingerprint", ""),
        "has_private_key": bool(secrets.get("private_key")),
        "has_passphrase": bool(secrets.get("passphrase") or secrets.get("client_secret") or secrets.get("access_token")),
        "has_secrets": has_secrets,
    }

# Active SSE sessions: session_id -> asyncio.Queue
_active_sse_queues: Dict[str, asyncio.Queue] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing MCP Gateway database and services...")
    init_db()
    registry.initialize()
    logger.info("MCP Gateway ready.")
    yield
    logger.info("Shutting down MCP Gateway.")

app = FastAPI(title="VPS MCP Gateway", lifespan=lifespan)

# Allow CORS for Web UI and client connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for Admin Web UI
web_dir = os.path.join(os.path.dirname(__file__), "web")
if os.path.exists(web_dir):
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

# --- Security & Auth Helpers ---

def verify_admin_token() -> bool:
    """Admin endpoints are protected at reverse proxy level via Nginx HTTP Basic Auth."""
    return True

def verify_client_mcp_auth(request: Request):
    """Verify API Key for LLM clients accessing MCP endpoints."""
    if not MCP_API_KEY:
        return True  # Open if no API key configured

    # 1. Check Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split(" ")
        key = parts[1] if len(parts) == 2 else parts[0]
        if key == MCP_API_KEY:
            return True

    # 2. Check X-API-Key header
    if request.headers.get("X-API-Key") == MCP_API_KEY:
        return True

    # 3. Check query param ?api_key=...
    if request.query_params.get("api_key") == MCP_API_KEY:
        return True

    raise HTTPException(status_code=401, detail="Unauthorized: Invalid MCP API Key")

# --- Admin Web UI Routes ---

@app.get("/", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
async def serve_admin_dashboard():
    index_path = os.path.join(web_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse("<h1>MCP Gateway</h1><p>Web UI files not found.</p>", status_code=404)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "mcp-gateway",
        "services": registry.list_services_status()
    }

# --- Admin API Routes ---

class LoginPayload(BaseModel):
    password: str

@app.post("/api/admin/login")
async def admin_login(payload: LoginPayload):
    if payload.password == ADMIN_PASSWORD:
        return {"ok": True, "token": ADMIN_PASSWORD}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")

@app.get("/api/admin/services")
async def get_admin_services(auth: bool = Depends(verify_admin_token)):
    return registry.list_services_status()

class ToggleServicePayload(BaseModel):
    enabled: bool

@app.post("/api/admin/services/{service_id}/toggle")
async def toggle_service(service_id: str, payload: ToggleServicePayload, auth: bool = Depends(verify_admin_token)):
    service = registry.get_service(service_id)
    if not service:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    
    registry.update_service(service_id, enabled=payload.enabled, config=service.config, secrets=service.secrets)
    return {"ok": True, "enabled": payload.enabled}

class SaveServicePayload(BaseModel):
    enabled: bool = True
    config: Dict[str, Any] = {}
    secrets: Dict[str, str] = {}

@app.post("/api/admin/services/{service_id}")
async def save_service(service_id: str, payload: SaveServicePayload, auth: bool = Depends(verify_admin_token)):
    registry.update_service(
        service_id=service_id,
        enabled=payload.enabled,
        config=payload.config,
        secrets=payload.secrets
    )
    return {"ok": True, "message": f"Service '{service_id}' updated"}

@app.post("/api/admin/services/{service_id}/test")
async def test_existing_service(service_id: str, auth: bool = Depends(verify_admin_token)):
    service = registry.get_service(service_id)
    if not service:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    res = await service.test_connection()
    return res

class TestConfigPayload(BaseModel):
    config: Dict[str, Any] = {}
    secrets: Dict[str, str] = {}

@app.post("/api/admin/services/{service_id}/test-config")
async def test_service_draft_config(service_id: str, payload: TestConfigPayload, auth: bool = Depends(verify_admin_token)):
    service = registry.get_service(service_id)
    cfg = payload.config or (service.config if service else {})
    sec = payload.secrets or {}
    
    if service:
        for k, v in service.secrets.items():
            if k not in sec or not sec[k]:
                sec[k] = v

    if service_id == "passbolt":
        test_client = PassboltClient(
            base_url=cfg.get("base_url", ""),
            private_key_armored=sec.get("private_key", ""),
            passphrase=sec.get("passphrase", ""),
            user_email=cfg.get("user_email", ""),
            fingerprint=cfg.get("fingerprint", "")
        )
        return await test_client.test_connection()

    if service_id == "notebooklm":
        from .services.notebooklm.client import NotebookLMClient
        # Draft test uses an isolated throwaway profile so it never clobbers
        # a real account's stored storage_state.json.
        draft = NotebookLMClient(
            auth_json=sec.get("auth_json", "") or sec.get("storage_state", ""),
            email=cfg.get("email", "") or cfg.get("user_email", ""),
            language=cfg.get("language", "") or cfg.get("hl", ""),
            profile="__draft__",
        )
        return await draft.test_connection()

    # Generic: for any instance-capable service, build a temp client from the
    # draft config/secrets and run its connection test.
    service = registry.get_service(service_id)
    builder = getattr(type(service), "_build_client", None) if service else None
    if builder:
        try:
            client = builder(cfg, sec)
            return await client.test_connection()
        except Exception as e:
            return {"ok": False, "message": str(e), "details": {"error": str(e)}}

    return {"ok": False, "message": f"Tester not implemented for {service_id}"}

# --- Generic per-service multi-account admin API -------------------------------

class ServiceAccountPayload(BaseModel):
    instance_id: Optional[str] = None
    name: Optional[str] = ""
    enabled: bool = True
    is_default: bool = False
    config: Dict[str, Any] = {}
    secrets: Dict[str, str] = {}

@app.get("/api/admin/services/{service_id}/accounts")
async def list_service_accounts(service_id: str, auth: bool = Depends(verify_admin_token)):
    service = registry.get_service(service_id)
    summary = service.get_account_summary() if service and hasattr(service, "get_account_summary") else None
    if summary:
        # Pair the live service state with the persisted label/id/default flags.
        by_id = {a["instance_id"]: a for a in summary}
        out = []
        for it in registry.get_instances(service_id):
            row = dict(_instance_status(it))
            live = by_id.get(it["instance_id"], {})
            row["configured"] = live.get("configured", row["configured"])
            if live.get("base_url"):
                row["base_url"] = live["base_url"]
            if live.get("user_email"):
                row["user_email"] = live["user_email"]
            out.append(row)
        return out
    instances = registry.get_instances(service_id)
    return [_instance_status(it) for it in instances]

@app.post("/api/admin/services/{service_id}/accounts")
async def save_service_account(service_id: str, payload: ServiceAccountPayload, auth: bool = Depends(verify_admin_token)):
    instance_id = (payload.instance_id or "").strip() or _generate_instance_id(
        payload.name or payload.config.get("user_email", "") or payload.config.get("email", "")
    )
    name = (payload.name or "").strip()

    existing_accounts = registry.get_instances(service_id)
    existing_account = next((a for a in existing_accounts if a["instance_id"] == instance_id), None)

    # Merge: keep existing config/secrets and only overwrite with non-empty values,
    # so editing just a label never wipes stored credentials.
    merged_config = dict(existing_account["config"]) if existing_account else {}
    merged_secrets = dict(existing_account["secrets"]) if existing_account else {}
    if payload.config:
        merged_config.update({k: v for k, v in payload.config.items() if v is not None and str(v).strip()})
    if payload.secrets:
        merged_secrets.update({k: v for k, v in payload.secrets.items() if v is not None and str(v).strip()})

    wants_default = payload.is_default or not existing_accounts or not any(e["is_default"] for e in existing_accounts)

    registry.save_instance(
        service_id, instance_id, payload.enabled, merged_config, merged_secrets,
        is_default=wants_default, name=name or existing_account.get("name", "") if existing_account else name,
    )
    return {"ok": True, "message": f"Cuenta '{instance_id}' guardada", "instance_id": instance_id}

@app.delete("/api/admin/services/{service_id}/accounts/{instance_id}")
async def delete_service_account(service_id: str, instance_id: str, auth: bool = Depends(verify_admin_token)):
    registry.delete_instance(service_id, instance_id)

    # Guarantee at least one default account remains.
    remaining = registry.get_instances(service_id)
    if remaining and not any(e["is_default"] for e in remaining):
        first = remaining[0]
        registry.save_instance(
            service_id, first["instance_id"], first["enabled"],
            first["config"], first["secrets"], is_default=True, name=first.get("name", ""),
        )
    return {"ok": True, "message": f"Cuenta '{instance_id}' eliminada"}

@app.post("/api/admin/services/{service_id}/accounts/{instance_id}/test")
async def test_service_account(service_id: str, instance_id: str, auth: bool = Depends(verify_admin_token)):
    service = registry.get_service(service_id)
    if not service or not hasattr(service, "test_account"):
        raise HTTPException(status_code=404, detail=f"Servicio '{service_id}' no disponible")
    try:
        return await service.test_account(instance_id)
    except Exception as e:
        return {"ok": False, "message": str(e), "details": {}}

@app.get("/api/admin/services/{service_id}/accounts/{instance_id}/qr")
async def get_service_account_qr(service_id: str, instance_id: str, auth: bool = Depends(verify_admin_token)):
    """Return a rendered QR (image data-URI) for pairing a WhatsApp account."""
    service = registry.get_service(service_id)
    if not service or not hasattr(service, "get_account_qr"):
        raise HTTPException(status_code=404, detail=f"Servicio '{service_id}' no soporta QR")
    try:
        return await service.get_account_qr(instance_id)
    except Exception as e:
        return {"account": instance_id, "qr": "", "image": "", "message": str(e)}

@app.get("/api/admin/services/{service_id}/account-schema")
async def get_service_account_schema(service_id: str, auth: bool = Depends(verify_admin_token)):
    service = registry.get_service(service_id)
    if not service or not hasattr(service, "get_account_schema"):
        return {"config": [], "secrets": []}
    return service.get_account_schema()

# --- Google OAuth web flow (100% panel, sin localhost manual) ------------------
# Estados pendientes: state -> {instance_id, redirect_uri, created}
_GOOGLE_OAUTH_STATES: Dict[str, Dict[str, Any]] = {}


def _google_public_base() -> str:
    base = (os.environ.get("MCP_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if base:
        return base
    domain = (os.environ.get("MCP_DOMAIN") or "").strip()
    if domain:
        return f"https://{domain}"
    return "https://mcp.jeisson.top"


def _google_callback_url() -> str:
    return _google_public_base() + "/api/admin/services/google/oauth/callback"


def _google_full_scopes() -> str:
    from .services.google.client import GOOGLE_SCOPES
    return GOOGLE_SCOPES


async def _google_exchange_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> Dict[str, Any]:
    import httpx
    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if res.status_code != 200:
            raise RuntimeError(f"Google token exchange failed ({res.status_code}): {res.text[:300]}")
        return res.json()


def _google_save_refresh(instance_id: str, refresh_token: str, scope: str) -> Dict[str, Any]:
    instances = registry.get_instances("google")
    target = next((i for i in instances if i["instance_id"] == instance_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Cuenta Google '{instance_id}' no existe. Guárdala primero en el panel.")
    merged_secrets = dict(target["secrets"])
    merged_secrets["refresh_token"] = refresh_token
    merged_secrets["scope"] = scope or _google_full_scopes()
    registry.save_instance(
        "google", instance_id, target["enabled"], target["config"], merged_secrets,
        is_default=target.get("is_default", True), name=target.get("name", ""),
    )
    log_activity("google", "oauth_connect", "success", f"Cuenta '{instance_id}' conectada vía web")
    return {"ok": True, "message": f"Cuenta '{instance_id}' conectada con Google.", "instance_id": instance_id}


@app.get("/api/admin/services/google/oauth/info")
async def google_oauth_info(auth: bool = Depends(verify_admin_token)):
    return {
        "callback_url": _google_callback_url(),
        "scopes": _google_full_scopes(),
        "instructions": (
            "1) Guarda la cuenta con email + client_id + client_secret. "
            "2) Si usas cliente Web, registra esta callback URL como URI de redirección autorizada. "
            "3) Pulsa «Conectar con Google»."
        ),
    }


@app.get("/api/admin/services/google/oauth/start")
async def google_oauth_start(instance_id: str = Query(...), auth: bool = Depends(verify_admin_token)):
    import urllib.parse
    instances = registry.get_instances("google")
    target = next((i for i in instances if i["instance_id"] == instance_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Cuenta Google '{instance_id}' no existe. Guárdala primero.")
    secrets = target["secrets"] or {}
    client_id = (secrets.get("client_id") or "").strip()
    client_secret = (secrets.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="La cuenta no tiene client_id/client_secret guardados.")
    redirect_uri = _google_callback_url()
    state = "g-" + uuid.uuid4().hex[:16]
    _GOOGLE_OAUTH_STATES[state] = {"instance_id": instance_id, "redirect_uri": redirect_uri,
                                   "created": asyncio.get_event_loop().time()}
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": _google_full_scopes(),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return {"auth_url": auth_url, "redirect_uri": redirect_uri, "state": state}


@app.get("/api/admin/services/google/oauth/callback", response_class=HTMLResponse)
async def google_oauth_callback(code: Optional[str] = Query(None), state: Optional[str] = Query(None),
                                error: Optional[str] = Query(None)):
    def _page(ok: bool, title: str, msg: str) -> str:
        color = "#22c55e" if ok else "#ef4444"
        icon = "✓" if ok else "✗"
        return (
            "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Google OAuth</title></head>"
            f"<body style='font-family:system-ui;background:#0f172a;color:#e2e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0'>"
            f"<div style='max-width:480px;background:#1e293b;padding:32px;border-radius:16px;text-align:center'>"
            f"<div style='font-size:48px;color:{color}'>{icon}</div>"
            f"<h2>{title}</h2><p style='color:#94a3b8'>{msg}</p>"
            "<p style='color:#64748b;font-size:13px'>Puedes cerrar esta pestaña y pulsar «Probar» en el panel.</p>"
            "</div></body></html>"
        )
    if error:
        return HTMLResponse(_page(False, "Autorización cancelada", f"Google devolvió: {error}"), status_code=400)
    if not code or not state:
        return HTMLResponse(_page(False, "Faltan parámetros", "No se recibió code/state de Google."), status_code=400)
    pending = _GOOGLE_OAUTH_STATES.pop(state, None)
    if not pending:
        return HTMLResponse(_page(False, "Sesión caducada", "Repite «Conectar con Google» desde el panel."), status_code=400)
    try:
        instances = registry.get_instances("google")
        target = next((i for i in instances if i["instance_id"] == pending["instance_id"]), None)
        if not target:
            raise RuntimeError("La cuenta ya no existe.")
        secrets = target["secrets"] or {}
        tokens = await _google_exchange_code(
            (secrets.get("client_id") or "").strip(), (secrets.get("client_secret") or "").strip(),
            code, pending["redirect_uri"],
        )
        refresh = tokens.get("refresh_token", "")
        if not refresh:
            raise RuntimeError("Google no devolvió refresh_token (reintenta aceptando el consentimiento).")
        _google_save_refresh(pending["instance_id"], refresh, tokens.get("scope", ""))
        return HTMLResponse(_page(True, "Google conectado", f"Cuenta '{pending['instance_id']}' vinculada. Gmail, Calendar y Drive activos."))
    except Exception as e:
        logger.error(f"google oauth callback failed: {e}")
        return HTMLResponse(_page(False, "Error conectando", str(e)[:300]), status_code=400)


class GoogleOAuthExchangePayload(BaseModel):
    instance_id: str
    code: str
    redirect_uri: str = "http://127.0.0.1:8080/"


@app.post("/api/admin/services/google/oauth/exchange")
async def google_oauth_exchange(payload: GoogleOAuthExchangePayload, auth: bool = Depends(verify_admin_token)):
    """Canje manual para clientes OAuth tipo Escritorio (redirect localhost): pega el code en el panel."""
    code = (payload.code or "").strip()
    if "code=" in code and "://" in code:
        # Acepta pegar la URL completa de localhost (?code=...)
        import urllib.parse as _up
        try:
            code = _up.parse_qs(_up.urlparse(code).query).get("code", [code])[0]
        except Exception:
            pass
    if not code:
        raise HTTPException(status_code=400, detail="Falta el código de autorización.")
    instances = registry.get_instances("google")
    target = next((i for i in instances if i["instance_id"] == payload.instance_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Cuenta Google '{payload.instance_id}' no existe.")
    secrets = target["secrets"] or {}
    try:
        tokens = await _google_exchange_code(
            (secrets.get("client_id") or "").strip(), (secrets.get("client_secret") or "").strip(),
            code, (payload.redirect_uri or "").strip() or "http://127.0.0.1:8080/",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:300])
    refresh = tokens.get("refresh_token", "")
    if not refresh:
        raise HTTPException(status_code=400, detail="Google no devolvió refresh_token.")
    return _google_save_refresh(payload.instance_id, refresh, tokens.get("scope", ""))

# Backward-compatible Passbolt aliases -----------------------------------------
@app.get("/api/admin/passbolt/accounts")
async def list_passbolt_accounts(auth: bool = Depends(verify_admin_token)):
    return await list_service_accounts("passbolt", auth)

@app.post("/api/admin/passbolt/accounts")
async def save_passbolt_account(payload: ServiceAccountPayload, auth: bool = Depends(verify_admin_token)):
    return await save_service_account("passbolt", payload, auth)

@app.delete("/api/admin/passbolt/accounts/{instance_id}")
async def delete_passbolt_account(instance_id: str, auth: bool = Depends(verify_admin_token)):
    return await delete_service_account("passbolt", instance_id, auth)

@app.post("/api/admin/passbolt/accounts/{instance_id}/test")
async def test_passbolt_account(instance_id: str, auth: bool = Depends(verify_admin_token)):
    return await test_service_account("passbolt", instance_id, auth)

@app.get("/api/admin/tools")
async def get_admin_tools(scope: str = Query("unified"), auth: bool = Depends(verify_admin_token)):
    tools = registry.get_tools_for_scope(scope)
    return tools

class TesterCallPayload(BaseModel):
    scope: str = "unified"
    tool: str
    arguments: Dict[str, Any] = {}

@app.post("/api/admin/tools/execute")
@app.post("/api/admin/tester/call")
async def admin_tester_call(payload: TesterCallPayload, auth: bool = Depends(verify_admin_token)):
    handler = McpProtocolHandler(scope=payload.scope)
    rpc_payload = {
        "jsonrpc": "2.0",
        "id": "tester-" + str(uuid.uuid4())[:8],
        "method": "tools/call",
        "params": {
            "name": payload.tool,
            "arguments": payload.arguments
        }
    }
    response, _ = await handler.handle_request(rpc_payload)
    return response

@app.get("/api/admin/gateway-info")
async def get_gateway_info(auth: bool = Depends(verify_admin_token)):
    return {
        "api_key": MCP_API_KEY or "",
        "unified_endpoint": "/unified",
        "services": registry.list_services_status()
    }

@app.get("/api/admin/logs")
async def get_admin_logs(auth: bool = Depends(verify_admin_token)):
    return get_recent_activity(limit=100)

# --- MCP JSON-RPC Protocol Endpoints (Streamable-HTTP & SSE) ---

async def _process_mcp_http_post(scope: str, request: Request):
    """Handles Streamable-HTTP POST request."""
    verify_client_mcp_auth(request)
    session_id = request.headers.get("Mcp-Session-Id") or request.query_params.get("sessionId")
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON-RPC payload")

    handler = McpProtocolHandler(scope=scope)
    response_data, effective_sid = await handler.handle_request(body, session_id=session_id)

    headers = {
        "Mcp-Session-Id": effective_sid,
        "Content-Type": "application/json"
    }

    if response_data is None:
        return Response(status_code=204, headers=headers)
        
    return JSONResponse(content=response_data, headers=headers)

async def _sse_stream_generator(scope: str, session_id: str, request: Request):
    """Event stream generator for MCP SSE transport."""
    q: asyncio.Queue = asyncio.Queue()
    _active_sse_queues[session_id] = q

    # Send endpoint event immediately
    endpoint_url = f"/{scope}/message?sessionId={session_id}"
    yield f"event: endpoint\ndata: {endpoint_url}\n\n"

    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                # Wait for outgoing message with timeout to send keep-alive comment
                msg = await asyncio.wait_for(q.get(), timeout=15.0)
                yield f"event: message\ndata: {json.dumps(msg)}\n\n"
            except asyncio.TimeoutError:
                # SSE keep-alive ping
                yield ": ping\n\n"
    finally:
        _active_sse_queues.pop(session_id, None)

# Subroutes: one isolated MCP endpoint per registered service
def _register_service_routes(service_id: str):
    @app.post(f"/{service_id}")
    @app.post(f"/{service_id}/mcp")
    async def service_http_post(request: Request, _service_id: str = service_id):
        return await _process_mcp_http_post(scope=_service_id, request=request)

    @app.get(f"/{service_id}")
    @app.get(f"/{service_id}/sse")
    async def service_sse_get(request: Request, _service_id: str = service_id):
        verify_client_mcp_auth(request)
        session_id = request.headers.get("Mcp-Session-Id") or request.query_params.get("sessionId") or str(uuid.uuid4())
        return StreamingResponse(
            _sse_stream_generator(scope=_service_id, session_id=session_id, request=request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Mcp-Session-Id": session_id,
            }
        )

    @app.delete(f"/{service_id}")
    @app.delete(f"/{service_id}/mcp")
    async def service_http_delete(request: Request, _service_id: str = service_id):
        verify_client_mcp_auth(request)
        session_id = request.headers.get("Mcp-Session-Id") or request.query_params.get("sessionId")
        if session_id and session_id in _active_sse_queues:
            _active_sse_queues.pop(session_id, None)
        return Response(status_code=204)

    @app.post(f"/{service_id}/message")
    @app.post(f"/{service_id}/sse")
    async def service_sse_message(request: Request, sessionId: Optional[str] = Query(None), _service_id: str = service_id):
        verify_client_mcp_auth(request)
        session_id = sessionId or request.headers.get("Mcp-Session-Id") or "default-session"

        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON-RPC payload")

        handler = McpProtocolHandler(scope=_service_id)
        response_data, effective_sid = await handler.handle_request(body, session_id=session_id)

        # If an SSE stream is active for this session, push event to the stream
        q = _active_sse_queues.get(effective_sid)
        if q and response_data:
            await q.put(response_data)
            return Response(status_code=202, headers={"Mcp-Session-Id": effective_sid})

        if response_data is None:
            return Response(status_code=204, headers={"Mcp-Session-Id": effective_sid})

        return JSONResponse(content=response_data, headers={"Mcp-Session-Id": effective_sid})


for _sid in AVAILABLE_SERVICES.keys():
    _register_service_routes(_sid)

# Subroute: Unified aggregator endpoint (/unified, /mcp, /sse)
@app.post("/unified")
@app.post("/mcp")
async def unified_http_post(request: Request):
    return await _process_mcp_http_post(scope="unified", request=request)

@app.get("/unified")
@app.get("/unified/sse")
@app.get("/sse")
async def unified_sse_get(request: Request):
    verify_client_mcp_auth(request)
    session_id = request.headers.get("Mcp-Session-Id") or request.query_params.get("sessionId") or str(uuid.uuid4())
    return StreamingResponse(
        _sse_stream_generator(scope="unified", session_id=session_id, request=request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Mcp-Session-Id": session_id
        }
    )

@app.delete("/unified")
@app.delete("/mcp")
async def unified_http_delete(request: Request):
    verify_client_mcp_auth(request)
    session_id = request.headers.get("Mcp-Session-Id") or request.query_params.get("sessionId")
    if session_id and session_id in _active_sse_queues:
        _active_sse_queues.pop(session_id, None)
    return Response(status_code=204)

@app.post("/unified/message")
@app.post("/unified/sse")
async def unified_sse_message(request: Request, sessionId: Optional[str] = Query(None)):
    verify_client_mcp_auth(request)
    session_id = sessionId or request.headers.get("Mcp-Session-Id") or "default-session"
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON-RPC payload")

    handler = McpProtocolHandler(scope="unified")
    response_data, effective_sid = await handler.handle_request(body, session_id=session_id)

    q = _active_sse_queues.get(effective_sid)
    if q and response_data:
        await q.put(response_data)
        return Response(status_code=202, headers={"Mcp-Session-Id": effective_sid})

    if response_data is None:
        return Response(status_code=204, headers={"Mcp-Session-Id": effective_sid})

    return JSONResponse(content=response_data, headers={"Mcp-Session-Id": effective_sid})
