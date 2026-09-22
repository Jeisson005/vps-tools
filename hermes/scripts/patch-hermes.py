#!/usr/bin/env python3
"""
Patch Manager for Hermes Agent in vps-tools.

Applies necessary custom patches to upstream hermes-agent:
1. browser_tool_cdp.py (formerly tools/browser_tool.py): Preserves custom CDP
    ports when discovering remote Steel browser endpoints.
2. scripts/whatsapp-bridge/bridge.js: Sets markOnlineOnConnect=true so Baileys
    reports presence 'available' on connect. Without it Baileys marks every
    inbound with an 'inactive' delivery receipt and WhatsApp never shows the
    sender the 2nd grey tick (nor timely blue ticks). Requires the bot account
    to have a push name set (else Baileys skips presence with 'no name
    present' and receipts stay inactive).
3. scripts/whatsapp-bridge/bridge.js (/read endpoint): Dual-sends read
    receipts to the resolved PN JID. Since WhatsApp's LID migration, inbound
    DMs arrive as 123@lid and the server silently ignores LID-addressed
    read receipts (no blue ticks, no error). The patch resolves the PN via
    the session lid-mapping file (fallback: signalRepository.lidMapping)
    and appends a PN key alongside the original LID key.
4. agent/vault_backends/passbolt.py (new file + 2 anchored edits in base.py):
    Exposes the Passbolt vault (via the local MCP gateway) as a login source
    for the password-blind browser tools (handles ``pb:<uuid>``). No unlock
    needed (gateway holds the session), so it works headless. List results
    are cached in-process; secrets always resolve fresh. See
    hermes/patches/passbolt_backend.py (source of truth).

Validates target signatures before applying and issues explicit warnings if upstream
code has changed.
"""
import sys
import os
import shutil


def patch_browser_tool(base_dir: str) -> bool:
    # Upstream split CDP discovery out of tools/browser_tool.py into
    # tools/browser_tool_cdp.py. Patch whichever file holds the
    # webSocketDebuggerUrl discovery block.
    candidates = [
        os.path.join(base_dir, "tools/browser_tool_cdp.py"),
        os.path.join(base_dir, "tools/browser_tool.py"),
    ]
    path = next((p for p in candidates if os.path.isfile(p)), candidates[0])
    if not os.path.isfile(path):
        print(f"[-] [browser_tool] File not found: {path}")
        return False

    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    if "_cdp_port_preserved" in code or "p_raw.netloc and p_ws.netloc" in code:
        print(f"[+] [browser_tool] CDP port preservation patch already applied ({os.path.basename(path)}).")
        return True

    target = 'ws_url = str(payload.get("webSocketDebuggerUrl") or "").strip()'

    replacement = '''ws_url = str(payload.get("webSocketDebuggerUrl") or "").strip()
    if ws_url:
        try:
            from urllib.parse import urlparse as _cdp_up
            _cdp_raw, _cdp_ws = _cdp_up(discovery_url), _cdp_up(ws_url)
            if _cdp_raw.netloc and _cdp_ws.netloc and ":" in _cdp_raw.netloc and ":" not in _cdp_ws.netloc:
                ws_url = ws_url.replace(f"://{_cdp_ws.netloc}/", f"://{_cdp_raw.netloc}/", 1)
        except Exception:
            pass
    _cdp_port_preserved = True'''

    if target not in code:
        print(f"[!] [WARNING] [browser_tool] Upstream CDP signature changed in {os.path.basename(path)}.")
        return False

    new_code = code.replace(target, replacement, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_code)

    print(f"[+] [browser_tool] CDP port preservation patch applied successfully ({os.path.basename(path)}).")
    return True

