# Security Audits (monthly)

Two-layer monthly security audit (runs day 1, 3:00 AM):

1. **Programmatic layer** (`scripts/security_scan.sh`): deterministic, read-only.
   Trivy CVE scan of running images + repo, Gitleaks over git history,
   exposure diff vs `baseline/ports.allow`, TLS expiry, privileged containers.
   Output: `reports/YYYY-MM/`.
2. **Agent layer** (`agent/run_audit.sh`): runs opencode headless (`--auto`,
   read-only prompt in `agent/PROMPT.md`, same model as the MCP `principal`
   account). Verifies findings via OSV/NVD + vendor advisories, judges
   exposure, and SENDS the Telegram verdict itself (routine one-liner if all
   clear, routine list if suggestions, urgent if something is exposed now).

## Contents

- `scripts/install.sh`: installs Trivy + Gitleaks (run once).
- `scripts/security_scan.sh [YYYY-MM]`: layer 1, exit 0 always.
- `scripts/check_exposure.sh <baseline> <out>`: standalone exposure audit.
- `scripts/monthly_audit.sh`: orchestrator (scan -> agent), called by cron.
- `agent/PROMPT.md`: versioned audit procedure (placeholders rendered by runner).
- `agent/run_audit.sh [YYYY-MM]`: layer 2 runner.
- `baseline/ports.allow`: expected listening sockets (public/local/review).
- `baseline/accepted-risks.md`: known trade-offs (not failures).
- `baseline/*.example`: templates for LOCAL overrides (see below).
- `reports/`: monthly artifacts (gitignored, `.gitkeep` only).
- `.env.example`: `AUDIT_MODEL` (must track MCP principal), timeouts.

## Local overrides (gitignored, never committed)

`baseline/local/` holds operator-specific tweaks. Copy the `.example`
templates there:

| File | Effect |
|---|---|
| `local/.trivyignore` | CVE suppressions, passed as trivy `--ignorefile` |
| `local/agent-notes.local.md` | Appended to the agent prompt (wins on conflict) |
| `local/ports.allow` | Extra allow entries for the exposure diff |

Use for: confirmed false positives, temp ports, personal context the repo
must not contain.

## Manual run

```bash
./scripts/install.sh            # once
./scripts/security_scan.sh      # layer 1 only
./agent/run_audit.sh            # layer 2 only (needs layer 1 report)
./scripts/monthly_audit.sh      # both, like cron does
```
