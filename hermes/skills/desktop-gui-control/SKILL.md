---
name: desktop-gui-control
description: "Control the user's active graphical desktop and on-screen applications (X11 / KasmVNC / WireGuard on DISPLAY=:1) via cua-driver and Chrome CDP: mouse, keyboard, windows, desktop apps, and on-screen browser interaction."
version: 3.0.0
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

Provides complete, authoritative control over the user's **real graphical X11 desktop environment and visible applications** (running on `DISPLAY=:1`, accessible via KasmVNC at `https://desktop.your-domain.com` or via direct VNC client over WireGuard VPN at `10.x.x.x:5901`).

> **Note on Web Automation:** For background/isolated web scraping, headless tasks, or persistent web browsing outside the user's graphical screen, use the **`browser-automation`** skill. Use this skill ONLY when the user wants actions performed directly on their visible desktop screen.

---

## 🎯 When to Use This Skill

- The user says *"controla mi equipo / mi pantalla / mi escritorio / en mi VNC"*.
- The user asks to open or interact with desktop applications (terminals, text editors, IDEs, file managers, local GUI apps).
- The user says *"abre el navegador en mi escritorio para que yo lo vea aquí"*.

---

## 🖥️ Architecture & Capabilities

Whether accessed via **KasmVNC** (web) or **native VNC over WireGuard**, the environment is the **same Linux X11 desktop on `DISPLAY=:1`**.

You can drive the session on two complementary levels:

### 🪟 Level 1: Desktop OS & Application Control (`cua-driver`)

Always export the display before executing desktop commands:
```bash
export DISPLAY=:1
```

#### 1. Session Verification & Screenshots
```bash
# Verify X11 desktop is active
xdpyinfo >/dev/null 2>&1 && echo "Desktop alive"

# Capture the desktop screen state
cua-driver call get_desktop_state | jq -r .base64_image | base64 -d > /tmp/screen.png
vision_analyze image=/tmp/screen.png
```

#### 2. Mouse & Keystrokes
```bash
# Single click at coordinates
cua-driver call mouse_click x=500 y=300 button=left

# Double click (e.g. to open an icon)
cua-driver call mouse_double_click x=500 y=300 button=left

# Typing text
cua-driver call type_text text="echo 'Hello World'"
cua-driver call key_press key="Return"

# Keyboard shortcuts (Linux idiomatic)
cua-driver call key_down key="Control_L"
cua-driver call key_press key="c"
cua-driver call key_up key="Control_L"
```

#### 3. Drag & Drop & Scrolling
```bash
# Drag and drop between coordinates
cua-driver call drag start_x=100 start_y=200 end_x=400 end_y=500

# Scroll viewport down / up
cua-driver call scroll direction="down" amount=5
```

---

### 🌐 Level 2: On-Screen Visible Browser (Google Chrome in X11)

When the user wants to see a browser running inside their graphical desktop monitor:

```bash
export DISPLAY=:1

# 1. Launch Chrome visible on the desktop with remote debugging enabled
google-chrome --remote-debugging-port=9222 --user-data-dir=~/.config/google-chrome-vnc "https://example.com" &

# 2. Drive the visible browser via CDP or cua-driver
# You can interact via DOM inspection or direct clicks while the user watches in real-time.
```

---

## 🛡️ Operational & Safety Rules

1. **Never kill or restart the X11 server:** Do not terminate the user's active desktop session on `:1`.
2. **Never type secrets automatically:** Do not type passwords, bank PINs, or sensitive credentials without explicit user request.
3. **Report actions clearly:** Always inform the user what actions were executed on their desktop.
