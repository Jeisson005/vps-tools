---
name: visual-session-control
description: "Control the user's real graphical desktop session (KasmVNC / X11 on DISPLAY=:1) via cua-driver: mouse, keyboard, windows, and desktop applications."
version: 2.0.0
author: VPS Tools
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [desktop, kasmvnc, gui, x11, cua-driver, computer-use]
    category: computer-use
    related_skills: [steel-browser, computer-use]
---

# Visual Session Control Skill (User Desktop GUI)

Controls the user's **real graphical desktop session** (KasmVNC on `DISPLAY=:1`, accessible via `https://desktop.jeisson.top` / `https://vnc.jeisson.top`).

> **Note on Web Browsing:** For isolated scraping, testing, or headless/persistent web automation, use the **`steel-browser`** skill. Use this skill ONLY when the user wants actions performed directly on their visible desktop screen.

## When to Use

- The user says *"controla mi equipo / mi pantalla / mi escritorio / en mi VNC"*.
- You need to interact with graphical desktop applications (file managers, terminals, desktop IDEs, local GUI apps).
- The user wants you to perform visible actions on their active monitor screen.

## Prerequisites

- Active KasmVNC / X11 desktop session running on `DISPLAY=:1`.
- `cua-driver` installed at `/home/jeisson/.local/bin/cua-driver`.

## How to Drive the User Desktop

Always export the user's active display before executing commands:

```bash
# 1. Verify the user's live desktop session is running
export DISPLAY=:1
xdpyinfo >/dev/null 2>&1 && echo "Desktop session alive"

# 2. Capture screenshot of the user's monitor
cua-driver call get_desktop_state | jq -r .base64_image | base64 -d > /tmp/screen.png
vision_analyze image=/tmp/screen.png

# 3. Perform mouse / keyboard actions
cua-driver call mouse_click x=500 y=300 button=left
cua-driver call key_press key="Return"
cua-driver call type_text text="Hello World"
```

## Guidelines

- Never kill or reset the user's X11 desktop session.
- Report all actions clearly to the user after interacting with their screen.
