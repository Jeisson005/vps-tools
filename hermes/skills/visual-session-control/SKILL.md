---
name: visual-session-control
description: "Control the user's active graphical desktop and visible browser (X11 / VNC / KasmVNC / WireGuard on DISPLAY=:1) via cua-driver and Chrome CDP: mouse, keyboard, window management, and on-screen browser interaction."
version: 2.1.0
author: VPS Tools
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [desktop, vnc, kasmvnc, wireguard, x11, cua-driver, chrome-cdp, computer-use]
    category: computer-use
    related_skills: [steel-browser, computer-use]
---

# Visual Session Control Skill (User Desktop & On-Screen Browser)

Controls the user's **real graphical X11 desktop session and visible browser** (running on `DISPLAY=:1`, reachable via KasmVNC at `https://desktop.jeisson.top` or via direct VNC client over WireGuard VPN at `10.x.x.x:5901`).

---

## 🎯 When to Use This Skill

Use this skill whenever the user wants actions performed **directly on their visible screen**:
1. *"Controla mi equipo / mi pantalla / mi escritorio / en mi VNC"*.
2. *"Abre el navegador en mi escritorio para que yo lo vea aquí"*.
3. Interacting with local desktop applications (terminals, text editors, file managers, local GUI apps).

> **Note on Web Automation:** For background/isolated web scraping, automated testing, or persistent headless browsing outside the user's graphical screen, use the **`steel-browser`** skill instead.

---

## 🖥️ How It Works (Protocol Agnostic)

Whether the user connects through **KasmVNC** (web browser) or a **native VNC client over WireGuard** (TigerVNC, RealVNC, Remmina), the underlying graphical environment is the **same Linux X11 server on `DISPLAY=:1`**.

You can interact with the user's visual session on two levels:

### Level 1: Desktop OS & Window Control (cua-driver)
Control any desktop window, move the mouse, click, drag, and send keystrokes:

```bash
export DISPLAY=:1

# 1. Verify the X11 session is active
xdpyinfo >/dev/null 2>&1 && echo "Desktop alive"

# 2. Capture and inspect desktop screenshot
cua-driver call get_desktop_state | jq -r .base64_image | base64 -d > /tmp/screen.png
vision_analyze image=/tmp/screen.png

# 3. Mouse and keyboard interactions
cua-driver call mouse_click x=500 y=300 button=left
cua-driver call type_text text="Hello World"
cua-driver call key_press key="Return"
```

### Level 2: On-Screen Visible Browser Control (Google Chrome in X11)
Launch or attach to Google Chrome displayed directly on the user's monitor:

```bash
export DISPLAY=:1

# 1. Launch Chrome visible on the user's screen with CDP debugging enabled
google-chrome --remote-debugging-port=9222 --user-data-dir=~/.config/google-chrome-vnc "https://example.com" &

# 2. Drive the visible browser via CDP / Playwright or cua-driver
# You can interact via DOM inspection or direct visual clicks while the user watches in real-time.
```

---

## 🛡️ Guidelines
- **Preserve User Session:** Never kill or restart the user's X11/VNC display server (`:1`).
- **Confirmation:** Always report actions performed on the user's screen so they can track what was done.
