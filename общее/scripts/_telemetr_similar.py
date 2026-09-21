# -*- coding: utf-8 -*-
"""Scrape technoinsider profile + similar channels from telemetr.me via Edge cookies."""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "tgads-snapshots"
SNAP.mkdir(exist_ok=True)

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
    # Edge may store encrypted_value; plain value often empty
    cols = [r[1] for r in conn.execute("PRAGMA table_info(cookies)").fetchall()]
    print("cookie columns:", cols, flush=True)
    value_expr = "value"
    if "encrypted_value" in cols:
        # we'll still pull value; encrypted needs DPAPI
        pass
    cur = conn.execute(
        "SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly, samesite "
        "FROM cookies WHERE host_key LIKE '%telemetr%' OR host_key LIKE '%.telemetr.me%'"
    )
    rows = cur.fetchall()
    conn.close()
    cookies = []
    for r in rows:
        host = r["host_key"]
        expires = None
        if r["expires_utc"] and r["expires_utc"] > 0:
            expires = int(r["expires_utc"] / 1_000_000 - 11644473600)
        same = {0: "None", 1: "Lax", 2: "Strict"}.get(r["samesite"] or 0, "Lax")
        val = r["value"] or ""
        cookies.append(
            {
                "name": r["name"],
                "value": val,
                "domain": host,
                "path": r["path"] or "/",
                "expires": expires or -1,
                "httpOnly": bool(r["is_httponly"]),
                "secure": bool(r["is_secure"]),
                "sameSite": same if same != "None" else "None",
            }
        )
    nonempty = sum(1 for c in cookies if c["value"])
    print(f"telemetr cookies: {len(cookies)}, nonempty value: {nonempty}", flush=True)
    return cookies


def extract_stats(text: str) -> dict:
    out = {}
    patterns = {
        "subscribers": r"Подписчики.*?Всего\s*([\d\s\u00a0]+)",
        "views_per_post": r"Просмотров на пост.*?Всего\s*([\d\s\u00a0]+)",
        "er_total": r"ER\s*Общий\s*([\d.,]+)\s*%",
        "er_daily": r"Суточный\s*([\d.,]+)\s*%",
    }
    for k, p in patterns.items():
        m = re.search(p, text, re.S | re.I)
        if m:
            out[k] = m.group(1).strip()
    return out


def main() -> None:
    db = copy_cookies_db()
    cookies = load_telemetr_cookies(db)

    with sync_playwright() as p:
        # Prefer CDP if Edge debug port is up
        browser = None
        context = None
        used_cdp = False
        try:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            used_cdp = True
            print("connected via CDP", flush=True)
        except Exception as exc:
            print(f"CDP unavailable ({exc}), launching Edge with cookies", flush=True)
            browser = p.chromium.launch(channel="msedge", headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            if cookies:
                clean = []
                for c in cookies:
                    if not c["value"]:
                        continue
                    item = dict(c)
                    if item.get("sameSite") not in ("Strict", "Lax", "None"):
                        item["sameSite"] = "Lax"
                    if item.get("expires", -1) <= 0:
                        item.pop("expires", None)
                    clean.append(item)
                print(f"adding {len(clean)} cookies", flush=True)
                try:
                    context.add_cookies(clean)
                except Exception as e:
                    print("add_cookies:", e, flush=True)

        page = context.new_page()
        api_hits = []

        def on_response(resp):
            try:
                url = resp.url
                if "telemetr" in url and any(
                    x in url for x in ("api", "similar", "похож", "channel", "search", "catalog", "recommend")
                ):
                    api_hits.append({"url": url, "status": resp.status})
            except Exception:
                pass

        page.on("response", on_response)

        # 1) Channel page
        page.goto(
            "https://telemetr.me/content/technoinsider",
            wait_until="domcontentloaded",
            timeout=90000,
        )
        time.sleep(5)
        body = page.inner_text("body")
        print("URL", page.url, flush=True)
        print("TITLE", page.title(), flush=True)
        print("STATS", extract_stats(body), flush=True)
        print("BODY_HEAD", body[:2500].replace("\n", " | "), flush=True)
        page.screenshot(path=str(SNAP / "telemetr_technoinsider.png"), full_page=False)
        (SNAP / "telemetr_technoinsider.html").write_text(page.content(), encoding="utf-8")

        # Look for similar / related sections
        for label in [
            "Похожие",
            "похожие",
            "Рекоменд",
            "Кросс",
            "Пересечен",
            "Аудитор",
            "Полная статистика",
        ]:
            loc = page.get_by_text(label, exact=False)
            print(f"label '{label}': {loc.count()}", flush=True)

        # Click full stats if present
        full = page.get_by_text("Полная статистика", exact=False)
        if full.count():
            try:
                full.first.click()
                time.sleep(4)
                print("opened full stats", page.url, flush=True)
                body2 = page.inner_text("body")
                print("FULL_STATS", extract_stats(body2), flush=True)
                print("FULL_HEAD", body2[:3000].replace("\n", " | "), flush=True)
                page.screenshot(path=str(SNAP / "telemetr_technoinsider_full.png"))
                (SNAP / "telemetr_technoinsider_full.html").write_text(
                    page.content(), encoding="utf-8"
                )
            except Exception as e:
                print("full stats click fail", e, flush=True)

        # Try similar channels URLs
        candidates = [
            "https://telemetr.me/content/technoinsider/similar",
            "https://telemetr.me/content/technoinsider/channels",
            "https://telemetr.me/content/technoinsider/cross",
            "https://telemetr.me/catalog?category=Технологии",
            "https://telemetr.me/catalog?category=%D0%A2%D0%B5%D1%85%D0%BD%D0%BE%D0%BB%D0%BE%D0%B3%D0%B8%D0%B8",
            "https://telemetr.me/search?q=technoinsider",
        ]
        for url in candidates:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(3)
                t = page.inner_text("body")
                print(f"\n=== {url} ===", flush=True)
                print("title", page.title(), "len", len(t), flush=True)
                print(t[:1800].replace("\n", " | "), flush=True)
                slug = url.rstrip("/").split("/")[-1][:40]
                page.screenshot(path=str(SNAP / f"telemetr_try_{slug}.png"))
            except Exception as e:
                print(f"fail {url}: {e}", flush=True)

        print("API_HITS", json.dumps(api_hits[:40], ensure_ascii=False), flush=True)

        # User info from page JS
        try:
            user = page.evaluate("() => window.user || null")
            print("window.user", user, flush=True)
        except Exception as e:
            print("user eval", e, flush=True)

        if not used_cdp:
            browser.close()
        else:
            print("leaving CDP browser open", flush=True)


if __name__ == "__main__":
    main()
