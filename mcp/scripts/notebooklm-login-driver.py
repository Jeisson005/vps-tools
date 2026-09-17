#!/usr/bin/env python3
"""Drive the Google login for NotebookLM inside the login container.

Why this exists in addition to `notebooklm login`: that command opens Chromium and
waits for a *human at the machine*. In a headless container nobody is there, so this
driver does the two scriptable steps (email, password) itself, hands over to the human
only where Google demands it (phone tap / captcha / unusual-activity check), and then
saves the session the same way the CLI does — into the shared profile, no copies.

Env:
  LOGIN_EMAIL       Google account email (not a secret)
  LOGIN_PW_FILE     file holding the password (never passed via argv)
  NOTEBOOKLM_PROFILE / MCP_DATA_DIR   where the profile lives (shared volume)
  DISPLAY           X display for the headful Chromium (Xvfb)
  LOGIN_2FA_WAIT    seconds to wait for the human to approve the prompt (default 900)
  LOGIN_CAPTCHA_FILE  optional file the operator writes the captcha text into
"""
from __future__ import annotations

import os
import sys
import time

from playwright.sync_api import sync_playwright
from urllib.parse import urlparse


def host_of(url: str) -> str:
    """Host of a URL — 'notebook.google.com' also shows up inside Google's redirect
    query string, so substring checks on the whole URL are wrong (they reported a
    successful login while still sitting on the password challenge)."""
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


APP_HOSTS = ("notebook.google.com", "notebooklm.google.com")

EMAIL = os.environ.get("LOGIN_EMAIL", "")
PW_FILE = os.environ.get("LOGIN_PW_FILE", "/tmp/login_pw")
PROFILE = os.environ.get("NOTEBOOKLM_PROFILE", "personal")
DATA_DIR = os.environ.get("MCP_DATA_DIR", "/app/data")
PROFILE_DIR = os.path.join(DATA_DIR, "notebooklm", "profiles", PROFILE)
BROWSER_DIR = os.path.join(PROFILE_DIR, "browser_profile")
STATE_PATH = os.path.join(PROFILE_DIR, "storage_state.json")
SHOT_DIR = os.path.join(DATA_DIR, "login-shots")
LOG = os.path.join(SHOT_DIR, "driver.log")
WAIT_2FA = int(os.environ.get("LOGIN_2FA_WAIT", "900"))
CAPTCHA_FILE = os.environ.get("LOGIN_CAPTCHA_FILE", os.path.join(SHOT_DIR, "captcha.txt"))
TARGET = "https://notebook.google.com/"


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(SHOT_DIR, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def shot(page, name: str) -> None:
    try:
        os.makedirs(SHOT_DIR, exist_ok=True)
        page.screenshot(path=os.path.join(SHOT_DIR, name), timeout=15000)
    except Exception as exc:
        log(f"shot {name} failed: {exc}")


def visible(page, selector: str) -> bool:
    try:
        return page.locator(selector).first.is_visible(timeout=1500)
    except Exception:
        return False


def main() -> int:
    os.makedirs(PROFILE_DIR, exist_ok=True)
    os.makedirs(SHOT_DIR, exist_ok=True)
    try:
        os.chmod(PROFILE_DIR, 0o700)
    except Exception:
        pass
    pw = ""
    try:
        with open(PW_FILE, "r", encoding="utf-8") as fh:
            pw = fh.read().strip()
    except Exception:
        log(f"no password file at {PW_FILE} (a signed-in chooser may still work)")
    log("driver start: profile=%s dir=%s email=%s pw=%s" % (PROFILE, PROFILE_DIR, EMAIL, "yes" if pw else "NO"))

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            BROWSER_DIR,
            headless=False,
            viewport={"width": 1440, "height": 900},
            args=["--no-first-run", "--no-default-browser-check", "--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(TARGET, wait_until="domcontentloaded", timeout=90000)
        time.sleep(5)
        log(f"url after goto: {page.url}")
        shot(page, "driver-00-start.png")

        # --- email step -------------------------------------------------------
        if "accounts.google.com" in page.url:
            if visible(page, "#identifierId"):
                page.fill("#identifierId", EMAIL)
                page.click("#identifierNext")
                time.sleep(4)
                log(f"after EMAIL: {page.url}")
                shot(page, "driver-01-after-email.png")

        # --- captcha (appears inline as input#ca, not in an iframe) ------------
        if visible(page, "#ca"):
            log("CAPTCHA_PRESENT: escribe el texto en " + CAPTCHA_FILE)
            shot(page, "driver-02-captcha.png")
            deadline = time.time() + 600
            while time.time() < deadline and not os.path.exists(CAPTCHA_FILE):
                time.sleep(3)
            if os.path.exists(CAPTCHA_FILE):
                with open(CAPTCHA_FILE, "r", encoding="utf-8") as fh:
                    code = fh.read().strip()
                os.unlink(CAPTCHA_FILE)
                page.fill("#ca", code)
                page.keyboard.press("Enter")
                time.sleep(5)
                log(f"captcha enviado; url={page.url}")
                shot(page, "driver-03-after-captcha.png")

        # --- password step ----------------------------------------------------
        if visible(page, 'input[type="password"]'):
            if not pw:
                log("ABORT: no hay contraseña disponible (LOGIN_PW_FILE vacío o ausente)")
                shot(page, "driver-07-no-password.png")
                ctx.close()
                return 3
            page.fill('input[type="password"]', pw)
            page.click("#passwordNext")
            time.sleep(6)
            log(f"after PASSWORD: {page.url}")
            shot(page, "driver-04-after-password.png")

        # --- wait for human (2FA push) or for the app to load -----------------
        deadline = time.time() + WAIT_2FA
        announced = False
        while time.time() < deadline:
            url = page.url
            if host_of(url) in APP_HOSTS:
                break
            if "challenge/dp" in url or "challenge/ipp" in url or "challenge/totp" in url:
                if not announced:
                    log("NEEDS_2FA: aprueba la notificación en el teléfono (o el código)")
                    announced = True
                if visible(page, "#ca"):
                    shot(page, "driver-05-captcha-2fa.png")
            time.sleep(3)
        log(f"final url: {page.url}")
        shot(page, "driver-09-final.png")

        if host_of(page.url) not in APP_HOSTS:
            log("LOGIN_INCOMPLETE: seguimos en " + host_of(page.url) + urlparse(page.url).path)
            shot(page, "driver-08-incomplete.png")
            ctx.close()
            return 2

        # Give the app a moment to settle cookies, then save the session exactly
        # where the gateway client expects it (the CLI owns this file).
        page.goto("https://notebooklm.google.com/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(6)
        state = ctx.storage_state()
        import json

        os.makedirs(PROFILE_DIR, exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        os.chmod(STATE_PATH, 0o600)
        names = {c.get("name") for c in state.get("cookies", [])}
        log(f"STATE_SAVED {STATE_PATH} cookies={len(state.get('cookies', []))} "
            f"SID={'SID' in names} 1PSID={'__Secure-1PSID' in names} 1PSIDTS={'__Secure-1PSIDTS' in names}")
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
