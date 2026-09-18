#!/usr/bin/env python3
"""
Patch: Edge TTS Spanish voices (vps-tools).

Upstream hermes-webui assumes Chinese/English voices in two places:

1. api/routes.py — the /api/tts Edge voice allowlist only accepts
   zh/en/fr/id voices. Any other voice (including the server-configured
   es-MX-DaliaNeural from ~/.hermes/config.yaml tts.edge) is rejected
   with 400 "invalid voice".
2. static/panels.js — the Settings voice dropdown (_populateTtsVoices)
   only lists those same voices, defaulting to Xiaoxiao (Chinese). Saving
   Settings with engine=edge therefore persists tts_voice:'' and the
   server falls back to Xiaoxiao for every later request.

This patch adds Spanish neural voices idempotently in both places:
  es-MX-DaliaNeural, es-MX-JorgeNeural,
  es-ES-ElviraNeural, es-ES-AlvaroNeural,
  es-CO-GonzaloNeural, es-CO-SalomeNeural

Idempotent: safe to re-run. Validates the upstream anchors before
applying and emits an explicit [!] [WARNING] if upstream changed the
code instead of forcing a broken patch (same contract as
hermes/scripts/patch-hermes.py).

Usage: sudo -u <user> python3 scripts/patch-tts-voices.py [WEBUI_SRC]
Default WEBUI_SRC: ~/hermes-webui
"""
import os
import sys

VOICES = [
    '"es-MX-DaliaNeural"',
    '"es-MX-JorgeNeural"',
    '"es-ES-ElviraNeural"',
    '"es-ES-AlvaroNeural"',
    '"es-CO-GonzaloNeural"',
    '"es-CO-SalomeNeural"',
]

# Upstream anchor: the last line of the hardcoded set before closing brace.
ANCHOR = '"id-ID-GadisNeural",'


def patch_routes(src_dir: str) -> bool:
    path = os.path.join(src_dir, "api", "routes.py")
    if not os.path.isfile(path):
        print(f"[-] [tts-voices] File not found: {path}")
        return False
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    if '"es-MX-DaliaNeural"' in code:
        print("[+] [tts-voices] Spanish Edge voices already allowlisted.")
        return True

    if ANCHOR not in code:
        print("[!] [WARNING] [tts-voices] Upstream anchor not found "
              f"({ANCHOR!r} missing in api/routes.py). "
              "Upstream may have reworked the Edge TTS allowlist — "
              "patch NOT applied, fix scripts/patch-tts-voices.py.")
        return False

    addition = ANCHOR + "\n" + "\n".join(f"        {v}," for v in VOICES)
    code = code.replace(ANCHOR, addition, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print("[+] [tts-voices] Spanish Edge voices allowlisted: " +
          ", ".join(v.strip('"') for v in VOICES))
    return True


PANELS_ANCHOR = "{value:'id-ID-GadisNeural',label:'Gadis (Indonesian, Female)'},"

PANELS_VOICES = [
    "{value:'es-MX-DaliaNeural',label:'Dalia (Spanish MX, Female)'}",
    "{value:'es-MX-JorgeNeural',label:'Jorge (Spanish MX, Male)'}",
    "{value:'es-ES-ElviraNeural',label:'Elvira (Spanish ES, Female)'}",
    "{value:'es-ES-AlvaroNeural',label:'Alvaro (Spanish ES, Male)'}",
    "{value:'es-CO-GonzaloNeural',label:'Gonzalo (Spanish CO, Male)'}",
    "{value:'es-CO-SalomeNeural',label:'Salome (Spanish CO, Female)'}",
]


def patch_panels(src_dir: str) -> bool:
    path = os.path.join(src_dir, "static", "panels.js")
    if not os.path.isfile(path):
        print(f"[-] [tts-voices] File not found: {path}")
        return False
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    if "es-MX-DaliaNeural" in code:
        print("[+] [tts-voices] Spanish Edge voices already in Settings dropdown.")
        return True

    if PANELS_ANCHOR not in code:
        print("[!] [WARNING] [tts-voices] Upstream anchor not found "
              "in static/panels.js (_populateTtsVoices edgeVoices). "
              "Upstream may have reworked the voice dropdown — "
              "patch NOT applied, fix scripts/patch-tts-voices.py.")
        return False

    addition = PANELS_ANCHOR + "\n" + "\n".join(
        f"          {v}," for v in PANELS_VOICES)
    code = code.replace(PANELS_ANCHOR, addition, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print("[+] [tts-voices] Spanish Edge voices added to Settings dropdown.")
    return True


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/hermes-webui")
    ok_routes = patch_routes(src)
    ok_panels = patch_panels(src)
    return 0 if (ok_routes and ok_panels) else 1


if __name__ == "__main__":
    sys.exit(main())
