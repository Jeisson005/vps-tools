#!/usr/bin/env python3
"""
Patch Manager for Hermes Agent in vps-tools.

Applies necessary custom patches to upstream hermes-agent:
1. api_server.py: Routes intermediate tool execution narration to OpenAI-compatible
   `reasoning_content` so Open WebUI cleanly nests it in the "Thinking" dropdown.
2. browser_tool.py: Preserves custom CDP port when discovering remote Steel browser WebSocket URLs.

Validates target signatures before applying and issues explicit warnings if upstream
code has changed.
"""
import sys
import os
import shutil

def patch_api_server(base_dir: str) -> bool:
    path = os.path.join(base_dir, "gateway/platforms/api_server.py")
    if not os.path.isfile(path):
        print(f"[-] [api_server] File not found: {path}")
        return False

    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    if "_pending_iteration_text" in code and "__thought__" in code:
        print("[+] [api_server] Patch already applied.")
        return True

    # Backup original
    backup_path = path + ".orig"
    if not os.path.exists(backup_path):
        shutil.copyfile(path, backup_path)

    target_on_delta = """            def _on_delta(delta):
                # Filter out None — the agent fires stream_delta_callback(None)
                # to signal the CLI display to close its response box before
                # tool execution, but the SSE writer uses None as end-of-stream
                # sentinel.  Forwarding it would prematurely close the HTTP
                # response, causing Open WebUI (and similar frontends) to miss
                # the final answer after tool calls.  The SSE loop detects
                # completion via agent_task.done() instead.
                # Called from the worker thread running run_conversation —
                # put_threadsafe (not put_nowait) is required here.
                if delta is not None:
                    _stream_q.put_threadsafe(delta)"""

    replacement_on_delta = """            _pending_iteration_text = []

            def _on_delta(delta):
                if delta is not None:
                    _pending_iteration_text.append(delta)
                else:
                    if _pending_iteration_text:
                        thought = "".join(_pending_iteration_text).strip()
                        _pending_iteration_text.clear()
                        if thought:
                            _stream_q.put_threadsafe(("__thought__", thought + "\\n\\n"))"""

    target_done = """            # Ensure SSE drain loops can terminate without relying on polling
            # agent_task.done(), which can race with queue timeout checks.
            agent_task.add_done_callback(lambda _fut: _stream_q.put_nowait(None))"""

    replacement_done = """            def _on_agent_done(fut):
                try:
                    res, _ = fut.result()
                    final_resp = res.get("response") if isinstance(res, dict) else ""
                except Exception:
                    final_resp = ""

                if _pending_iteration_text:
                    final_text = "".join(_pending_iteration_text)
                    _pending_iteration_text.clear()
                else:
                    final_text = final_resp

                if final_text:
                    _stream_q.put_threadsafe(final_text)
                _stream_q.put_threadsafe(None)

            agent_task.add_done_callback(_on_agent_done)"""

    target_emit = """                if isinstance(item, tuple) and len(item) == 2 and item[0] == "__tool_progress__":
                    await response.write(_sse_frame(item[1], event="hermes.tool.progress"))
                else:"""

    replacement_emit = """                if isinstance(item, tuple) and len(item) == 2 and item[0] == "__tool_progress__":
                    await response.write(_sse_frame(item[1], event="hermes.tool.progress"))
                elif isinstance(item, tuple) and len(item) == 2 and item[0] == "__thought__":
                    thought_chunk = {
                        "id": completion_id, "object": "chat.completion.chunk",
                        "created": created, "model": model,
                        "choices": [{"index": 0, "delta": {"reasoning_content": item[1]}, "finish_reason": None}],
                    }
                    await response.write(_sse_frame(thought_chunk))
                else:"""

    missing = []
    if target_on_delta not in code:
        missing.append("target_on_delta")
    if target_done not in code:
        missing.append("target_done")
    if target_emit not in code:
        missing.append("target_emit")

    if missing:
        print(f"[!] [WARNING] [api_server] Upstream code has changed! Cannot find signatures: {', '.join(missing)}")
        print("    The patch was NOT applied to avoid breaking Hermes.")
        print("    Hermes will continue to work with upstream's native stream behavior.")
        return False

    new_code = code.replace(target_on_delta, replacement_on_delta, 1)
    new_code = new_code.replace(target_done, replacement_done, 1)
    new_code = new_code.replace(target_emit, replacement_emit, 1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_code)

    print("[+] [api_server] Reasoning content patch applied successfully.")
    return True

def patch_browser_tool(base_dir: str) -> bool:
    path = os.path.join(base_dir, "tools/browser_tool.py")
    if not os.path.isfile(path):
        print(f"[-] [browser_tool] File not found: {path}")
        return False

    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    if "p_raw.netloc and p_ws.netloc" in code:
        print("[+] [browser_tool] CDP port preservation patch already applied.")
        return True

    target = """    ws_url = str(payload.get("webSocketDebuggerUrl") or "").strip()
    if ws_url:
        logger.info("""

    replacement = """    ws_url = str(payload.get("webSocketDebuggerUrl") or "").strip()
    if ws_url:
        from urllib.parse import urlparse
        p_raw = urlparse(discovery_url)
        p_ws = urlparse(ws_url)
        if p_raw.netloc and p_ws.netloc and ":" in p_raw.netloc and ":" not in p_ws.netloc:
            ws_url = ws_url.replace(f"://{p_ws.netloc}/", f"://{p_raw.netloc}/", 1)
        logger.info("""

    if target not in code:
        print("[!] [WARNING] [browser_tool] Upstream CDP signature changed in browser_tool.py.")
        return False

    new_code = code.replace(target, replacement, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_code)

    print("[+] [browser_tool] CDP port preservation patch applied successfully.")
    return True

def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.hermes/hermes-agent")
    print(f"[*] Checking and applying custom Hermes patches on: {target_dir}")
    ok1 = patch_api_server(target_dir)
    ok2 = patch_browser_tool(target_dir)
    if ok1 and ok2:
        print("[+] All custom patches verified and active.")
    else:
        print("[!] Note: One or more patches could not be auto-applied due to upstream changes.")

if __name__ == "__main__":
    main()
