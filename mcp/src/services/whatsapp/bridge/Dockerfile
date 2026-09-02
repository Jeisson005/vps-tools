FROM node:22-slim

WORKDIR /app

# ca-certificates + git (some deps still use git). Baileys >= 7 depends on
# 'libsignal' from npm, so no SSH/git+auth is required to build.
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --no-cache @whiskeysockets/baileys@latest pino

COPY whatsapp-bridge.js /app/whatsapp-bridge.js

EXPOSE 3010

# The provisioner passes --port/--session-dir as extra args; with an ENTRYPOINT
# they are appended to the node command instead of replacing the whole command.
ENTRYPOINT ["node", "whatsapp-bridge.js"]
CMD ["--port", "3010", "--session-dir", "/app/sessions"]
