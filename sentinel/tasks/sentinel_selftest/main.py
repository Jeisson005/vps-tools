#!/usr/bin/env python3
"""
Autoprueba diaria del motor Sentinel (sentinel_selftest).

Verifica de punta a punta, con la configuracion VIVA de Hermes:
  1. hermes_config      .env + config.yaml legibles y completos
  2. models_endpoint    GET {base_url}/models con catalogo no vacio
  3. chat_e2e           POST {base_url}/chat/completions responde OK
  4. classifier_referee referee IA del clasificador devuelve categoria valida
  5. healer_e2e         opencode headless (provider dedicado sentinel-hermes,
                        servidor privado) responde OK
  6. telegram_urgent    bot rojo responde getMe (no envia mensajes)
  7. cron_wiring        tarea registrada en sentinel.tab y sincronizada
  8. sentinel_api       GET /health del API local responde 200
  9. disk               uso de disco raiz < 95%

Exito: exit 0 sin notificar. Fallo: notifica por bot urgente (rojo) y exit 1.
NUNCA imprime secretos.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SENTINEL_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SENTINEL_DIR))

from core.hermes_ai import (
    check_models,
    chat_complete,
    describe,
    get_llm_config,
    redact,
    run_opencode,
)

CHECKS = []  # (name, ok, detail)


def check(name):
    def deco(fn):
        try:
            detail = fn() or "OK"
            CHECKS.append((name, True, str(detail)[:300]))
        except Exception as e:  # noqa: BLE001
            CHECKS.append((name, False, redact(e, 300)))
    return deco


@check("hermes_config")
def _c1():
    c = get_llm_config()
    assert len(c["api_key"]) > 20, "api_key ausente o muy corta"
    assert c["base_url"].startswith("http"), "base_url invalido"
    assert c["model"], "model ausente"
    return "OK (%s)" % describe()


@check("models_endpoint")
def _c2():
    models = check_models(timeout=20)
    assert models, "catalogo vacio"
    return "OK (%d modelos)" % len(models)


@check("chat_e2e")
def _c3():
    # El modelo vivo de Hermes puede ser de razonamiento (reasoning): parte del
    # presupuesto de max_tokens se consume en tokens de pensamiento ANTES de
    # emitir `content`. Un max_tokens pequeno deja la respuesta vacia de forma
    # intermitente (finish_reason="length"), asi que usamos un presupuesto
    # holgado y reintentamos con timeout creciente ante fallos transitorios.
    last = "sin respuesta"
    for attempt, (mt, tout) in enumerate(((256, 60), (512, 90)), 1):
        try:
            t = chat_complete("Responde unicamente con la palabra OK", max_tokens=mt, timeout=tout)
            if "ok" in t.lower():
                return "OK (respuesta=%s)" % redact(t, 20)
            last = "respuesta inesperada: %s" % redact(t, 100)
        except Exception as e:  # noqa: BLE001
            last = redact(e, 200)
        if attempt < 2:
            import time

            time.sleep(3)
    raise AssertionError(last)


@check("classifier_referee")
def _c4():
    from core.classifier import ErrorCategory, _ai_referee

    r = _ai_referee(
        1,
        "Traceback (most recent call last): ZeroDivisionError: division by zero",
        "",
        {"task_name": "sentinel_selftest", "description": "smoke", "language": "python",
         "requires_browser": False},
    )
    assert isinstance(r, dict), "referee sin respuesta"
    allowed = {c.value for c in ErrorCategory}
    assert str(r.get("category", "")) in allowed or getattr(r.get("category"), "value", "") in allowed, \
        "categoria invalida"
    src = r.get("source", "?")
    return "OK (categoria=%s fuente=%s)" % (getattr(r.get("category"), "value", r.get("category")), src)


@check("healer_e2e")
def _c5():
    with tempfile.TemporaryDirectory(prefix="sentinel_selftest_") as tmp:
        r = run_opencode(
            "Responde unicamente con la palabra OK",
            cwd=Path(tmp),
            timeout=150,
        )
    assert r.get("ok"), "opencode fallo rc=%s: %s" % (
        r.get("returncode"), redact(r.get("stderr") or r.get("stdout"), 200))
    assert "ok" in (r.get("stdout") or "").lower(), "respuesta inesperada"
    return "OK (%s)" % redact(r.get("model_ref"), 80)


@check("telegram_urgent")
def _c6():
    from core.config import settings

    token = (settings.BOT_URGENT_TOKEN or "").strip()
    assert token, "BOT_URGENT_TOKEN ausente"
    url = "https://api.telegram.org/bot%s/getMe" % token
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=15) as res:
        body = json.loads(res.read().decode("utf-8", errors="replace"))
    assert body.get("ok"), "getMe no ok"
    return "OK (bot=@%s)" % (body.get("result", {}).get("username", "?"))


@check("cron_wiring")
def _c7():
    tab = SENTINEL_DIR / "cron" / "sentinel.tab"
    assert tab.is_file(), "sentinel.tab ausente"
    content = tab.read_text(encoding="utf-8", errors="ignore")
    assert "sentinel_selftest" in content, "tarea no registrada en sentinel.tab"
    try:
        proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0 and "SENTINEL ISOLATED MANAGED CRONTAB" in proc.stdout, \
            "bloque Sentinel no sincronizado en crontab"
    except FileNotFoundError:
        return "OK (tab registrado; crontab no disponible aqui)"
    return "OK (tab + crontab sincronizados)"


@check("sentinel_api")
def _c8():
    from core.config import settings

    url = "http://127.0.0.1:%s/health" % int(settings.SENTINEL_PORT)
    with urllib.request.urlopen(url, timeout=10) as res:
        assert res.status == 200, "HTTP %s" % res.status
    return "OK (%s)" % url


@check("disk")
def _c9():
    usage = shutil.disk_usage("/")
    pct = round(usage.used / usage.total * 100, 1)
    assert pct < 95, "disco al %s%%" % pct
    return "OK (uso %s%%)" % pct


def main() -> int:
    print("== Autoprueba Sentinel ==")
    for name, ok, detail in CHECKS:
        print("[%s] %s: %s" % ("OK " if ok else "FAIL", name, detail))
    failed = [n for n, ok, _ in CHECKS if not ok]
    if not failed:
        print("== Resultado: TODO OK (%d/%d) ==" % (len(CHECKS), len(CHECKS)))
        return 0
    try:
        from core.telegram_hub import TelegramHub

        lines = "\n".join("• `%s`: %s" % (n, d) for n, ok, d in CHECKS if not ok)
        TelegramHub.send_urgent(
            "🛡️ *Autoprueba Diaria Sentinel: FALLOS*\n\n"
            "Fallaron %d de %d comprobaciones:\n%s\n\n"
            "Revisa el log de la tarea `sentinel_selftest`." % (len(failed), len(CHECKS), lines)
        )
    except Exception as e:  # noqa: BLE001
        print("Aviso: no se pudo notificar por Telegram: %s" % redact(e, 200))
    print("== Resultado: FALLO (%s) ==" % ", ".join(failed))
    return 1


if __name__ == "__main__":
    sys.exit(main())
