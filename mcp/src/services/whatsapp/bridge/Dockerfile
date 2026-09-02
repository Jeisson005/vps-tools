FROM node:22-slim

WORKDIR /app

# Baileys + pino for the bridge
RUN npm install @whiskeysockets/baileys@^6 pino

COPY whatsapp-bridge.js /app/whatsapp-bridge.js

EXPOSE 3010

# Port and session dir are provided at runtime via args/env.
CMD ["node", "whatsapp-bridge.js", "--port", "3010", "--session-dir", "/app/sessions"]
