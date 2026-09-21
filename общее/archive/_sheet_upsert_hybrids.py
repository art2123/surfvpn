# -*- coding: utf-8 -*-
"""Upsert hybrid shortlist into «Все остальное» + «Слаги»."""
from __future__ import annotations

import json
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
CREDS = Path(r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json")
SHORTLIST = Path(__file__).resolve().parent.parent / "imports" / "ti_hybrid_shortlist.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Prefer stable marketing slugs (not raw login with underscores when possible)
SLUG_MAP = {
    "blokirovki_runeta": "blokiruneta",
    "tginfo": "tginfo",
    "rozetked": "rozetked",
    "lagomvpn": "lagomvpn",
    "amnezia_vpn_news_ru": "amnezianews",
    "quattrovpn_news": "quattronews",
    "roskomsvoboda": "roskomsvoboda",
}


def main() -> None:
    data = json.loads(SHORTLIST.read_text(encoding="utf-8"))
    rows = data["priority_batch"]
    creds = Credentials.from_service_account_file(str(CREDS), scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    inv = sh.worksheet("Все остальное")
    slugs = sh.worksheet("Слаги")

    inv_vals = inv.get_all_values()
    slug_vals = slugs.get_all_values()

    existing_logins = set()
    for r in inv_vals[1:]:
        if len(r) > 2 and r[2]:
            existing_logins.add(r[2].strip().lstrip("@").lower())

    existing_slug_logins = {}
    used_slugs = set()
    for r in slug_vals[1:]:
        login = (r[0] if r else "").strip().lstrip("@").lower()
        slug = (r[1] if len(r) > 1 else "").strip()
        if login:
            existing_slug_logins[login] = slug
        if slug:
            used_slugs.add(slug)

    # Update technoinsider slug note
    for i, r in enumerate(slug_vals[1:], start=2):
        login = (r[0] if r else "").strip().lstrip("@").lower()
        if login in ("technoinsider", "technoinside"):
            note = (
                "эталон гибрида tech+VPN/RKN (Gru); Surf trials winner; "
                "см. общее/tgads-quality-media.md"
            )
            # col D = заметка
            slugs.update_cell(i, 4, note)
            print(f"updated Слаги note for {login} row {i}")
            break

    for item in rows:
        login = item["login"].lower()
        title = {
            "blokirovki_runeta": "Блокировки Рунета | Новости",
            "tginfo": "Telegram Info",
            "rozetked": "Rozetked",
            "lagomvpn": "Lagom VPN — Новости ВПН",
            "amnezia_vpn_news_ru": "Amnezia VPN Новости",
            "quattrovpn_news": "Quattro VPN — Новости",
            "roskomsvoboda": "Roskomsvoboda",
        }.get(login, login)
        note = (
            f"TI-hybrid P{item.get('priority')}/{item.get('class')}; "
            f"subs={item.get('subs')} er={item.get('er')}; {item.get('why', '')}"
        )

        if login not in existing_logins:
            inv.append_row(
                [
                    "Канал",
                    title,
                    f"@{login}",
                    f"https://t.me/{login}",
                    str(item.get("subs") or ""),
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ],
                value_input_option="USER_ENTERED",
            )
            existing_logins.add(login)
            print(f"+inv @{login}")
        else:
            print(f"=inv exists @{login}")

        if login not in existing_slug_logins:
            s = SLUG_MAP.get(login, login.replace("_", "")[:20])
            base = s
            n = 2
            while s in used_slugs:
                s = f"{base}{n}"
                n += 1
            slugs.append_row(
                [login, s, "канал", note],
                value_input_option="USER_ENTERED",
            )
            existing_slug_logins[login] = s
            used_slugs.add(s)
            print(f"+slug {login} -> {s}")
        else:
            # refresh note
            for i, r in enumerate(slug_vals[1:], start=2):
                if (r[0] if r else "").strip().lstrip("@").lower() == login:
                    slugs.update_cell(i, 4, note)
                    print(f"=slug note refresh {login}")
                    break
            else:
                # newly appended during this run not in slug_vals snapshot — ok
                print(f"=slug exists {login} -> {existing_slug_logins[login]}")


if __name__ == "__main__":
    main()
