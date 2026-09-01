import os
import subprocess
import asyncio
import json
import socket
import ssl
import time
import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import httpx

app = FastAPI(title="Headscale Client & Connectivity Diagnostic Suite", version="1.4.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_DIR = os.path.dirname(BASE_DIR)
DEFAULT_LIST = os.path.join(CLIENT_DIR, "domains.default.txt")
CUSTOM_LIST = os.path.join(CLIENT_DIR, "domains.custom.txt")
ROUTES_FILE = os.path.join(CLIENT_DIR, "routes.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")
ENV_FILE = os.path.join(CLIENT_DIR, ".env")
TAILSCALED_DEFAULT_CONFIG = "/etc/default/tailscaled"

os.makedirs(STATIC_DIR, exist_ok=True)

class ModeRequest(BaseModel):
    mode: str # 'full' or 'mesh'
    exit_node: Optional[str] = None

class SingleDiagnoseRequest(BaseModel):
    domain: str

class DeepDiagnoseRequest(BaseModel):
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

class CustomDomainRequest(BaseModel):
    domain: str
    name: Optional[str] = None
    category: Optional[str] = "Personalizado"

class RouteAddRequest(BaseModel):
    ips: List[str]
    domain: str

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

# ----------------- SYSTEM ROUTES MANAGEMENT -----------------

def get_persisted_routes() -> List[Dict[str, Any]]:
    if os.path.isfile(ROUTES_FILE):
        try:
            with open(ROUTES_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_persisted_routes(routes: List[Dict[str, Any]]):
    with open(ROUTES_FILE, "w") as f:
        json.dump(routes, f, indent=2)

def check_active_system_route(ip: str) -> bool:
    try:
        res = subprocess.run(["ip", "route", "show", f"{ip}/32"], capture_output=True, text=True)
        return "tailscale0" in res.stdout
    except Exception:
        return False

def apply_system_route(ip: str) -> bool:
    try:
        # Replace/Add route via tailscale0
        res = subprocess.run(["ip", "route", "replace", f"{ip}/32", "dev", "tailscale0"], capture_output=True, text=True)
        return res.returncode == 0
    except Exception:
        return False

def remove_system_route(ip: str) -> bool:
    try:
        res = subprocess.run(["ip", "route", "del", f"{ip}/32", "dev", "tailscale0"], capture_output=True, text=True)
        return res.returncode == 0
    except Exception:
        return False

# ----------------- VPN STATUS -----------------

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

# ----------------- DIAGNOSTICS HELPERS -----------------

async def resolve_all_ips(domain: str) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    ipv4_list = []
    ipv6_list = []
    cnames = []
    
    try:
        # Standard getaddrinfo for all records
        infos = await loop.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
        for item in infos:
            ip = item[4][0]
            if ":" in ip:
                if ip not in ipv6_list:
                    ipv6_list.append(ip)
            else:
                if ip not in ipv4_list:
                    ipv4_list.append(ip)
    except Exception:
        pass

    # Dig CNAME and extra IPs if available
    try:
        proc = await asyncio.create_subprocess_exec("dig", "+short", "CNAME", domain, stdout=asyncio.subprocess.PIPE)
        out, _ = await proc.communicate()
        for line in out.decode().splitlines():
            line = line.strip().rstrip(".")
            if line and line not in cnames:
                cnames.append(line)
    except Exception:
        pass

    return {
        "domain": domain,
        "ipv4": ipv4_list,
        "ipv6": ipv6_list,
        "cnames": cnames,
        "total_ips": len(ipv4_list) + len(ipv6_list)
    }

async def ping_ip(ip: str) -> Dict[str, Any]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "2", "-W", "2", ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        out, _ = await proc.communicate()
        out_str = out.decode()
        if proc.returncode == 0:
            # Parse average RTT
            for line in out_str.splitlines():
                if "avg" in line or "rtt" in line:
                    parts = line.split("=")[1].split("/")
                    return {"success": True, "avg_rtt_ms": float(parts[1].strip()), "packet_loss": 0}
            return {"success": True, "avg_rtt_ms": 10.0, "packet_loss": 0}
        return {"success": False, "avg_rtt_ms": None, "packet_loss": 100}
    except Exception:
        return {"success": False, "avg_rtt_ms": None, "packet_loss": 100}

async def tcp_connect_test(ip: str, port: int = 443) -> Dict[str, Any]:
    t0 = time.time()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=3.0)
        dur = int((time.time() - t0) * 1000)
        writer.close()
        await writer.wait_closed()
        return {"success": True, "latency_ms": dur, "port": port}
    except Exception as e:
        return {"success": False, "latency_ms": None, "port": port, "error": str(e)}

async def tls_sni_handshake_test(domain: str, ip: Optional[str] = None) -> Dict[str, Any]:
    t0 = time.time()
    target = ip or domain
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        loop = asyncio.get_event_loop()
        
        def _do_ssl():
            raw_s = socket.create_connection((target, 443), timeout=3.5)
            with ctx.wrap_socket(raw_s, server_hostname=domain) as s:
                cert = s.getpeercert()
                issuer = dict(x[0] for x in cert.get("issuer", []))
                return {
                    "issuer": issuer.get("organizationName", issuer.get("commonName", "Unknown")),
                    "notAfter": cert.get("notAfter", "")
                }
        
        cert_info = await loop.run_in_executor(None, _do_ssl)
        dur = int((time.time() - t0) * 1000)
        return {"status": "OK", "latency_ms": dur, "cert": cert_info}
    except ssl.SSLError as se:
        dur = int((time.time() - t0) * 1000)
        if "handshake" in str(se).lower() or "reset" in str(se).lower():
            return {"status": "DPI_RESET", "latency_ms": dur, "error": str(se)}
        return {"status": "CERT_WARN", "latency_ms": dur, "error": str(se)}
    except Exception as e:
        dur = int((time.time() - t0) * 1000)
        return {"status": "FAIL", "latency_ms": dur, "error": str(e)}

async def http_full_lifecycle(domain: str, proxy: Optional[str] = None) -> Dict[str, Any]:
    url = f"https://{domain}"
    redirects_chain = []
    t0 = time.time()
    
    client_kwargs = {
        "timeout": 6.0,
        "follow_redirects": True,
        "verify": False
    }
    if proxy:
        client_kwargs["proxy"] = proxy

    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.get(url)
            total_dur = int((time.time() - t0) * 1000)
            
            for h in resp.history:
                redirects_chain.append({
                    "url": str(h.url),
                    "status_code": h.status_code
                })
            
            redirects_chain.append({
                "url": str(resp.url),
                "status_code": resp.status_code
            })

            return {
                "success": resp.status_code < 500 or resp.status_code in [200, 301, 302, 401, 403, 404, 405],
                "status_code": resp.status_code,
                "total_time_ms": total_dur,
                "redirects": redirects_chain,
                "final_url": str(resp.url),
                "protocol": resp.http_version,
                "server_header": resp.headers.get("server", "N/A")
            }
    except httpx.ConnectTimeout:
        return {"success": False, "status_code": 0, "total_time_ms": int((time.time() - t0) * 1000), "error": "Connection Timeout", "redirects": []}
    except httpx.ProxyError as pe:
        return {"success": False, "status_code": 0, "total_time_ms": int((time.time() - t0) * 1000), "error": f"Proxy Error: {str(pe)}", "redirects": []}
    except Exception as e:
        return {"success": False, "status_code": 0, "total_time_ms": int((time.time() - t0) * 1000), "error": str(e), "redirects": []}

async def check_domain_deep(domain: str, name: str, category: str) -> Dict[str, Any]:
    domain = domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    
    dns_ok = False
    resolved_ip = ""
    tcp_ok = False
    tls_ok = "FAIL"
    http_code = "000"
    latency_ms = 0

    # 1. DNS
    t0 = time.time()
    try:
        loop = asyncio.get_event_loop()
        addrinfo = await loop.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
        if addrinfo:
            resolved_ip = addrinfo[0][4][0]
            dns_ok = True
    except Exception:
        dns_ok = False

    # 2. TCP
    if dns_ok:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(domain, 443), timeout=3.0)
            tcp_ok = True
            writer.close()
            await writer.wait_closed()
        except Exception:
            tcp_ok = False

    # 3. TLS
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

    # 4. HTTP
    if tcp_ok:
        try:
            async with httpx.AsyncClient(timeout=4.0, follow_redirects=True, verify=False) as client:
                req_t0 = time.time()
                resp = await client.head(f"https://{domain}")
                latency_ms = int((time.time() - req_t0) * 1000)
                http_code = str(resp.status_code)
        except Exception:
            latency_ms = int((time.time() - t0) * 1000)

    # Verdict
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

