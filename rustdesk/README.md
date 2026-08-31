# 🖥️ RustDesk Self-Hosted Remote Desktop Server & Web Client

Fully autonomous self-hosted **RustDesk Server** (`hbbs` + `hbbr`) and official containerized **Web Client** (`desk.jeisson.top`) for secure, low-latency, end-to-end encrypted remote desktop access.

---

## 🎯 Architecture & Components

1. **`hbbs` (ID & Rendezvous Server):**
   * Handles peer discovery, TCP hole-punching, authentication, and heartbeats.
   * Ports: `21115/tcp` (NAT test), `21116/tcp` + `21116/udp` (Signaling & ID registration), `21118/tcp` (WebSocket).
2. **`hbbr` (Relay Server):**
   * Encrypted relay server for peer connections when direct P2P connection cannot be established.
   * Ports: `21117/tcp` (Relay stream), `21119/tcp` (Relay WebSocket).
3. **`rustdesk-web` (Self-Hosted Web Client):**
   * Browser-accessible remote control interface on `https://desk.jeisson.top`.
   * Directly connects to controlled endpoints with audio, clipboard, and full display support.

---

## 🚀 Quick Setup

### 1. Configure Environment
```bash
cp .env.example .env
chmod 600 .env
nano .env
```
Ensure you define your domains:
* `RUSTDESK_DOMAIN=rustdesk.jeisson.top`
* `RUSTDESK_WEB_DOMAIN=desk.jeisson.top`
* `RUSTDESK_WEB_USER=jeisson`
* `RUSTDESK_WEB_PASSWORD=YourSecurePassword`

### 2. Start Services
```bash
./scripts/start.sh
```

### 3. Retrieve Server Public Key
```bash
./scripts/status.sh
# Output will display: 🔑 Server Public Key: <PUB_KEY>
```

---

## 💻 Client Configuration

In your desktop/mobile RustDesk application:
1. Open **Settings** → **Network** / **ID/Relay Server**.
2. Set:
   * **ID Server:** `rustdesk.jeisson.top`
   * **Relay Server:** `rustdesk.jeisson.top`
   * **Key:** `<YOUR_PUBLIC_KEY>`
3. Connect!
