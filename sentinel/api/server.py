"""
Sentinel Internal MCP & REST API Server
Exposes Model Context Protocol (MCP) tools and REST management endpoints on port 8006.
Supports full MCP SSE Session Queues & Streamable HTTP transport.
"""
import os
import sys
import json
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse

# Add parent directory to sys.path to import core modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings, TASKS_DIR, LOGS_DIR
from core.git_manager import GitManager
from core.cron_manager import CronManager
from core.runner import TaskRunner
from core.healer import Healer
from core.telegram_hub import TelegramHub

logger = logging.getLogger("sentinel.api")

app = FastAPI(title="Sentinel Task Orchestration & MCP Server", version="2.0.0")

_active_sse_queues: Dict[str, asyncio.Queue] = {}

# -----------------------------------------------------------------------------
# MCP JSON-RPC 2.0 PROTOCOL SCHEMAS & SANITIZER
# -----------------------------------------------------------------------------
MCP_TOOLS = [
    {
        "name": "sentinel_create_task",
        "description": "Create and schedule a new polyglot task (Python, Bash, Node.js) with git version control, .env secret isolation, and auto-healing fallback.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Descriptive human-readable name of the task (e.g. 'Sync S3 Uploads' or 'Monthly Utility Invoicing')"},
                "description": {"type": "string", "description": "OBLIGATORIO: 1-3 frases con el objetivo de la tarea segun la peticion original del usuario: que debe hacer, para que sirve y criterio de exito. Se guarda en task.json + TASK.md y se inyecta al auto-heal/clasificador para no romper la intencion."},
                "schedule_cron": {"type": "string", "description": "Standard 5-field cron expression (e.g. '0 3 * * *' for 3 AM daily or '*/30 * * * *' for every 30m)"},
                "language": {"type": "string", "enum": ["python", "bash", "nodejs"], "description": "Programming language / runtime for the script"},
                "script_code": {"type": "string", "description": "The full source code of the script to execute"},
                "env_vars": {"type": "object", "description": "Optional dictionary of secret environment variables stored securely in the task's private .env file"},
                "requires_browser": {"type": "boolean", "description": "Set to true if this task uses Steel Browser for web automation / 2FA checkpoints"}
            },
            "required": ["name", "schedule_cron", "language", "script_code", "description"]
        }
    },
    {
        "name": "sentinel_list_tasks",
        "description": "List all active scheduled tasks in Sentinel, including schedules, languages, git version, and recent execution status.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "sentinel_run_task",
        "description": "Trigger an immediate execution of a task with the full error classification and self-healing pipeline.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Unique identifier of the task"}
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "sentinel_update_task",
        "description": "Update the schedule, source code, description/goal, or environment secrets of an existing task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID of the task to update"},
                "name": {"type": "string", "description": "Optional new name"},
                "description": {"type": "string", "description": "Optional new goal description (1-3 frases: que hace, para que, criterio de exito)"},
                "schedule_cron": {"type": "string", "description": "Optional new cron expression"},
                "script_code": {"type": "string", "description": "Optional updated script code"},
                "env_vars": {"type": "object", "description": "Optional updated environment secrets"}
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "sentinel_delete_task",
        "description": "Delete a task, remove its cron schedule from sentinel.tab, and archive its files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID of the task to delete"}
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "sentinel_get_task_logs",
        "description": "View recent execution logs and git commit history for a specific task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task identifier"},
                "lines": {"type": "integer", "description": "Number of log lines to retrieve (default: 100)"}
            },
            "required": ["task_id"]
        }
    }
]


