# -*- coding: utf-8 -*-
"""Via Edge CDP: profile technoinsider + similar channels on telemetr.me."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "tgads-snapshots"
OUT = ROOT / "imports"
SNAP.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)


def dump(page, name: str) -> str:
    body = page.inner_text("body")
    page.screenshot(path=str(SNAP / f"{name}.png"), full_page=False)
    (SNAP / f"{name}.html").write_text(page.content(), encoding="utf-8")
    (SNAP / f"{name}.txt").write_text(body, encoding="utf-8")
    return body


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        page = None
        for pg in context.pages:
            if "telemetr" in (pg.url or ""):
                page = pg
                break
        if page is None:
            page = context.new_page()

        api_payloads = []

        def on_response(resp):
            try:
                url = resp.url
                if "telemetr" not in url:
                    return
                if any(
                    x in url
                    for x in (
                        "similar",
                        "audience",
                        "channels",
                        "stat",
                        "api",
                        "catalog",
                        "search",
                    )
                ):
                    item = {"url": url, "status": resp.status}
                    try:
                        if "json" in (resp.headers.get("content-type") or ""):
                            item["json"] = resp.json()
                    except Exception:
                        pass
                    api_payloads.append(item)
            except Exception:
                pass

        page.on("response", on_response)

        # --- Channel page ---
        page.goto(
            "https://telemetr.me/content/technoinsider",
            wait_until="domcontentloaded",
            timeout=120000,
        )
        time.sleep(5)
        body = dump(page, "ti_home")
        print("URL", page.url, flush=True)
        print("TITLE", page.title(), flush=True)
        logged = "Зарегистрироваться" not in body[:3000] or "Мои каналы" in body
        # Better: window.user
        try:
            user = page.evaluate("() => window.user || null")
            print("USER", json.dumps(user, ensure_ascii=False)[:500], flush=True)
        except Exception as e:
            print("USER_ERR", e, flush=True)
        print("BODY_HEAD", body[:2000].encode("ascii", "replace").decode(), flush=True)

        # Click full stats
        for label in ["Полная статистика", "Статистика", "Аудитория", "Похожие"]:
            loc = page.get_by_text(label, exact=False)
            print(f"seen '{label}': {loc.count()}", flush=True)

        full = page.locator("a,button,span,div").filter(has_text=re.compile(r"Полная статистика"))
        if full.count():
            try:
                full.first.click(timeout=5000)
                time.sleep(5)
                dump(page, "ti_full_stats")
                print("FULL_URL", page.url, flush=True)
            except Exception as e:
                print("full click", e, flush=True)

        # Direct similar / audience URLs
        for path in [
            "/content/technoinsider/stat",
            "/content/technoinsider/audience",
            "/content/technoinsider/similar",
            "/content/technoinsider/stat/audience",
            "/content/technoinsider/stat/similar",
            "/channel/technoinsider/similar",
        ]:
            url = "https://telemetr.me" + path
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(3)
                b = dump(page, "ti_" + path.strip("/").replace("/", "_"))
                print(f"\n=== {url} len={len(b)} ===", flush=True)
                print(b[:1500].replace("\n", " | "), flush=True)
            except Exception as e:
                print("nav fail", path, e, flush=True)

        # If logged in, try catalog search mimicking technoinsider
        page.goto(
            "https://telemetr.me/catalog/science?subscribers_from=30000&subscribers_to=150000&er_from=12&language[]=ru&sort=-er",
            wait_until="domcontentloaded",
            timeout=90000,
        )
        time.sleep(5)
        b = dump(page, "catalog_science_filter")
        print("\nCATALOG", page.url, flush=True)
        print(b[:2500].replace("\n", " | "), flush=True)

        page.goto(
            "https://telemetr.me/catalog/it?subscribers_from=30000&subscribers_to=150000&er_from=12&language[]=ru&sort=-er",
            wait_until="domcontentloaded",
            timeout=90000,
        )
        time.sleep(5)
        b = dump(page, "catalog_it_filter")
        print("\nCATALOG_IT", page.url, flush=True)
        print(b[:2500].replace("\n", " | "), flush=True)

        # Save API payloads
        (OUT / "telemetr_api_hits.json").write_text(
            json.dumps(api_payloads, ensure_ascii=False, indent=2)[:500000],
            encoding="utf-8",
        )
        print("API_HITS", len(api_payloads), flush=True)
        for h in api_payloads[:30]:
            print(h.get("status"), h.get("url")[:120], "json" in h, flush=True)

        print("DONE", flush=True)


if __name__ == "__main__":
    main()
