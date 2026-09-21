# -*- coding: utf-8 -*-
"""Open telemetr.me/tgads using Edge cookies (readonly copy) + Playwright."""
from __future__ import annotations

import json
import shutil
import sqlite3
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "tgads-snapshots"
IMPORTS = ROOT / "imports"
SNAP.mkdir(exist_ok=True)
IMPORTS.mkdir(exist_ok=True)

EDGE_COOKIES = (
    Path.home()
    / "AppData/Local/Microsoft/Edge/User Data/Default/Network/Cookies"
)
EDGE_COOKIES_LEGACY = (
    Path.home() / "AppData/Local/Microsoft/Edge/User Data/Default/Cookies"
)


def copy_cookies_db() -> Path:
    src = EDGE_COOKIES if EDGE_COOKIES.exists() else EDGE_COOKIES_LEGACY
    if not src.exists():
        raise SystemExit(f"no Edge cookies at {src}")
    dst = SNAP / "_edge_cookies.db"
    # SQLite backup works even when file is locked by Edge
    src_uri = f"file:{src.as_posix()}?mode=ro"
    src_conn = sqlite3.connect(src_uri, uri=True, timeout=30)
    dst_conn = sqlite3.connect(dst)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    return dst


def load_telemetr_cookies(db: Path) -> list[dict]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly, samesite "
        "FROM cookies WHERE host_key LIKE '%telemetr%' OR host_key LIKE '%.telemetr.me%'"
    )
    rows = cur.fetchall()
    conn.close()
    cookies = []
    for r in rows:
        host = r["host_key"]
        # Chromium expires_utc is microseconds since 1601
        expires = None
        if r["expires_utc"] and r["expires_utc"] > 0:
            expires = int(r["expires_utc"] / 1_000_000 - 11644473600)
        same = {0: "None", 1: "Lax", 2: "Strict"}.get(r["samesite"] or 0, "Lax")
        cookies.append(
            {
                "name": r["name"],
                "value": r["value"],
                "domain": host,
                "path": r["path"] or "/",
                "expires": expires or -1,
                "httpOnly": bool(r["is_httponly"]),
                "secure": bool(r["is_secure"]),
                "sameSite": same if same != "None" else "None",
            }
        )
    return cookies


def main() -> None:
    db = copy_cookies_db()
    cookies = load_telemetr_cookies(db)
    print(f"telemetr cookies: {len(cookies)}", flush=True)
    for c in cookies[:15]:
        print(f"  {c['domain']} {c['name']}={c['value'][:24]}...", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        if cookies:
            # Playwright rejects sameSite None sometimes — normalize
            clean = []
            for c in cookies:
                item = dict(c)
                if item.get("sameSite") not in ("Strict", "Lax", "None"):
                    item["sameSite"] = "Lax"
                if item.get("expires", -1) <= 0:
                    item.pop("expires", None)
                clean.append(item)
            try:
                context.add_cookies(clean)
            except Exception as exc:
                print(f"add_cookies warn: {exc}", flush=True)
                # try without sameSite
                for c in clean:
                    c.pop("sameSite", None)
                context.add_cookies(clean)

        page = context.new_page()
        page.goto("https://telemetr.me/tgads", wait_until="domcontentloaded", timeout=90000)
        time.sleep(6)
        print("URL", page.url, flush=True)
        print("TITLE", page.title(), flush=True)
        body = page.inner_text("body")
        print("BODY", body[:2000].replace("\n", " | "), flush=True)
        (SNAP / "telemetr_tgads.png").write_bytes(page.screenshot(full_page=False))
        (SNAP / "telemetr_tgads.html").write_text(page.content(), encoding="utf-8")

        # Try VPN search UI
        for sel in [
            'input[type="search"]',
            'input[placeholder*="оиск"]',
            'input[placeholder*="Search"]',
            'input[name="q"]',
            "input.form-control",
        ]:
            loc = page.locator(sel)
            if loc.count():
                print(f"found input {sel}", flush=True)
                loc.first.fill("vpn")
                page.keyboard.press("Enter")
                time.sleep(4)
                break

        # Click filters mentioning bot / VPN if present
        for label in ["Бот", "бот", "Bot", "VPN", "Экспорт", "Export", "CSV"]:
            loc = page.get_by_text(label, exact=False)
            if loc.count():
                print(f"seen text: {label} x{loc.count()}", flush=True)

        body2 = page.inner_text("body")
        (SNAP / "telemetr_tgads_after.html").write_text(page.content(), encoding="utf-8")
        print("AFTER", body2[:2000].replace("\n", " | "), flush=True)

        # Capture network JSON if any XHR
        # Export click
        export = page.get_by_text("Экспорт", exact=False)
        if export.count():
            with page.expect_download(timeout=15000) as dl_info:
                export.first.click()
            download = dl_info.value
            target = IMPORTS / f"telemetr_tgads_{download.suggested_filename}"
            download.save_as(target)
            print(f"downloaded {target}", flush=True)

        browser.close()


if __name__ == "__main__":
    main()
