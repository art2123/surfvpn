# -*- coding: utf-8 -*-
"""Batch Telemetr ER for hybrid shortlist via Edge CDP (port 9222)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "imports" / "ti_hybrid_telemetr_er.json"

LOGINS = [
    "technoinsider",
    "blokirovki_runeta",
    "rozetked",
    "tginfo",
    "it_teech",
    "techno_novinki",
    "mobile_review",
    "xor_journal",
    "habr_com",
    "hightech_fm",
    "roskomsvoboda",
    "adguardru",
    "vpn1_news",
    "amnezia_vpn_news_ru",
    "lagomvpn",
    "quattrovpn_news",
    "dedvpn",
    "siriusvpn",
    "green_vpn",
    "shukavpn",
]


def parse(body: str) -> dict:
    out: dict = {}
    m = re.search(r"Подписчиков\s*Всего\s*([\d\s'’]+)", body)
    if m:
        out["subs"] = int(re.sub(r"[\s'’]", "", m.group(1)))
    m = re.search(r"Просмотров на пост\s*([\d\s'’]+)", body)
    if m:
        out["views"] = int(re.sub(r"[\s'’]", "", m.group(1)))
    m = re.search(r"\bER\s*([\d.,]+)\s*%", body)
    if m:
        out["er"] = float(m.group(1).replace(",", "."))
    m = re.search(r"Суточный\s*([\d.,]+)\s*%", body)
    if m:
        out["er_daily"] = float(m.group(1).replace(",", "."))
    return out


def main() -> None:
    rows = []
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

        for login in LOGINS:
            url = f"https://telemetr.me/@{login}"
            print(f"→ {login}", flush=True)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90000)
                time.sleep(3.5)
                body = page.inner_text("body")
                metrics = parse(body)
                row = {"login": login, "url": url, **metrics}
                if not metrics:
                    row["error"] = "no metrics parsed"
                rows.append(row)
                print(
                    f"  subs={row.get('subs')} views={row.get('views')} er={row.get('er')}",
                    flush=True,
                )
            except Exception as e:
                rows.append({"login": login, "url": url, "error": str(e)})
                print(f"  ERR {e}", flush=True)

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
