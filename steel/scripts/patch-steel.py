#!/usr/bin/env python3
"""
Patch Manager for Steel Browser in vps-tools.

Enforces strict session isolation and real 404 responses for nonexistent or
expired sessions in steel-browser container.

Prevents unauthorized access to Chromium DevTools via arbitrary session IDs:
1. sessions.controller.js: Returns 404 when requested sessionId is not live and active.
2. cdp.routes.js: Returns 404 for /devtools/inspector.html when no active session is live.
"""
import sys
import subprocess
import os

CONTAINER_NAME = os.environ.get("STEEL_CONTAINER_NAME", "steel-browser")

def run_in_container(cmd: list) -> subprocess.CompletedProcess:
    full_cmd = ["docker", "exec", CONTAINER_NAME] + cmd
    return subprocess.run(full_cmd, capture_output=True, text=True)

def patch_file_in_container(file_path: str, target: str, replacement: str, name: str) -> bool:
    # Read current content
    res = run_in_container(["cat", file_path])
    if res.returncode != 0:
        print(f"[-] [{name}] Failed to read {file_path} in container {CONTAINER_NAME}")
        return False

    code = res.stdout
    if replacement.strip() in code:
        print(f"[+] [{name}] Patch already applied.")
        return True

    if target not in code:
        print(f"[!] [WARNING] [{name}] Upstream signature not found in {file_path}!")
        print("    Steel Browser code may have been updated upstream.")
        print("    Patch was NOT applied to avoid container corruption.")
        return False

    # Backup original inside container
    backup_path = file_path + ".orig"
    run_in_container(["cp", "-n", file_path, backup_path])

    new_code = code.replace(target, replacement, 1)

    # Write patched code into container
    p = subprocess.Popen(
        ["docker", "exec", "-i", CONTAINER_NAME, "tee", file_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    _, err = p.communicate(input=new_code)
    if p.returncode != 0:
        print(f"[-] [{name}] Failed to write patched code: {err}")
        return False

    print(f"[+] [{name}] Patch successfully applied to {file_path}")
    return True

def main():
    # Verify container is running
    chk = subprocess.run(
        ["docker", "ps", "--filter", f"name=^/{CONTAINER_NAME}$", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    if CONTAINER_NAME not in chk.stdout:
        print(f"[-] Container '{CONTAINER_NAME}' is not running. Please start it first.")
        sys.exit(1)

    print(f"[*] Checking and applying security patches to container: {CONTAINER_NAME}")

    # 1. Patch sessions.controller.js
    ctrl_path = "/app/api/build/modules/sessions/sessions.controller.js"
    target_details = """export const handleGetSessionDetails = async (server, request, reply) => {
    const sessionId = request.params.sessionId;
    if (sessionId !== server.sessionService.activeSession.id) {
        return reply.send({
            id: sessionId,
            createdAt: new Date().toISOString(),
            status: "released",
            duration: 0,
            eventCount: 0,
            timeout: 0,
            creditsUsed: 0,
            websocketUrl: getBaseUrl("ws"),
            debugUrl: getUrl("v1/sessions/debug"),
            debuggerUrl: getUrl("v1/devtools/inspector.html"),
            sessionViewerUrl: getBaseUrl(),
            userAgent: "",
            isSelenium: false,
            proxy: "",
            proxyTxBytes: 0,
            proxyRxBytes: 0,
            solveCaptcha: false,
        });
    }"""

    replacement_details = """export const handleGetSessionDetails = async (server, request, reply) => {
    const sessionId = request.params.sessionId;
    const active = server.sessionService.activeSession;
    if (!active || active.status !== "live" || sessionId !== active.id) {
        return reply.status(404).send({
            statusCode: 404,
            error: "Not Found",
            message: "Session not found or has expired",
        });
    }"""

    ok1 = patch_file_in_container(ctrl_path, target_details, replacement_details, "sessions-details-404")

    target_live = """export const handleGetSessionLiveDetails = async (server, request, reply) => {
    try {"""

    replacement_live = """export const handleGetSessionLiveDetails = async (server, request, reply) => {
    const targetId = request.params.id;
    const active = server.sessionService.activeSession;
    if (!active || active.status !== "live" || (targetId && targetId !== active.id)) {
        return reply.status(404).send({
            statusCode: 404,
            error: "Not Found",
            message: "Session not found or has expired",
        });
    }
    try {"""

    ok2 = patch_file_in_container(ctrl_path, target_live, replacement_live, "sessions-live-404")

    # 2. Patch cdp.routes.js
    cdp_path = "/app/api/build/modules/cdp/cdp.routes.js"
    target_cdp = """    }, async (request, reply) => {
        return reply.redirect(`${server.cdpService.getDebuggerUrl()}?ws=${server.cdpService
            .getDebuggerWsUrl(request.query.pageId)
            .replace("ws:", "")}`);
    });"""

    replacement_cdp = """    }, async (request, reply) => {
        const active = server.sessionService.activeSession;
        if (!active || active.status !== "live") {
            return reply.status(404).send({
                statusCode: 404,
                error: "Not Found",
                message: "No active browser session",
            });
        }
        return reply.redirect(`${server.cdpService.getDebuggerUrl()}?ws=${server.cdpService
            .getDebuggerWsUrl(request.query.pageId)
            .replace("ws:", "")}`);
    });"""

    ok3 = patch_file_in_container(cdp_path, target_cdp, replacement_cdp, "cdp-inspector-404")

    if ok1 and ok2 and ok3:
        print("[+] All Steel security patches verified. Restarting container to apply...")
        subprocess.run(["docker", "restart", CONTAINER_NAME], check=True)
        print("[+] Container steel-browser restarted cleanly with strict 404 session protection.")
    else:
        print("[!] Note: One or more patches could not be auto-applied. Check warnings above.")

if __name__ == "__main__":
    main()
