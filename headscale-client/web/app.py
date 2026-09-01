import os
import subprocess
import asyncio
import json
import socket
import ssl
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Headscale Client Dashboard", version="1.3.1")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_DIR = os.path.dirname(BASE_DIR)
DEFAULT_LIST = os.path.join(CLIENT_DIR, "domains.default.txt")
CUSTOM_LIST = os.path.join(CLIENT_DIR, "domains.custom.txt")
STATIC_DIR = os.path.join(BASE_DIR, "static")
ENV_FILE = os.path.join(CLIENT_DIR, ".env")
TAILSCALED_DEFAULT_CONFIG = "/etc/default/tailscaled"

os.makedirs(STATIC_DIR, exist_ok=True)

class ModeRequest(BaseModel):
    mode: str # 'full' or 'mesh'
    exit_node: Optional[str] = None

class SingleDiagnoseRequest(BaseModel):
    domain: str

class ProxyRequest(BaseModel):
    enabled: bool
    port: Optional[int] = 1080

class AutostartRequest(BaseModel):
    enabled: bool

class ConfigUpdateRequest(BaseModel):
    server_url: str
    auth_key: str
    hostname: str
    exit_node: Optional[str] = "100.64.0.4"

class ConnectRequest(BaseModel):
    server_url: Optional[str] = None
    auth_key: Optional[str] = None
    hostname: Optional[str] = None

