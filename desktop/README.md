# Remote Desktop (XFCE4, XRDP, KasmVNC)

Lightweight, high-performance remote desktop environment for Linux VPS with **XFCE4**, **KasmVNC** (HTML5 Web Desktop via WebSockets/WebP), and **XRDP** (RDP client access via WireGuard/Tunnel).

---

## 1. Architecture & Access Methods

| Access Method | Protocol / Port | Transport | Best For |
| :--- | :--- | :--- | :--- |
| **KasmVNC (Web Browser)** | HTTPS (443) / WSS | Nginx Reverse Proxy (`vnc.yourdomain.com`, `desktop.yourdomain.com`) | Zero client install, any browser (desktop, tablet, mobile) |
| **XRDP (RDP Client)** | RDP (3389) | Loopback / WireGuard VPN tunnel | Microsoft Remote Desktop, Remmina, native desktop clients |

> [!IMPORTANT]
> - **Security**: XRDP (port 3389) is **never exposed directly to the public internet**. It is bound to `127.0.0.1` and accessible only via SSH tunnel or WireGuard VPN.
> - **Web Access**: KasmVNC web access is securely routed through **Nginx with Let's Encrypt HTTPS/WSS** and authenticated with your credentials.

---

## 2. Installation & Configuration

### 1. Configure `.env` on your VPS
```bash
cd vps-tools/desktop
cp .env.example .env
nano .env
```
Set your user and secure password:
```env
DESKTOP_USER=jeisson
DESKTOP_PASSWORD=YourSuperStrongPasswordHere
KASMVNC_PORT=8444
KASMVNC_RESOLUTION=1920x1080
```

### 2. Run Automated Installation
```bash
sudo bash scripts/install_desktop.sh
```
This script:
1. Installs `xfce4`, `xfce4-goodies`, `dbus-x11`, `xrdp`, `xorgxrdp`.
2. Downloads and installs **KasmVNC Server** deb package.
3. Configures XFCE session startup (`~/.vnc/xstartup` and `~/.xsession`).
4. Sets up KasmVNC password and permissions for `DESKTOP_USER`.
5. Enables and starts the `kasmvnc@<username>` systemd service.
6. Configures UFW firewall (allows Docker bridge to access KasmVNC port, blocks public XRDP).

---

## 3. Service Management

```bash
# Check status of KasmVNC and XRDP
bash scripts/status.sh

# Start services
bash scripts/start.sh

# Stop services
bash scripts/stop.sh
```

---

## 4. Nginx HTTPS & Web Access

To expose KasmVNC over HTTPS with your custom domains (`vnc.yourdomain.com`, `desktop.yourdomain.com`):

```bash
cd ../nginx
# Add domain proxy with WebSocket support
bash scripts/site_add.sh --domain vnc.yourdomain.com --upstream host.docker.internal:8444 --websocket
bash scripts/site_add.sh --domain desktop.yourdomain.com --upstream host.docker.internal:8444 --websocket
```

Then open `https://vnc.yourdomain.com` in your web browser and login with your desktop credentials.
