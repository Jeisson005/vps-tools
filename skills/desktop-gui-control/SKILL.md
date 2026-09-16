---
name: desktop-gui-control
description: "Control graphical desktop sessions (X11 / KasmVNC / RDP) via cua-driver and Chrome CDP: session discovery, mouse, keyboard, windows, desktop apps, and on-screen browser interaction. Defaults to DISPLAY=:1, attachable to any active session."
version: 3.3.0
author: VPS Tools
license: MIT
platforms: [linux]
metadata:
  tags: [desktop, gui, vnc, kasmvnc, xrdp, rdp, x11, cua-driver, computer-use, mouse, keyboard, screen]
  category: computer-use
  related_skills: [browser-automation]
---

# Desktop GUI & On-Screen Control Skill

Provides control over **graphical X11 desktop sessions and visible applications** via `cua-driver`. Default workspace is `DISPLAY=:1` (KasmVNC web desktop); can attach to **any active local session** (e.g. RDP logins on `:10+`).

> [!WARNING]
> **Channel Awareness:** If the user is chatting via **Telegram, Discord, Web Chat, or CLI terminal**, they are NOT necessarily watching `:1`.
> - If the user wants to enter credentials, solve 2FA, or log in through a web page, do **NOT** open Chrome on the desktop. Use **`steel-session create`** in **`browser-automation`** to give them a **Live Viewer web link**.
> - Use this skill **ONLY** when the user explicitly mentions *"en mi escritorio / VNC / RDP"*, *"en mi pantalla visible"*, or asks to control local desktop GUI applications (e.g. terminals, text editors, file managers).
> - **Shared-session fights:** when attached to a session the user is actively watching (their RDP display), you share ONE mouse/keyboard. Move deliberately, announce takeovers, and prefer `:1` for autonomous background work.

---

## 🎯 When to Use This Skill

- The user explicitly says *"controla mi pantalla / en mi VNC / en mi RDP / en mi escritorio gráfico"*.
- The user asks to open or interact with desktop GUI applications (GIMP, LibreOffice, text editors, XFCE desktop).
- The user asks to see actions on a visible screen in real time.

---

## 🖥️ 0. Session Discovery & Selection

```bash
# List active local X displays (X1 -> :1, X10 -> :10, ...)
ls /tmp/.X11-unix/

# Who owns each display
ps aux | grep -E "Xvnc|Xorg" | grep -v grep
loginctl list-sessions 2>/dev/null || true
```

| Display | Origin | Visible at |
| :--- | :--- | :--- |
| `:1` | KasmVNC (agent home workspace) | KasmVNC web (`vnc.yourdomain.com`) |
| `:10+` | xrdp RDP logins (one per connection) | User's RDP client (Remmina, Windows App) |

```bash
# Attach to the target session (default :1)
export DISPLAY=:1            # agent workspace (KasmVNC web)
# export DISPLAY=:10         # user's RDP session (discover first)
export XAUTHORITY=~/.Xauthority
xdpyinfo >/dev/null 2>&1 && echo "attached to $DISPLAY"
```

Rules:
- Default to `:1` unless the user says *"mi sesión"*, *"donde estoy trabajando"*, *"mi RDP"* — then discover and attach.
- Always announce which display you are driving (e.g. *"tomo control de tu sesión RDP :10"*).
- All commands below use `$DISPLAY` — never hardcode `:1` in new work.

---

## 🖥️ Architecture & Capabilities

Driven on `$DISPLAY` via `cua-driver`:

```bash
export DISPLAY=${DISPLAY:-:1}
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

### 3. On-Screen Browser inside the attached session
When the user explicitly asks for a browser inside their visible session:
```bash
export DISPLAY=${DISPLAY:-:1}
google-chrome --remote-debugging-port=9222 --user-data-dir=~/.config/google-chrome-vnc "https://example.com"
```