def get_env_var(name: str, default: str = "") -> str:
    if os.path.isfile(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{name}="):
                    return line.split("=", 1)[1].strip('"\'')
    return os.environ.get(name, default)

def set_env_vars(data: Dict[str, str]):
    current = {}
    if os.path.isfile(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    current[k.strip()] = v.strip('"\'')
    
    current.update(data)
    
    with open(ENV_FILE, "w") as f:
        f.write("# Headscale Client Environment Configuration\n")
        for k, v in current.items():
            f.write(f'{k}="{v}"\n')

def check_socks5_listening(port: int = 1080) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.4)
        result = s.connect_ex(("127.0.0.1", port)) == 0
        s.close()
        return result
    except Exception:
        return False

def check_vpn_autostart() -> bool:
    wants_path = "/etc/systemd/system/multi-user.target.wants/tailscaled.service"
    return os.path.exists(wants_path) or os.path.islink(wants_path)

def check_proxy_autostart() -> bool:
    try:
        if os.path.isfile(TAILSCALED_DEFAULT_CONFIG):
            with open(TAILSCALED_DEFAULT_CONFIG) as f:
                content = f.read()
                return "socks5-server" in content
    except Exception:
        pass
    return False

def is_tailscale_connected() -> Dict[str, Any]:
    try:
        res = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            return {
                "connected": False,
                "backend_state": "Stopped",
                "raw": "Tailscale daemon stopped",
                "vpn_autostart": check_vpn_autostart(),
                "proxy_autostart": check_proxy_autostart(),
                "proxy_listening": check_socks5_listening(1080)
            }
        
        data = json.loads(res.stdout)
        backend_state = data.get("BackendState", "Stopped")
        
        self_node = data.get("Self", {})
        ips = self_node.get("TailscaleIPs", [])
        ipv4 = ips[0] if ips else "N/A"
        ipv6 = ips[1] if len(ips) > 1 else ""
        
        # Discover all available exit nodes and peers
        exit_nodes = []
        peers_list = []
        active_exit_ip = data.get("ExitNodeIP", "") or self_node.get("ExitNodeIP", "")
        if active_exit_ip == "null":
            active_exit_ip = ""

        for p_id, peer in data.get("Peer", {}).items():
            p_ips = peer.get("TailscaleIPs", [])
            p_ipv4 = p_ips[0] if p_ips else ""
            p_name = peer.get("HostName", "peer")
            p_online = peer.get("Online", False)
            offers_exit = peer.get("ExitNodeOption", False) or ("0.0.0.0/0" in peer.get("AllowedIPs", []))
            is_active_exit = peer.get("ExitNode", False)
            
            if is_active_exit and p_ipv4:
                active_exit_ip = p_ipv4
            
            peers_list.append({
                "name": p_name,
                "ip": p_ipv4,
                "os": peer.get("OS", "linux"),
                "online": p_online,
                "offers_exit": offers_exit,
                "is_active_exit": is_active_exit
            })
            
            if offers_exit and p_ipv4:
                exit_nodes.append({
                    "ip": p_ipv4,
                    "name": p_name,
                    "online": p_online
                })
        
        mode = "full" if (active_exit_ip and backend_state == "Running") else "mesh"
        
        return {
            "connected": backend_state == "Running",
            "backend_state": backend_state,
            "ipv4": ipv4 if backend_state == "Running" else "-",
            "ipv6": ipv6 if backend_state == "Running" else "-",
            "mode": mode,
            "exit_node_ip": active_exit_ip if mode == "full" else None,
            "hostname": self_node.get("HostName", "laptop"),
            "peers": peers_list,
            "peers_count": len(peers_list),
            "exit_nodes": exit_nodes,
            "vpn_autostart": check_vpn_autostart(),
            "proxy_autostart": check_proxy_autostart(),
            "proxy_listening": check_socks5_listening(1080),
            "server_url": get_env_var("HEADSCALE_URL", "https://headscale.jeisson.top")
        }
    except Exception as e:
        return {"connected": False, "backend_state": "Error", "error": str(e)}

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

@app.get("/api/config")
async def get_config():
    return {
        "server_url": get_env_var("HEADSCALE_URL", "https://headscale.jeisson.top"),
        "auth_key": get_env_var("HEADSCALE_AUTH_KEY", ""),
        "hostname": get_env_var("CLIENT_HOSTNAME", "jeisson-laptop"),
        "exit_node": get_env_var("EXIT_NODE", "100.64.0.4")
    }

@app.post("/api/config")
async def update_config(req: ConfigUpdateRequest):
    set_env_vars({
        "HEADSCALE_URL": req.server_url.strip(),
        "HEADSCALE_AUTH_KEY": req.auth_key.strip(),
        "CLIENT_HOSTNAME": req.hostname.strip(),
        "EXIT_NODE": req.exit_node.strip() if req.exit_node else "100.64.0.4"
    })
    return {"success": True, "message": "Configuración guardada correctamente en .env"}

@app.post("/api/mode")
async def set_mode(req: ModeRequest):
    if req.mode in ["full", "exit"]:
        exit_node = req.exit_node or get_env_var("EXIT_NODE", "100.64.0.4")
        res = subprocess.run(["tailscale", "set", f"--exit-node={exit_node}", "--exit-node-allow-lan-access=true"], capture_output=True, text=True)
        return {"success": res.returncode == 0, "mode": "full", "exit_node": exit_node, "output": res.stdout or res.stderr}
    elif req.mode in ["mesh", "direct"]:
        res = subprocess.run(["tailscale", "set", "--exit-node="], capture_output=True, text=True)
        return {"success": res.returncode == 0, "mode": "mesh", "output": res.stdout or res.stderr}
    raise HTTPException(status_code=400, detail="Invalid mode. Use 'full' or 'mesh'.")

@app.post("/api/connect")
async def connect_vpn(req: Optional[ConnectRequest] = None):
    server = (req.server_url if req and req.server_url else "") or get_env_var("HEADSCALE_URL", "https://headscale.jeisson.top")
    key = (req.auth_key if req and req.auth_key else "") or get_env_var("HEADSCALE_AUTH_KEY", "")
    hostname = (req.hostname if req and req.hostname else "") or get_env_var("CLIENT_HOSTNAME", "jeisson-laptop")
    
    cmd = ["tailscale", "up", f"--login-server={server}", f"--hostname={hostname}", "--accept-routes", "--reset"]
    if key:
        cmd.append(f"--authkey={key}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    return {"success": res.returncode == 0, "output": res.stdout or res.stderr}

@app.post("/api/disconnect")
async def disconnect_vpn():
    res = subprocess.run(["tailscale", "down"], capture_output=True, text=True)
    return {"success": res.returncode == 0, "output": res.stdout or res.stderr}

@app.post("/api/autostart/vpn")
async def toggle_vpn_autostart(req: AutostartRequest):
    wants_path = "/etc/systemd/system/multi-user.target.wants/tailscaled.service"
    service_path = "/usr/lib/systemd/system/tailscaled.service"
    if not os.path.exists(service_path):
        service_path = "/lib/systemd/system/tailscaled.service"
        
    try:
        if req.enabled:
            os.makedirs(os.path.dirname(wants_path), exist_ok=True)
            if not (os.path.exists(wants_path) or os.path.islink(wants_path)):
                os.symlink(service_path, wants_path)
        else:
            if os.path.islink(wants_path) or os.path.exists(wants_path):
                os.remove(wants_path)
        return {"success": True, "vpn_autostart": check_vpn_autostart()}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/autostart/proxy")
async def toggle_proxy_autostart(req: AutostartRequest):
    flags = '--socks5-server=localhost:1080' if req.enabled else ''
    config_content = f'PORT="41641"\nFLAGS="{flags}"\n'
    try:
        with open(TAILSCALED_DEFAULT_CONFIG, "w") as f:
            f.write(config_content)
        return {
            "success": True,
            "proxy_autostart": check_proxy_autostart(),
            "proxy_listening": check_socks5_listening(1080)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/switchyomega-rules")
async def get_switchyomega_rules(include_adult: bool = Query(False), profile: str = Query("proxy")):
    domains_set = set()
    
    # Non-restricted core domains to exclude from proxy list unless custom
    ignore_categories = {"Core"}
    if not include_adult:
        ignore_categories.add("Adulto")

    # Read default
    if os.path.isfile(DEFAULT_LIST):
        with open(DEFAULT_LIST) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("|")
                    domain = parts[0].strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
                    cat = parts[2].strip() if len(parts) > 2 else "General"
                    if cat not in ignore_categories and not domain.replace(".", "").isdigit():
                        domains_set.add(domain)

    # Read custom
    if os.path.isfile(CUSTOM_LIST):
        with open(CUSTOM_LIST) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("|")
                    domain = parts[0].strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
                    if not domain.replace(".", "").isdigit():
                        domains_set.add(domain)

    sorted_domains = sorted(list(domains_set))
    lines = ["[SwitchyOmega Conditions]", "@with result", ""]
    for d in sorted_domains:
        lines.append(f"*.{d} +{profile}")
        if not d.startswith("web."):
            lines.append(f"{d} +{profile}")
    lines.append("")
    lines.append("* +direct")
    lines.append("")

    return {"content": "\n".join(lines), "total_rules": len(sorted_domains)}

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
