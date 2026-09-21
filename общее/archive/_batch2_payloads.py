# -*- coding: utf-8 -*-
"""Prepare batch-2 createAd payloads from Связки (status=к заливке).

Does not call the cabinet — print JSON for browser Aj.apiRequest after admin paste.
Texts from Креативы t01/t04.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from google.oauth2.service_account import Credentials
import gspread

sys.stdout.reconfigure(encoding="utf-8")

CREDS = r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json"
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
OUT = Path(__file__).resolve().parent / "tgads-batch2-create-payloads.json"


def main() -> None:
    ss = gspread.authorize(
        Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    ).open_by_key(SHEET_ID)

    creatives = {
        r["код"]: r["содержимое"]
        for r in ss.worksheet("Креативы").get_all_records()
        if r.get("тип") == "текст"
    }
    slugs = {
        str(r["slug"]).strip(): str(r["логин"]).strip().lstrip("@")
        for r in ss.worksheet("Слаги").get_all_records()
        if r.get("slug")
    }

    vals = ss.worksheet("Связки").get_all_records()
    payloads = []
    for r in vals:
        if str(r.get("статус") or "").strip() != "к заливке":
            continue
        sp = r["start_param"]
        tx = r["tx"]
        pl = r["pl"]
        slug = r["slug"]
        login = slugs.get(slug, slug)
        target_type = "channels" if pl == "c" else "bots"
        # Target field name guessed from TG Ads UI; resolved to peer id via search* in browser
        payloads.append(
            {
                "start_param": sp,
                "title": sp,
                "text": creatives.get(tx, ""),
                "tx": tx,
                "pl": pl,
                "slug": slug,
                "login": login,
                "target_type": target_type,
                "target_url": f"https://t.me/{login}",
                "promote_url": r.get("promote_url")
                or f"https://t.me/getSurfVpnBot?start={sp}",
                "button": "open",
                "cpm": float(r.get("cpm") or 3),
                "budget": float(r.get("budget") or 8),
                "daily_budget": float(r.get("daily_budget") or 8),
                "views_per_user": 1,
                "active": 0,
                "placement": "telegram",
            }
        )

    OUT.write_text(json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} count={len(payloads)}")


if __name__ == "__main__":
    main()
