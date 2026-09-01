import os
import subprocess
import asyncio
import json
import socket
import ssl
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Headscale Client Dashboard", version="1.0.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_DIR = os.path.dirname(BASE_DIR)
DEFAULT_LIST = os.path.join(CLIENT_DIR, "domains.default.txt")
CUSTOM_LIST = os.path.join(CLIENT_DIR, "domains.custom.txt")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(STATIC_DIR, exist_ok=True)

class ModeRequest(BaseModel):
    mode: str # 'full' or 'direct'

class SingleDiagnoseRequest(BaseModel):
    domain: str

def get_env_var(name: str, default: str = "") -> str:
    env_file = os.path.join(CLIENT_DIR, ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if line.strip().startswith(f"{name}="):
                    return line.strip().split("=", 1)[1].strip('"\'')
    return os.environ.get(name, default)

def run_cmd(cmd: List[str]) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def is_tailscale_connected() -> Dict[str, Any]:
    try:
        res = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            return {"connected": False, "raw": "Tailscale not running"}
        data = json.loads(res.stdout)
        
        self_node = data.get("Self", {})
        ips = self_node.get("TailscaleIPs", [])
        ipv4 = ips[0] if ips else "N/A"
        ipv6 = ips[1] if len(ips) > 1 else ""
        exit_node_ip = data.get("ExitNodeIP", "") or self_node.get("ExitNodeIP", "")
        
        peers_count = len(data.get("Peer", {}))
        
        mode = "full" if exit_node_ip and exit_node_ip != "null" else "direct"
        
        return {
            "connected": True,
            "ipv4": ipv4,
            "ipv6": ipv6,
            "mode": mode,
            "exit_node_ip": exit_node_ip if mode == "full" else None,
            "hostname": self_node.get("HostName", "laptop"),
            "peers_count": peers_count,
            "server_url": get_env_var("HEADSCALE_URL", "https://headscale.jeisson.top")
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}

async def check_domain_deep(domain: str, name: str, category: str) -> Dict[str, Any]:
    domain = domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    
    dns_ok = False
    resolved_ip = ""
    tcp_ok = False
    tls_ok = "FAIL"
    http_code = "000"
    latency_ms = 0
    verdict = "DESCONOCIDO"

    # 1. DNS Resolution
    t0 = time.time()
    try:
        loop = asyncio.get_event_loop()
        addrinfo = await loop.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
        if addrinfo:
            resolved_ip = addrinfo[0][4][0]
            dns_ok = True
    except Exception:
        dns_ok = False

    # 2. TCP Check
    if dns_ok:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(domain, 443), timeout=3.0)
            tcp_ok = True
            writer.close()
            await writer.wait_closed()
        except Exception:
            tcp_ok = False

    # 3. TLS / SNI Check
    if tcp_ok:
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: ctx.wrap_socket(socket.create_connection((domain, 443), timeout=3.0), server_hostname=domain).close())
            tls_ok = "OK"
        except ssl.SSLError as se:
            if "handshake" in str(se).lower() or "reset" in str(se).lower():
                tls_ok = "DPI_RESET"
            else:
                tls_ok = "WARN"
        except Exception:
            tls_ok = "WARN"

    # 4. HTTP Code & Latency
    if tcp_ok:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=4.0, follow_redirects=True, verify=False) as client:
                req_t0 = time.time()
                resp = await client.head(f"https://{domain}")
                latency_ms = int((time.time() - req_t0) * 1000)
                http_code = str(resp.status_code)
        except Exception:
            latency_ms = int((time.time() - t0) * 1000)

    # Determine verdict
    if not dns_ok:
        verdict = "BLOQUEO_DNS"
    elif not tcp_ok:
        verdict = "BLOQUEO_TCP"
    elif tls_ok == "DPI_RESET":
        verdict = "BLOQUEO_DPI"
    elif http_code and http_code != "000":
        verdict = "LIBRE"
    else:
        verdict = "RESTRINGIDO"

    return {
        "domain": domain,
        "name": name,
        "category": category,
        "ip": resolved_ip or "-",
        "dns": "OK" if dns_ok else "FAIL",
        "tcp": "OK" if tcp_ok else "FAIL",
        "tls": tls_ok,
        "http_code": http_code,
        "latency_ms": latency_ms,
        "verdict": verdict
    }

@app.get("/api/status")
async def get_status():
    return is_tailscale_connected()

@app.post("/api/mode")
async def set_mode(req: ModeRequest):
    exit_node = get_env_var("EXIT_NODE", "100.64.0.4")
    if req.mode == "full":
        res = subprocess.run(["sudo", "tailscale", "set", f"--exit-node={exit_node}", "--exit-node-allow-lan-access=true"], capture_output=True, text=True)
        return {"success": res.returncode == 0, "mode": "full", "output": res.stdout}
    elif req.mode == "direct":
        res = subprocess.run(["sudo", "tailscale", "set", "--exit-node="], capture_output=True, text=True)
        return {"success": res.returncode == 0, "mode": "direct", "output": res.stdout}
    raise HTTPException(status_code=400, detail="Invalid mode. Use 'full' or 'direct'.")

@app.post("/api/connect")
async def connect_vpn():
    server = get_env_var("HEADSCALE_URL", "https://headscale.jeisson.top")
    key = get_env_var("HEADSCALE_AUTH_KEY", "")
    hostname = get_env_var("CLIENT_HOSTNAME", "jeisson-laptop")
    cmd = ["sudo", "tailscale", "up", f"--login-server={server}", f"--hostname={hostname}", "--accept-routes", "--reset"]
    if key:
        cmd.append(f"--authkey={key}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    return {"success": res.returncode == 0, "output": res.stdout or res.stderr}

@app.post("/api/disconnect")
async def disconnect_vpn():
    res = subprocess.run(["sudo", "tailscale", "down"], capture_output=True, text=True)
    return {"success": res.returncode == 0, "output": res.stdout}

@app.get("/api/diagnose")
async def run_diagnostics(category: Optional[str] = Query(None)):
    domain_items = []
    
    # Load default
    if os.path.isfile(DEFAULT_LIST):
        with open(DEFAULT_LIST) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("|")
                    domain = parts[0]
                    name = parts[1] if len(parts) > 1 else domain
                    cat = parts[2] if len(parts) > 2 else "General"
                    if not category or category.lower() == cat.lower():
                        domain_items.append((domain, name, cat))

    # Load custom
    if os.path.isfile(CUSTOM_LIST):
        with open(CUSTOM_LIST) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("|")
                    domain = parts[0]
                    name = parts[1] if len(parts) > 1 else domain
                    cat = parts[2] if len(parts) > 2 else "Personalizado"
                    if not category or category.lower() == cat.lower():
                        domain_items.append((domain, name, cat))

    tasks = [check_domain_deep(d, n, c) for d, n, c in domain_items]
    results = await asyncio.gather(*tasks)
    
    free_count = sum(1 for r in results if r["verdict"] == "LIBRE")
    blocked_count = len(results) - free_count

    return {
        "total": len(results),
        "free": free_count,
        "blocked": blocked_count,
        "results": results
    }

@app.post("/api/diagnose/single")
async def diagnose_single(req: SingleDiagnoseRequest):
    res = await check_domain_deep(req.domain, req.domain, "Personalizado")
    return res

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

if __name__ == "__main__":
    import uvicorn
    port = int(get_env_var("WEB_PORT", "29485"))
    uvicorn.run(app, host="0.0.0.0", port=port)
