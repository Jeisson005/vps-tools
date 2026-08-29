Machine is a Linux VPS with Steel Browser (API on port 3000 / browser.jeisson.top) and an optional X11 graphical desktop on DISPLAY=:1 (KasmVNC / WireGuard). For web automation (scraping, testing, logins, 2FA/Captchas), use skill "browser-automation" (steel-session / Playwright connectOverCDP). For on-screen desktop/browser control, use skill "desktop-gui-control" (DISPLAY=:1).
§
On this VPS, OpenCode and Hermes use the Steel Browser sandbox via dynamic sessions. OpenCode uses Playwright MCP (steel-mcp with --isolated for ephemeral or --persistent for persistent) and Hermes always uses persistent sessions via steel-session create. Persistent profile data (cookies and storage) is safely synced in ~/.config/steel/profiles/persistent/context.json.
§
Host has `claude` CLI and `agy` (Gemini CLI) at ~/.local/bin. Hermes timezone = America/Bogota (UTC-5); cron scheduler anchors 5-field expressions to this zone.
§
Image generation is NOT set up on this machine: CPU-only (no GPU), no ComfyUI/diffusion installed, no image API key. Real generation requires a cloud provider (FAL.ai recommended, or OpenAI gpt-image-1 / Comfy Cloud) plus a provider API key.
§
STT/voice: user is Colombian and sends voice notes in Spanish; wants transcription accurate in Spanish. Currently local faster-whisper "base" with auto-detect language (stt.language=""), weak on Spanish/PT — user open to upgrading (Groq free tier, OpenAI whisper-1) for quality.
§
User is technical/curious — asks deep "how does X work" questions (MCP ownership, browser/extension isolation, config internals) and tests agent capabilities. Values honest "I don't know" over fabricated answers.
§
Steel browser topology (this VPS): All browser interactions go through Steel API on port 3000 (browser.jeisson.top) creating dynamic, isolated Chromium sessions with unique UUIDs. Never use a shared static port. Hermes creates sessions with `steel-session create "<url>"`, which preloads persistent logins by default and outputs liveViewerUrl (for human-in-the-loop / 2FA) and cdpWsUrl. Drive the session with Playwright connectOverCDP. To persist newly acquired logins/cookies, run `steel-session sync <sessionId>` or `steel-session release <sessionId>`. Each chat or concurrent task receives its own isolated session without collision.