# ----------------- API ENDPOINTS -----------------

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

# ----------------- CUSTOM DOMAINS -----------------

@app.get("/api/custom-domains")
async def get_custom_domains():
    items = []
    if os.path.isfile(CUSTOM_LIST):
        with open(CUSTOM_LIST, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("|")
                    items.append({
                        "domain": parts[0].strip(),
                        "name": parts[1].strip() if len(parts) > 1 else parts[0].strip(),
                        "category": parts[2].strip() if len(parts) > 2 else "Personalizado"
                    })
    return {"domains": items}

@app.post("/api/custom-domains")
async def add_custom_domain(req: CustomDomainRequest):
    domain = req.domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    if not domain:
        raise HTTPException(status_code=400, detail="Dominio inválido")
    
    name = req.name.strip() if req.name else domain
    category = req.category.strip() if req.category else "Personalizado"
    
    existing = []
    if os.path.isfile(CUSTOM_LIST):
        with open(CUSTOM_LIST, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("|")
                    if parts[0].strip().lower() == domain:
                        return {"success": True, "message": "El dominio ya existe"}
                    existing.append(line)
    
    existing.append(f"{domain}|{name}|{category}")
    with open(CUSTOM_LIST, "w") as f:
        f.write("\n".join(existing) + "\n")
        
    return {"success": True, "message": f"Dominio {domain} agregado correctamente"}

@app.delete("/api/custom-domains/{domain}")
async def delete_custom_domain(domain: str):
    domain_clean = domain.strip().lower()
    existing = []
    found = False
    if os.path.isfile(CUSTOM_LIST):
        with open(CUSTOM_LIST, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("|")
                    if parts[0].strip().lower() == domain_clean:
                        found = True
                        continue
                    existing.append(line)
    
    with open(CUSTOM_LIST, "w") as f:
        f.write("\n".join(existing) + ("\n" if existing else ""))
        
    return {"success": True, "deleted": found}

# ----------------- SYSTEM ROUTES API -----------------

@app.get("/api/routes")
async def get_system_routes():
    persisted = get_persisted_routes()
    for r in persisted:
        r["is_active"] = check_active_system_route(r["ip"])
    return {"routes": persisted}

@app.post("/api/routes")
async def add_system_routes(req: RouteAddRequest):
    persisted = get_persisted_routes()
    existing_ips = {r["ip"] for r in persisted}
    added_count = 0
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for ip in req.ips:
        ip = ip.strip()
        if not ip or ":" in ip: # skip IPv6 for simple kernel routing
            continue
        
        ok = apply_system_route(ip)
        if ip not in existing_ips:
            persisted.append({
                "ip": ip,
                "domain": req.domain,
                "created_at": now_str,
                "is_active": ok
            })
            existing_ips.add(ip)
            added_count += 1
            
    save_persisted_routes(persisted)
    return {"success": True, "added": added_count, "routes": persisted}

@app.delete("/api/routes/{ip}")
async def delete_single_route(ip: str):
    remove_system_route(ip)
    persisted = get_persisted_routes()
    persisted = [r for r in persisted if r["ip"] != ip]
    save_persisted_routes(persisted)
    return {"success": True, "deleted": ip}

@app.delete("/api/routes")
async def clear_all_routes():
    persisted = get_persisted_routes()
    for r in persisted:
        remove_system_route(r["ip"])
    save_persisted_routes([])
    return {"success": True, "cleared_count": len(persisted)}

# ----------------- DEEP CONNECTIVITY DIAGNOSTICS -----------------

async def check_ip_direct_and_vps(ip: str, domain: str, vps_socks5_url: Optional[str], vpn_connected: bool) -> Dict[str, Any]:
    # 1. Local Ping
    ping_res = await ping_ip(ip)
    
    # 2. Local TCP
    tcp_80 = await tcp_connect_test(ip, 80)
    tcp_443 = await tcp_connect_test(ip, 443)
    
    # 3. Local TLS SNI to this specific IP
    tls_res = await tls_sni_handshake_test(domain, ip)
    
    # 4. Local HTTP direct to this IP with Host header
    local_http = {"status_code": 0, "latency_ms": 0, "success": False, "error": "No probado"}
    if tcp_443.get("success"):
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=3.5, verify=False) as client:
                resp = await client.get(f"https://{ip}/", headers={"Host": domain, "User-Agent": "Mozilla/5.0"})
                local_http = {
                    "status_code": resp.status_code,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "success": True,
                    "server": resp.headers.get("server", "N/A")
                }
        except Exception as e:
            local_http = {
                "status_code": 0,
                "latency_ms": int((time.time() - t0) * 1000),
                "success": False,
                "error": str(e)
            }
    elif tcp_80.get("success"):
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=3.5, verify=False) as client:
                resp = await client.get(f"http://{ip}/", headers={"Host": domain, "User-Agent": "Mozilla/5.0"})
                local_http = {
                    "status_code": resp.status_code,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "success": True,
                    "server": resp.headers.get("server", "N/A")
                }
        except Exception as e:
            local_http = {
                "status_code": 0,
                "latency_ms": int((time.time() - t0) * 1000),
                "success": False,
                "error": str(e)
            }

    # 5. VPS HTTP check through SOCKS5 proxy (only if VPN connected)
    vps_http = {"status_code": 0, "latency_ms": 0, "success": False, "error": "VPN Desconectada"}
    if vpn_connected and vps_socks5_url:
        t0_vps = time.time()
        try:
            async with httpx.AsyncClient(proxy=vps_socks5_url, timeout=4.0, verify=False) as client:
                resp_vps = await client.get(f"https://{domain}/", headers={"User-Agent": "Mozilla/5.0"})
                vps_http = {
                    "status_code": resp_vps.status_code,
                    "latency_ms": int((time.time() - t0_vps) * 1000),
                    "success": True,
                    "server": resp_vps.headers.get("server", "N/A")
                }
        except Exception as e:
            vps_http = {
                "status_code": 0,
                "latency_ms": int((time.time() - t0_vps) * 1000),
                "success": False,
                "error": str(e)
            }

    # Per-IP Verdict
    loc_ok = local_http.get("success", False) and (local_http.get("status_code", 0) != 0)
    vps_ok = vps_http.get("success", False) and (vps_http.get("status_code", 0) != 0)
    is_routed = check_active_system_route(ip)
    
    if is_routed:
        verdict = "SOLUCIONADO_ENRUTADA"
    elif not vpn_connected:
        verdict = "ACCESIBLE_LOCAL" if loc_ok else "FALLA_LOCAL"
    elif not loc_ok and vps_ok:
        verdict = "BLOQUEADA_LOCAL"
    elif loc_ok and vps_ok:
        verdict = "LIBRE_AMBOS"
    elif loc_ok and not vps_ok:
        verdict = "LIBRE_LOCAL_FALLA_VPS"
    else:
        verdict = "INACCESIBLE_AMBOS"

    return {
        "ip": ip,
        "ping": ping_res,
        "tcp_80": tcp_80,
        "tcp_443": tcp_443,
        "tls_local": tls_res,
        "local_http": local_http,
        "vps_http": vps_http,
        "verdict": verdict,
        "is_routed": is_routed
    }

# ----------------- DEEP CONNECTIVITY DIAGNOSTICS -----------------

@app.post("/api/deep-diagnose")
async def run_deep_diagnose(req: DeepDiagnoseRequest):
    domain = req.domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    if not domain:
        raise HTTPException(status_code=400, detail="Dominio inválido")

    vpn_status = is_tailscale_connected()
    vpn_connected = vpn_status.get("connected", False)
    vps_socks5_url = "socks5://100.64.0.4:1080" if vpn_connected else None

    # 1. Full DNS Discovery
    dns_data = await resolve_all_ips(domain)
    
    # 2. Detailed Per-IP Diagnostics in parallel (Local vs VPS)
    ip_tasks = [check_ip_direct_and_vps(ip, domain, vps_socks5_url, vpn_connected) for ip in dns_data["ipv4"][:6]]
    ip_tests = await asyncio.gather(*ip_tasks) if ip_tasks else []

    # 3. Global Domain TLS SNI check (Local)
    tls_local = await tls_sni_handshake_test(domain)

    # 4. Global HTTP Full Lifecycle (Local)
    http_local = await http_full_lifecycle(domain, proxy=None)

    # 5. Global HTTP Full Lifecycle (VPS VPN)
    if vpn_connected and vps_socks5_url:
        http_vps = await http_full_lifecycle(domain, proxy=vps_socks5_url)
    else:
        http_vps = {
            "success": False,
            "status_code": 0,
            "total_time_ms": 0,
            "error": "VPN Desconectada",
            "redirects": [],
            "final_url": "-",
            "server_header": "N/A"
        }

    # 6. Accurate Analysis & Recommendation
    local_code = http_local.get("status_code", 0)
    vps_code = http_vps.get("status_code", 0)
    
    has_dns = len(dns_data["ipv4"]) > 0 or len(dns_data["ipv6"]) > 0
    has_tcp = any(t.get("tcp_443", {}).get("success") or t.get("tcp_80", {}).get("success") for t in ip_tests)
    tls_status = tls_local.get("status", "FAIL")
    local_ok = (has_dns and has_tcp and tls_status == "OK" and local_code != 0)
    
    unrouted_blocked = [t["ip"] for t in ip_tests if t["verdict"] in ["BLOQUEADA_LOCAL", "FALLA_LOCAL"]]
    routed_ips = [t["ip"] for t in ip_tests if t.get("is_routed")]
    vpn_working = (vps_code != 0) and (http_vps.get("success", False))

    if not vpn_connected:
        if local_ok:
            action = "NONE"
            reason = f"🟢 Conexión Local Directa Óptima (HTTP {local_code}). El sitio web funciona con normalidad en tu red local (VPN no activa)."
        else:
            action = "CONNECT_VPN"
            reason = f"⚠️ Falla de acceso en tu conexión local ({'TLS/DPI o Timeout' if tls_status != 'OK' else 'HTTP 000'}). La VPN está desconectada: actívala para comparar si el sitio abre a través del VPS y poder enrutarlo."
    else:
        if unrouted_blocked:
            action = "ENROUTE_VPN"
            reason = f"Se detectaron {len(unrouted_blocked)} IP(s) con bloqueo en tu red local ({', '.join(unrouted_blocked)}). Enrútalas para restaurar el acceso."
        elif routed_ips and (local_code != 0 or vps_code != 0):
            action = "SOLUCIONADO"
            reason = f"🟢 Bloqueo Solucionado: {len(routed_ips)} IP(s) están actualmente enrutadas por la VPN (tailscale0). El acceso al host responde con éxito (HTTP {local_code})."
        elif local_ok:
            action = "NONE"
            if local_code == 403:
                reason = f"Conexión directa y VPN funcionando correctamente. El servidor responde HTTP 403 (Restricción propia de la web/CDN '{http_local.get('server_header', '')}', no es bloqueo de tu red)."
            elif local_code == 200:
                reason = "Conexión directa óptima (HTTP 200 OK) tanto en tu red local como por la VPN."
            else:
                reason = f"Conexión directa y VPN funcionando por igual (HTTP {local_code}). Sin bloqueos de proveedor."
        else:
            action = "NONE"
            reason = "El sitio web no responde en ninguna de las dos conexiones (posible caída del servidor remoto)."

    return {
        "domain": domain,
        "dns": dns_data,
        "ip_tests": ip_tests,
        "tls_local": tls_local,
        "http_local": http_local,
        "http_vps": http_vps,
        "vpn_connected": vpn_connected,
        "analysis": {
            "local_working": (local_code != 0),
            "vpn_working": vpn_working,
            "vpn_connected": vpn_connected,
            "recommended_action": action,
            "message": reason,
            "routed_ips_count": len(routed_ips)
        },
        "ips_to_route": unrouted_blocked or dns_data["ipv4"]
    }

# ----------------- SWITCHYOMEGA RULES EXPORT -----------------

@app.get("/api/switchyomega-rules")
async def get_switchyomega_rules(include_adult: bool = Query(False), profile: str = Query("proxy")):
    domains_set = set()
    ignore_categories = {"Core"}
    if not include_adult:
        ignore_categories.add("Adulto")

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
    domain = req.domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    res = await check_domain_deep(domain, domain, "Personalizado")
    return res

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

if __name__ == "__main__":
    import uvicorn
    port = int(get_env_var("WEB_PORT", "29485"))
    uvicorn.run(app, host="0.0.0.0", port=port)
