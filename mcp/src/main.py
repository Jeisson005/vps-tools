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
        "api_key": MCP_API_KEY or "mcp_sec_4d692f955b2f868126e6e5f5d026e22ab930",
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
