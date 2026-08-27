---
name: desktop-gui-control
description: "Control the user's active graphical desktop and on-screen applications (X11 / KasmVNC / WireGuard on DISPLAY=:1) via cua-driver and Chrome CDP: mouse, keyboard, windows, desktop apps, and on-screen browser interaction."
version: 3.1.0
author: VPS Tools
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [desktop, gui, vnc, kasmvnc, wireguard, x11, cua-driver, computer-use, mouse, keyboard, screen]
    category: computer-use
    related_skills: [browser-automation]
---

# Desktop GUI & On-Screen Control Skill

Provides complete control over the user's **graphical X11 desktop environment and visible applications** on `DISPLAY=:1` (accessible via KasmVNC or WireGuard VNC).

> [!WARNING]
> **Channel Awareness:** If the user is chatting via **Telegram, Discord, or Web Dashboard**, they are NOT watching the VNC monitor `:1`. 
> - If the user wants to enter credentials, solve 2FA, or log in from Telegram, do **NOT** open Chrome in `:1`. Use **`steel-session create`** in **`browser-automation`** to give them a **Live Viewer web link**.
> - Use this skill **ONLY** when the user explicitly mentions *"en mi escritorio VNC"*, *"en KasmVNC"*, *"en mi pantalla visible"*, or asks to control local desktop GUI applications (e.g. terminals, text editors, file managers).

---

## 🎯 When to Use This Skill

- The user explicitly says *"controla mi pantalla / en mi VNC / en mi escritorio gráfico"*.
- The user asks to open or interact with desktop GUI applications (GIMP, LibreOffice, text editors, XFCE desktop).
- The user asks to see actions on their visible VNC screen in real time.

---

## 🖥️ Architecture & Capabilities

Driven on `DISPLAY=:1` via `cua-driver`:

```bash
export DISPLAY=:1
```

### 1. Session Verification & Screenshots
```bash
# Verify X11 desktop is active
xdpyinfo >/dev/null 2>&1 && echo "Desktop alive"

# Capture the desktop screen state
cua-driver call get_desktop_state | jq -r .base64_image | base64 -d > /tmp/screen.png
vision_analyze image=/tmp/screen.png
```

### 2. Mouse & Keystrokes
```bash
cua-driver call mouse_click x=500 y=300 button=left
cua-driver call type_text text="echo 'Hello World'"
cua-driver call key_press key="Return"
```

### 3. On-Screen Browser inside VNC
When the user explicitly asks for a browser inside their VNC monitor:
```bash
export DISPLAY=:1
google-chrome --remote-debugging-port=9222 --user-data-dir=~/.config/google-chrome-vnc "https://example.com"
```
