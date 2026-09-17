# Throwaway login image for NotebookLM — NOT the always-on gateway.
#
# Rationale: the browser is needed exactly once (interactive Google sign-in), so it
# lives in its own image that only the compose profile "login" builds/runs:
#
#   docker compose --profile login build notebooklm-login
#   docker compose --profile login run --rm notebooklm-login
#
# Result: the running mcp-gateway container keeps its lean image and ~15 MB idle RAM;
# Chromium + Xvfb exist only inside this container for the few minutes the login
# takes, then disappear with --rm. The session file lands straight in the shared
# profile on ./data (no export/copy), which is what keeps it valid.
FROM mcp-gateway:latest

ENV DEBIAN_FRONTEND=noninteractive

# Xvfb for a *headful* Chromium on a virtual display (Google blocks headless sign-in),
# plus tools to look at that invisible screen when the flow asks for something a
# script cannot answer (captcha): `xwd`+ImageMagick to grab a PNG of the display and
# send it to the user, `x11vnc` if they would rather watch/type in the window.
RUN apt-get update && apt-get install -y --no-install-recommends \
      xvfb \
      x11-apps \
      x11vnc \
      imagemagick \
      fonts-liberation \
      libnss3 \
      libatk-bridge2.0-0 \
      libgtk-3-0 \
      libgbm1 \
      libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Chromium matching the playwright version pinned by notebooklm-py[browser].
RUN python3 -m playwright install --with-deps chromium

COPY scripts/notebooklm-login.sh /app/scripts/notebooklm-login.sh
RUN chmod +x /app/scripts/notebooklm-login.sh

ENTRYPOINT ["/app/scripts/notebooklm-login.sh"]
