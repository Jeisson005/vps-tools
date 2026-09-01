# 🖥️ RustDesk Self-Hosted Remote Desktop Server & Web Client

Fully autonomous self-hosted **RustDesk Server** (`hbbs` + `hbbr`) and official containerized **Web Client** (`desk.jeisson.top`) for secure, low-latency, end-to-end encrypted remote desktop access.

---

## 🎯 Architecture & Ports

RustDesk requires the following ports open on your firewall (`ufw`):
* `21115/tcp`: NAT type test
* `21116/tcp`: TCP hole-punching / ID registration
* `21116/udp`: UDP heartbeat / peer discovery
* `21117/tcp`: Encrypted relay service
* `21118/tcp`: Web client WebSocket (hbbs)
* `21119/tcp`: Web client WebSocket (hbbr)

```bash
# Allow in UFW Firewall:
sudo ufw allow 21115:21119/tcp comment "RustDesk Server TCP (hbbs/hbbr)"
sudo ufw allow 21116/udp comment "RustDesk Server UDP (hbbs discovery)"
sudo ufw reload
```

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
