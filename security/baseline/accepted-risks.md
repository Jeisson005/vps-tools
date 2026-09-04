# Accepted risks - Known exposures/design trade-offs, reviewed periodically.
# The audit agent must still mention these briefly, but they are NOT failures.

1. **Steel Browser runs Chromium with `--no-sandbox` + `SYS_ADMIN`** (steel/docker-compose.yml).
   Required for headless automation in Docker. Mitigated by: isolated containers,
   2G memory cap, localhost-only API, ephemeral sessions. If Steel adds userns
   support, drop this exception.
2. **RustDesk protocol ports (21115-21119) are public.** Required for remote
   desktop connectivity. Mitigated by: key-pinned self-hosted server, fail2ban.
3. **`opencode run --auto` is used ONLY by security/agent/run_audit.sh**, scoped
   `--dir security/` with a read-only prompt (only curl to api.telegram.org
   allowed as a side effect). No other automation uses --auto.
4. **Trivy/Gitleaks findings on `latest`/`main` tags**: version drift is reported,
   not auto-upgraded. Patching is always manual.
5. **Docker bypasses UFW (DOCKER-USER chain empty, confirmed 2026-09).**
   Any `0.0.0.0`-published container port is internet-reachable regardless of
   UFW default-deny. Standing rule until fixed: NO sensitive port may be
   published to 0.0.0.0 (agent verifies 3159/30101 auth every audit). Proper
   fixes (pick one): populate DOCKER-USER with drop rules, or rebind
   sensitive publishes to 127.0.0.1.
