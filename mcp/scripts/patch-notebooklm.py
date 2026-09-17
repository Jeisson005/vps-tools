#!/usr/bin/env python3
"""
Patch Manager for notebooklm-py inside the MCP gateway container (vps-tools).

Same contract as ``hermes/scripts/patch-hermes.py``: signature-validated,
idempotent, fail-closed (backup + revert if the edited file no longer compiles),
and it never hard-fails the caller — it prints ``[!] WARNING`` when upstream
drifted so an image rebuild can still come up.

Patch list
----------
1. ``_web/transport/streaming_post.py`` — bounded TAIL buffer for the streamed
   chat body (``VPS_CHAT_TAIL_BYTES``).

   Why: Google repeats the *whole* cumulative payload (answer + grounding /
   citation text) in every frame of the streamed chat response. Measured on a
   88-source notebook: one exhaustive question produced a **238 MB** raw body
   for a ~10 KB answer, with a marker string repeated 1574x. The library buffered
   that whole body (cap = 256 MiB for chat), rebuilt an httpx.Response from it
   and then decoded every frame into Python objects: peak RSS 1.5-3.1 GB.

   Only the chat path raises the cap above ``MAX_RPC_RESPONSE_BYTES`` (50 MiB),
   so that is the discriminator: when the caller raises the cap we keep a rolling
   line-aligned tail instead of the whole body, while still enforcing the real
   total-byte cap. The parser takes the answer from the *last* marked chunk
   (``isFinalResponse``) and terminal frames arrive at the end of the stream, so a
   tail window preserves the semantics (verify with the same question before and
   after: identical answer + references, RSS down by ~10x).
"""
from __future__ import annotations

import os
import py_compile
import shutil
import sys
import tempfile

MARKER = "VPS_CHAT_TAIL_BYTES"
TARGET_REL = os.path.join("_web", "transport", "streaming_post.py")

SIG_OLD = """        buffer = bytearray()
        async for chunk in response.aiter_bytes():
            buffer.extend(chunk)
            if len(buffer) > max_bytes:
                raise RPCResponseTooLargeError(
                    f"RPC response exceeded {max_bytes} bytes "
                    f"(read {len(buffer)} bytes before aborting)",
                    limit_bytes=max_bytes,
                    bytes_read=len(buffer),
                )"""

SIG_NEW = '''        buffer = bytearray()
        # --- vps-tools patch: bounded tail buffer for chat streams ---------
        # Google re-sends the full cumulative payload (answer + grounding) in
        # every frame, so a chat body can reach ~250 MB for a ~10 KB answer.
        # Only the chat path raises the cap above MAX_RPC_RESPONSE_BYTES, so use
        # that as the discriminator and keep just the last VPS_CHAT_TAIL_BYTES
        # of the body. The parser reads the answer from the last marked chunk
        # and the terminal frames close the stream, so the tail carries
        # everything downstream needs. The real cap still applies to the total.
        _vps_tail = None
        if max_bytes > MAX_RPC_RESPONSE_BYTES:
            _vps_tail = VPS_CHAT_TAIL_BYTES
        _vps_total = 0
        async for chunk in response.aiter_bytes():
            _vps_total += len(chunk)
            if _vps_total > max_bytes:
                raise RPCResponseTooLargeError(
                    f"RPC response exceeded {max_bytes} bytes "
                    f"(read {_vps_total} bytes before aborting)",
                    limit_bytes=max_bytes,
                    bytes_read=_vps_total,
                )
            buffer.extend(chunk)
            if _vps_tail is not None and len(buffer) > _vps_tail:
                del buffer[: len(buffer) - _vps_tail]
        if _vps_tail is not None and _vps_total > _vps_tail:
            # Drop the partially-kept first line so the parser starts on a
            # complete frame (``)]}\'`` anti-XSSI prefix is already consumed).
            _vps_cut = buffer.find(b"\\n")
            if _vps_cut != -1:
                del buffer[: _vps_cut + 1]'''

CONST_ANCHOR = "MAX_RPC_RESPONSE_BYTES = 50 * 1024 * 1024"
CONST_NEW = """MAX_RPC_RESPONSE_BYTES = 50 * 1024 * 1024

#: vps-tools patch: how much of a streamed chat body to keep (tail window).
VPS_CHAT_TAIL_BYTES = 16 * 1024 * 1024"""


def _site_packages() -> str | None:
    try:
        import notebooklm  # noqa: PLC0415

        return os.path.dirname(os.path.abspath(notebooklm.__file__))
    except Exception:
        return None


def patch_chat_tail_buffer(base_dir: str) -> bool:
    path = os.path.join(base_dir, TARGET_REL)
    if not os.path.isfile(path):
        print(f"[-] [chat-tail] File not found: {path}")
        return False

    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    if MARKER in code:
        print("[+] [chat-tail] Tail-buffer patch already applied.")
        return True

    if SIG_OLD not in code or CONST_ANCHOR not in code:
        print("[!] [WARNING] [chat-tail] Upstream streaming_post.py signature changed; patch NOT applied.")
        return False

    new_code = code.replace(CONST_ANCHOR, CONST_NEW, 1).replace(SIG_OLD, SIG_NEW, 1)

    backup = shutil.copyfile(path, tempfile.mktemp(prefix="streaming_post.", suffix=".bak"))
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_code)

    try:
        py_compile.compile(path, doraise=True)
    except Exception as exc:  # pragma: no cover - fail closed
        shutil.copyfile(backup, path)
        print(f"[!] [WARNING] [chat-tail] py_compile failed ({exc}); reverted, patch NOT applied.")
        return False

    import hashlib

    digest = hashlib.sha256(new_code.encode("utf-8")).hexdigest()[:16]
    print(f"[+] [chat-tail] Bounded chat tail buffer applied (sha256:{digest}).")
    return True


def main() -> int:
    base = None
    for i, a in enumerate(sys.argv[1:]):
        if a == "--path" and i + 2 <= len(sys.argv[1:]):
            base = sys.argv[i + 2]
    base = base or os.environ.get("NOTEBOOKLM_PKG_PATH") or _site_packages()
    if not base or not os.path.isdir(base):
        print("[-] notebooklm package not found (not installed here); nothing to patch.")
        return 0
    print(f"[*] Applying vps-tools patches to notebooklm-py at: {base}")
    if patch_chat_tail_buffer(base):
        print("[+] All notebooklm patches verified and active.")
    else:
        print("[!] Note: notebooklm patch could not be auto-applied due to upstream changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