def handle_mcp_tool_call(name: str, args: dict) -> dict:
    """Dispatches tool executions for MCP clients."""
    normalized_name = name.replace("centinela_", "sentinel_")
    
    if normalized_name == "sentinel_create_task":
        task_name = args.get("name")
        cron_expr = args.get("schedule_cron")
        lang = args.get("language", "python")
        code = args.get("script_code", "")
        env_vars = args.get("env_vars", {})
        requires_browser = args.get("requires_browser", False)
        description = (args.get("description", "") or "").strip()
        if not description:
            return {
                "content": [{
                    "type": "text",
                    "text": "❌ Falta 'description': escribe 1-3 frases con el objetivo segun la peticion del usuario (que hace, para que, criterio de exito)."
                }],
                "isError": True,
            }
        
        task_id = task_name.lower().replace(" ", "_").replace("-", "_")
        task_id = "".join(c for c in task_id if c.isalnum() or c == "_")[:32]
        if not task_id or (TASKS_DIR / task_id).exists():
            task_id = f"{task_id}_{uuid.uuid4().hex[:6]}"
            
        task_dir = TASKS_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        
        ext_map = {"python": "main.py", "bash": "main.sh", "nodejs": "main.js"}
        script_file = ext_map.get(lang, "main.sh")
        (task_dir / script_file).write_text(code, encoding="utf-8")
        os.chmod(task_dir / script_file, 0o755)
        
        if env_vars:
            env_lines = [f"{k}={v}" for k, v in env_vars.items()]
            (task_dir / ".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")
            os.chmod(task_dir / ".env", 0o600)
            
        meta = {
            "id": task_id,
            "name": task_name,
            "description": description,
            "language": lang,
            "script_file": script_file,
            "schedule_cron": cron_expr,
            "requires_browser": requires_browser,
            "created_at": asyncio.get_event_loop().time()
        }
        TaskRunner.save_task_meta(task_id, meta)
        # TASK.md: proposito legible para humanos y auto-heal (no secretos).
        (task_dir / "TASK.md").write_text(
            f"# {task_name}\n\n## Objetivo\n{description}\n\n"
            f"- Horario: `{cron_expr}`\n- Lenguaje: `{lang}`\n- Browser: `{requires_browser}`\n",
            encoding="utf-8",
        )
        GitManager.init_task_repo(task_dir, f"Initial task commit: {task_name}")
        
        cmd = f"/usr/local/bin/sentinel-run --id {task_id}"
        CronManager.add_or_update_task(task_id, task_name, cron_expr, cmd)
        
        return {
            "content": [{
                "type": "text",
                "text": f"✅ Tarea '{task_name}' creada y programada con éxito.\n• ID: {task_id}\n• Horario: {cron_expr}\n• Ubicación: {task_dir}\n• Git tracking & AutoHeal: Activo"
            }]
        }

    elif normalized_name == "sentinel_list_tasks":
        tasks = []
        if TASKS_DIR.exists():
            for d in TASKS_DIR.iterdir():
                if d.is_dir() and (d / "task.json").exists():
                    meta = TaskRunner.load_task_meta(d.name) or {}
                    history = GitManager.get_history(d, limit=1)
                    last_commit = history[0]["commit"] if history else "none"
                    tasks.append({
                        "id": d.name,
                        "name": meta.get("name", d.name),
                        "description": meta.get("description", ""),
                        "schedule": meta.get("schedule_cron", "manual"),
                        "language": meta.get("language", "unknown"),
                        "git_version": last_commit
                    })
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(tasks, indent=2, ensure_ascii=False)
            }]
        }

    elif normalized_name == "sentinel_run_task":
        task_id = args.get("task_id")
        res = TaskRunner.run_task(task_id)
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(res, indent=2, ensure_ascii=False)
            }]
        }

    elif normalized_name == "sentinel_get_task_logs":
        task_id = args.get("task_id")
        lines_count = args.get("lines", 100)
        log_file = LOGS_DIR / f"{task_id}.log"
        content = "No log file found."
        if log_file.exists():
            all_lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
            content = "\n".join(all_lines[-lines_count:])
        history = GitManager.get_history(TASKS_DIR / task_id, limit=5)
        return {
            "content": [{
                "type": "text",
                "text": f"--- RECENT LOGS ---\n{content}\n\n--- GIT HISTORY ---\n{json.dumps(history, indent=2)}"
            }]
        }

    elif normalized_name == "sentinel_update_task":
        task_id = args.get("task_id")
        task_dir = TASKS_DIR / task_id
        meta = TaskRunner.load_task_meta(task_id) or {}
        if not task_dir.is_dir() or not meta:
            return {"content": [{"type": "text", "text": f"❌ Tarea '{task_id}' no encontrada."}], "isError": True}
        if args.get("name"):
            meta["name"] = args["name"]
        if args.get("description"):
            meta["description"] = args["description"].strip()
        if args.get("schedule_cron"):
            meta["schedule_cron"] = args["schedule_cron"]
        if args.get("script_code"):
            script_file = meta.get("script_file", "main.py")
            (task_dir / script_file).write_text(args["script_code"], encoding="utf-8")
            os.chmod(task_dir / script_file, 0o755)
        if args.get("env_vars") is not None:
            env_lines = [f"{k}={v}" for k, v in (args.get("env_vars") or {}).items()]
            (task_dir / ".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")
            os.chmod(task_dir / ".env", 0o600)
        TaskRunner.save_task_meta(task_id, meta)
        if meta.get("description"):
            (task_dir / "TASK.md").write_text(
                f"# {meta.get('name', task_id)}\n\n## Objetivo\n{meta['description']}\n\n"
                f"- Horario: `{meta.get('schedule_cron', '')}`\n- Lenguaje: `{meta.get('language', '')}`\n"
                f"- Browser: `{meta.get('requires_browser', False)}`\n",
                encoding="utf-8",
            )
        cmd = f"/usr/local/bin/sentinel-run --id {task_id}"
        CronManager.add_or_update_task(task_id, meta.get("name", task_id), meta.get("schedule_cron", "0 5 * * *"), cmd)
        return {"content": [{"type": "text", "text": f"✅ Tarea '{task_id}' actualizada (incl. TASK.md)."}]}

    elif normalized_name == "sentinel_delete_task":
        task_id = args.get("task_id")
        CronManager.remove_task(task_id)
        return {
            "content": [{
                "type": "text",
                "text": f"✅ Tarea '{task_id}' eliminada del crontab de Sentinel."
            }]
        }

    return {"content": [{"type": "text", "text": f"Tool '{name}' not found."}], "isError": True}