def patch_whatsapp_presence(base_dir: str) -> bool:
    path = os.path.join(base_dir, "scripts/whatsapp-bridge/bridge.js")
    if not os.path.isfile(path):
        print(f"[-] [whatsapp-presence] File not found: {path}")
        return False

    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    if "markOnlineOnConnect: true" in code:
        print("[+] [whatsapp-presence] markOnlineOnConnect already enabled.")
        return True

    target = "markOnlineOnConnect: false,"

    replacement = ("markOnlineOnConnect: true, // vps-tools: presence 'available' "
                   "required for active delivery/read receipts (ticks)")

    if target not in code:
        print("[!] [WARNING] [whatsapp-presence] Upstream socket options changed; patch NOT applied.")
        return False

    backup_path = path + ".orig"
    if not os.path.exists(backup_path):
        shutil.copyfile(path, backup_path)

    new_code = code.replace(target, replacement, 1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_code)

    # Fail-closed syntax validation (JS equivalent of AST check): if the
    # edited file no longer parses, restore the backup and report failure.
    import hashlib
    import subprocess
    try:
        subprocess.run(["node", "--check", path], check=True,
                       capture_output=True, timeout=30)
    except Exception as exc:
        shutil.copyfile(backup_path, path)
        print(f"[!] [WARNING] [whatsapp-presence] node --check failed ({exc}); restored backup, patch NOT applied.")
        return False

    digest = hashlib.sha256(new_code.encode("utf-8")).hexdigest()[:16]
    print(f"[+] [whatsapp-presence] markOnlineOnConnect enabled for delivery/read receipts (sha256:{digest}).")
    return True

def install_passbolt_backend(base_dir: str) -> bool:
    """Install the Passbolt vault backend (vps-tools addition).

    Copies hermes/patches/passbolt_backend.py -> agent/vault_backends/passbolt.py
    and registers it in agent/vault_backends/base.py with two anchored edits
    (external_backend_classes + is_enabled). Idempotent; warns (does not force)
    if upstream signatures changed. Validates with ast.parse before writing.
    """
    import ast
    import hashlib

    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "patches", "passbolt_backend.py")
    dest_dir = os.path.join(base_dir, "agent", "vault_backends")
    dest = os.path.join(dest_dir, "passbolt.py")
    base_py = os.path.join(dest_dir, "base.py")

    if not os.path.isfile(src):
        print(f"[-] [passbolt-backend] Source not found: {src}")
        return False
    if not os.path.isfile(base_py):
        print(f"[-] [passbolt-backend] base.py not found: {base_py}")
        return False

    with open(src, "r", encoding="utf-8") as f:
        wanted = f.read()
    try:
        ast.parse(wanted)
    except SyntaxError as exc:
        print(f"[!] [WARNING] [passbolt-backend] Source has syntax errors ({exc}); NOT installed.")
        return False

    current = ""
    if os.path.isfile(dest):
        with open(dest, "r", encoding="utf-8") as f:
            current = f.read()
    if current != wanted:
        with open(dest, "w", encoding="utf-8") as f:
            f.write(wanted)
        digest = hashlib.sha256(wanted.encode("utf-8")).hexdigest()[:16]
        print(f"[+] [passbolt-backend] Installed agent/vault_backends/passbolt.py (sha256:{digest}).")
    else:
        print("[+] [passbolt-backend] agent/vault_backends/passbolt.py already current.")

    with open(base_py, "r", encoding="utf-8") as f:
        code = f.read()
    orig = code

    old_classes = '''def external_backend_classes():
    from agent.vault_backends.bitwarden import BitwardenLoginBackend
    from agent.vault_backends.onepassword import OnePasswordLoginBackend
    return (OnePasswordLoginBackend, BitwardenLoginBackend)'''
    new_classes = '''def external_backend_classes():
    from agent.vault_backends.bitwarden import BitwardenLoginBackend
    from agent.vault_backends.onepassword import OnePasswordLoginBackend
    _classes = [OnePasswordLoginBackend, BitwardenLoginBackend]
    try:
        # vps-tools: Passbolt backend (optional local addition).
        from agent.vault_backends.passbolt import PassboltLoginBackend
        _classes.append(PassboltLoginBackend)
    except Exception:
        pass
    return tuple(_classes)'''
    if "PassboltLoginBackend" not in code:
        if old_classes not in code:
            print("[!] [WARNING] [passbolt-backend] external_backend_classes signature changed; patch NOT applied.")
            return False
        code = code.replace(old_classes, new_classes, 1)

    old_enabled = "    return is_installed(name)"
    new_enabled = '''    if name == "passbolt":
        # vps-tools: enabled when a gateway token is available (no CLI needed).
        try:
            from agent.vault_backends.passbolt import is_configured
            return is_configured()
        except Exception:
            return False
    return is_installed(name)'''
    if "is_configured()" not in code:
        if code.count(old_enabled) != 1:
            print("[!] [WARNING] [passbolt-backend] is_enabled signature changed; patch NOT applied.")
            return False
        code = code.replace(old_enabled, new_enabled, 1)

    if code != orig:
        try:
            ast.parse(code)
        except SyntaxError as exc:
            print(f"[!] [WARNING] [passbolt-backend] Patched base.py fails ast.parse ({exc}); reverted, NOT applied.")
            return False
        with open(base_py, "w", encoding="utf-8") as f:
            f.write(code)
        print("[+] [passbolt-backend] Registered PassboltLoginBackend in base.py.")
    else:
        print("[+] [passbolt-backend] base.py registration already present.")
    return True


