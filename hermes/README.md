# Hermes Agent (Nous Research)

Open-source autonomous AI agent by Nous Research designed for terminal-native workflows with persistent memory, tool calling, and multi-model support.

---

## 1. Quick Installation

1. Copy `.env.example` to `.env` (optional customizations):
```bash
cd vps-tools/hermes
cp .env.example .env
```

2. Run automated installer:
```bash
sudo bash scripts/install.sh
```

---

## 2. Usage & Configuration

```bash
# Run interactive setup wizard (connect API keys & models)
hermes setup

# Start interactive agent session in terminal
hermes chat

# Check agent status / diagnostics
hermes doctor
```

---

## 3. Status Verification

```bash
bash scripts/status.sh
```
