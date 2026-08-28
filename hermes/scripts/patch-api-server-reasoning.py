#!/usr/bin/env python3
"""
Patch Hermes Agent API Server to route intermediate tool execution text
to OpenAI-compatible reasoning_content for Open WebUI / reasoning-capable clients.
"""
import sys
import os

def patch_api_server(base_dir: str):
    path = os.path.join(base_dir, "gateway/platforms/api_server.py")
    if not os.path.isfile(path):
        print(f"[-] {path} not found.")
        return

    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    if "_pending_iteration_text" in code:
        print("[+] API server already patched with reasoning_content routing.")
        return

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

    if target_on_delta not in code or target_done not in code or target_emit not in code:
        print("[-] Target signatures not matched in api_server.py.")
        return

    new_code = code.replace(target_on_delta, replacement_on_delta, 1)
    new_code = new_code.replace(target_done, replacement_done, 1)
    new_code = new_code.replace(target_emit, replacement_emit, 1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_code)

    print("[+] Successfully patched api_server.py with reasoning_content bridge!")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/home/jeisson/.hermes/hermes-agent"
    patch_api_server(target)