def process_jsonrpc_request(body: dict) -> Optional[dict]:
    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})

    if method == "notifications/initialized":
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "sentinel-mcp-server",
                    "version": "2.0.0"
                }
            }
        }

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": MCP_TOOLS
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        result = handle_mcp_tool_call(tool_name, tool_args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method '{method}' not found"}
    }


# -----------------------------------------------------------------------------
# MCP SSE ENDPOINT & JSON-RPC 2.0 HANDLERS
# -----------------------------------------------------------------------------
@app.get("/sse")
@app.get("/mcp")
async def mcp_sse_endpoint(request: Request):
    session_id = request.headers.get("Mcp-Session-Id") or request.query_params.get("sessionId") or str(uuid.uuid4())
    q: asyncio.Queue = asyncio.Queue()
    _active_sse_queues[session_id] = q

    async def event_generator():
        # Yield endpoint immediately
        endpoint_url = f"/messages?sessionId={session_id}"
        yield f"event: endpoint\ndata: {endpoint_url}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"event: message\ndata: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            _active_sse_queues.pop(session_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Mcp-Session-Id": session_id
        }
    )


@app.post("/messages")
@app.post("/mcp/messages")
async def mcp_messages_endpoint(request: Request):
    session_id = request.headers.get("Mcp-Session-Id") or request.query_params.get("sessionId")
    
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None})

    response_data = process_jsonrpc_request(body)

    # If SSE queue is active for this session, push response to queue as well
    if session_id and session_id in _active_sse_queues and response_data is not None:
        await _active_sse_queues[session_id].put(response_data)

    if response_data is None:
        return Response(status_code=204)
        
    return JSONResponse(content=response_data)


# -----------------------------------------------------------------------------
# REST API ENDPOINTS
# -----------------------------------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "sentinel", "version": "2.0.0"}


@app.get("/api/tasks")
def list_tasks_rest():
    tasks = []
    if TASKS_DIR.exists():
        for d in TASKS_DIR.iterdir():
            if d.is_dir() and (d / "task.json").exists():
                meta = TaskRunner.load_task_meta(d.name) or {}
                tasks.append(meta)
    return {"tasks": tasks}


@app.post("/api/tasks/{task_id}/run")
def run_task_rest(task_id: str):
    res = TaskRunner.run_task(task_id)
    return res


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.SENTINEL_HOST, port=settings.SENTINEL_PORT)
