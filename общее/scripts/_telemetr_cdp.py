# -*- coding: utf-8 -*-
"""Connect to Edge CDP, open telemetr TG Ads, try export/scrape."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "tgads-snapshots"
IMPORTS = ROOT / "imports"
SNAP.mkdir(exist_ok=True)
IMPORTS.mkdir(exist_ok=True)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = None
        for pg in context.pages:
            if "telemetr" in (pg.url or ""):
                page = pg
                break
        if page is None:
            page = context.new_page()
            page.goto("https://telemetr.me/tgads", wait_until="domcontentloaded", timeout=90000)
        else:
            page.bring_to_front()
        time.sleep(5)
        print("URL", page.url, flush=True)
        print("TITLE", page.title(), flush=True)
        body = page.inner_text("body")
        print("BODY_LEN", len(body), flush=True)
        print("BODY", body[:2500].replace("\n", " | "), flush=True)
        page.screenshot(path=str(SNAP / "telemetr_tgads_cdp.png"))
        (SNAP / "telemetr_tgads_cdp.html").write_text(page.content(), encoding="utf-8")

        logged_in = not re.search(r"вход|логин|login|регистрац|sign in", body, re.I) or (
            "каталог" in body.lower() or "tgads" in body.lower() or "креатив" in body.lower()
        )
        print("guess_logged_in", logged_in, flush=True)

        # Collect card-like texts
        cards = page.evaluate(
            """() => {
              const nodes = Array.from(document.querySelectorAll('[class*="card"],[class*="ad"],[class*="creative"],article,tr'));
              return nodes.slice(0, 40).map(n => (n.innerText||'').trim().slice(0, 400)).filter(Boolean);
            }"""
        )
        print("CARDS", len(cards), flush=True)
        for c in cards[:8]:
            print("---", c[:200].replace("\n", " / "), flush=True)

        # Look for API responses in performance — listen briefly
        captured = []

        def on_response(resp):
            try:
                url = resp.url
                if "telemetr" in url and any(x in url for x in ("api", "tgads", "ads", "search", "export", "csv")):
                    captured.append({"url": url, "status": resp.status})
            except Exception:
                pass

        page.on("response", on_response)

        # Try typing vpn in any visible input
        inputs = page.locator("input:visible")
        print("visible inputs", inputs.count(), flush=True)
        if inputs.count():
            try:
                inputs.first.click()
                inputs.first.fill("vpn")
                page.keyboard.press("Enter")
                time.sleep(5)
            except Exception as exc:
                print("fill fail", exc, flush=True)

        for label in ["Бот", "Экспорт", "CSV", "Поиск", "Применить", "Найти"]:
            loc = page.get_by_role("button", name=re.compile(label, re.I))
            if loc.count() == 0:
                loc = page.get_by_text(label, exact=False)
            print(f"label {label}: {loc.count()}", flush=True)

        print("captured urls", captured[:20], flush=True)
        body2 = page.inner_text("body")
        (SNAP / "telemetr_tgads_cdp_after.html").write_text(page.content(), encoding="utf-8")
        print("AFTER", body2[:2000].replace("\n", " | "), flush=True)
        # don't close browser — user may login
        print("DONE leave edge open", flush=True)


if __name__ == "__main__":
    main()