def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.hermes/hermes-agent")
    print(f"[*] Checking and applying custom Hermes patches on: {target_dir}")
    ok1 = patch_browser_tool(target_dir)
    ok2 = patch_whatsapp_presence(target_dir)
    ok3 = patch_whatsapp_read_lid_pn(target_dir)
    ok4 = install_passbolt_backend(target_dir)
    if ok1 and ok2 and ok3 and ok4:
        print("[+] All custom patches verified and active.")
    else:
        print("[!] Note: One or more patches could not be auto-applied due to upstream changes.")


def patch_whatsapp_read_lid_pn(base_dir: str) -> bool:
    path = os.path.join(base_dir, "scripts/whatsapp-bridge/bridge.js")
    if not os.path.isfile(path):
        print(f"[-] [whatsapp-read-lid] File not found: {path}")
        return False

    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    if "lid-mapping-${_m[1]}_reverse.json" in code:
        print("[+] [whatsapp-read-lid] LID->PN dual-send already applied.")
        return True

    target = """  try {
    await sock.readMessages(receiptKeys);
    return res.json({ success: true, marked: true });"""

    replacement = """  try {
    // vps-tools: WhatsApp server silently ignores LID-addressed read receipts
    // (no blue ticks, no error). Dual-send: original LID key + resolved PN key.
    try {
      const _lid = String(req.body?.key?.remoteJid || '');
      const _m = _lid.match(/^(\\d+)@lid$/);
      if (_m) {
        let _pn = null;
        try {
          const _f = path.join(SESSION_DIR, `lid-mapping-${_m[1]}_reverse.json`);
          if (existsSync(_f)) _pn = JSON.parse(readFileSync(_f, 'utf8'));
        } catch {}
        if (!_pn) {
          try { _pn = await sock.signalRepository?.lidMapping?.getPNForLID?.(_lid); } catch {}
        }
        if (_pn && !String(_pn).includes('@')) _pn = `${String(_pn).replace(/\\D/g, '')}@s.whatsapp.net`;
        if (_pn && String(_pn).includes('@')) {
          for (const _k of receiptKeys.slice()) {
            receiptKeys.push({ id: _k.id, remoteJid: String(_pn), participant: undefined, fromMe: false });
          }
        }
      }
    } catch {}
    await sock.readMessages(receiptKeys);
    return res.json({ success: true, marked: true });"""

    if target not in code:
        print("[!] [WARNING] [whatsapp-read-lid] Upstream /read block changed; patch NOT applied.")
        return False

    new_code = code.replace(target, replacement, 1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_code)

    import hashlib
    import subprocess
    try:
        subprocess.run(["node", "--check", path], check=True,
                       capture_output=True, timeout=30)
    except Exception as exc:
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"[!] [WARNING] [whatsapp-read-lid] node --check failed ({exc}); reverted, patch NOT applied.")
        return False

    digest = hashlib.sha256(new_code.encode("utf-8")).hexdigest()[:16]
    print(f"[+] [whatsapp-read-lid] LID->PN dual-send applied (sha256:{digest}).")
    return True

if __name__ == "__main__":
    main()
