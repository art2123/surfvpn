# -*- coding: utf-8 -*-
"""Batch-2: enrich VPN-сервисы + Слаги, write 50 Связки draft rows, export admin codes."""
from __future__ import annotations

import re
import sys
from datetime import date
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
OUT = Path(__file__).resolve().parent / "tgads-batch2-codes.txt"

# Final 25: (login, tip_sheet, pl, title, link, actions)
TARGETS = [
    ("technoinsider", "Канал", "c", "Техно Инсайдер", "https://t.me/technoinsider", 1347),
    ("v2raytun_bot", "Бот", "b", "v2raytun - Premium+", "https://t.me/v2raytun_bot", 167),
    ("amnezia_vpn_news_ru", "Канал", "c", "Amnezia VPN Новости", "https://t.me/amnezia_vpn_news_ru", 57),
    ("proton_vpn_news", "Канал", "c", "Proton VPN | News", "https://t.me/proton_vpn_news", 52),
    ("fastvpnkeybot", "Бот", "b", "FastKey VPN", "https://t.me/fastvpnkeybot", 32),
    ("vpnural", "Канал", "c", "Vpn Ural | Информационный", "https://t.me/vpnural", 32),
    ("clubvpnru_bot", "Бот", "b", "ClubVPN | Happ | INCY", "https://t.me/clubvpnru_bot", 52),
    ("phonkvpnbot", "Бот", "b", "phonk VPN", "https://t.me/phonkvpnbot", 45),
    ("atelecomprovpn", "Канал", "c", "Baikal Online", "https://t.me/atelecomprovpn", 28),
    ("adguardru", "Канал", "c", "AdGuard [RU]", "https://t.me/adguardru", 22),
    ("gruvpnbot", "Бот", "b", "Gru VPN", "https://t.me/GruVPNbot", 162),
    ("phantom_vpn_robot", "Бот", "b", "Phantom VPN | Happ | v2RayTun", "https://t.me/phantom_vpn_robot", 143),
    ("x_rocket_vpn_bot", "Бот", "b", "X Rocket VPN", "https://t.me/X_Rocket_VPN_bot", 114),
    ("velvet_vpn_bot", "Бот", "b", "Velvet VPN", "https://t.me/velvet_vpn_bot", 106),
    ("vpn1_news", "Канал", "c", "VPN #1 | Новости", "https://t.me/vpn1_news", 76),
    ("siriusvpn", "Канал", "c", "Sirius VPN", "https://t.me/siriusvpn", 70),
    ("planetavpna", "Канал", "c", "Planeta Vpn | Channel", "https://t.me/planetavpna", 22),
    ("green_vpn", "Канал", "c", "Green VPN | Channel", "https://t.me/green_vpn", 19),
    ("vezarys", "Канал", "c", "Vezarus", "https://t.me/vezarys", 14),
    ("dedvpn", "Канал", "c", "DedVPN", "https://t.me/dedvpn", 10),
    ("vpnducksbot", "Бот", "b", "VPN DUCKS", "https://t.me/VpnDucksBot", 13),
    ("bloggervpnbot", "Бот", "b", "BloggerVPN", "https://t.me/BloggerVPNBot", 10),
    ("vpn_raketa_bot", "Бот", "b", "VPN RAKETA", "https://t.me/VPN_Raketa_bot", 10),
    ("vpnui_bot", "Бот", "b", "UI VPN", "https://t.me/VPNUI_bot", 17),
    ("toshibuvpn_bot", "Бот", "b", "Toshibu VPN", "https://t.me/toshibuvpn_bot", 17),
]

TEXTS = ("t01", "t04")
CPM_DEFAULT = {"c": "3", "b": "3"}  # align with live batch style
BUDGET = "8"
DAILY = "8"


def make_slug(login: str) -> str:
    s = re.sub(r"[^a-z0-9]", "", login.lower().lstrip("@"))
    return s[:12]


def main() -> None:
    assert len(TARGETS) == 25, len(TARGETS)
    ss = gspread.authorize(
        Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    ).open_by_key(SHEET_ID)

    # --- VPN-сервисы ---
    inv_ws = ss.worksheet("VPN-сервисы")
    inv_vals = inv_ws.get_all_values()
    inv_header = inv_vals[0]
    inv_login_i = inv_header.index("Логин")
    existing_logins = {
        str(r[inv_login_i]).strip().lstrip("@").lower()
        for r in inv_vals[1:]
        if len(r) > inv_login_i and r[inv_login_i]
    }
    inv_new = []
    for login, tip, pl, title, link, actions in TARGETS:
        if login.lower() in existing_logins:
            continue
        row = [""] * len(inv_header)
        # map known columns
        def setc(name: str, val: str) -> None:
            if name in inv_header:
                row[inv_header.index(name)] = val

        setc("Тип", tip)
        setc("Название", title)
        setc("Логин", f"@{login}")
        setc("Ссылка", link)
        if "VPN-рекламодатели" in inv_header:
            setc("VPN-рекламодатели", f"batch2 Blanc Actions≈{actions}")
        inv_new.append(row)
        existing_logins.add(login.lower())

    if inv_new:
        inv_ws.append_rows(inv_new, value_input_option="USER_ENTERED")
    print(f"VPN-сервисы added={len(inv_new)}")

    # --- Слаги ---
    slug_ws = ss.worksheet("Слаги")
    slug_vals = slug_ws.get_all_values()
    slug_header = slug_vals[0]
    # expected: логин | slug | тип | ...
    i_login = slug_header.index("логин") if "логин" in slug_header else 0
    i_slug = slug_header.index("slug") if "slug" in slug_header else 1
    existing_slug_logins = {
        str(r[i_login]).strip().lstrip("@").lower()
        for r in slug_vals[1:]
        if len(r) > i_login and r[i_login]
    }
    used_slugs = {
        str(r[i_slug]).strip().lower()
        for r in slug_vals[1:]
        if len(r) > i_slug and r[i_slug]
    }
    slug_map: dict[str, str] = {}
    slug_new = []
    for login, tip, pl, title, link, actions in TARGETS:
        if login.lower() in existing_slug_logins:
            # find existing
            for r in slug_vals[1:]:
                if str(r[i_login]).strip().lstrip("@").lower() == login.lower():
                    slug_map[login] = str(r[i_slug]).strip()
                    break
            continue
        base = make_slug(login)
        slug = base
        n = 2
        while slug in used_slugs:
            suffix = str(n)
            slug = (base[: 12 - len(suffix)] + suffix)[:12]
            n += 1
        used_slugs.add(slug)
        slug_map[login] = slug
        tip_slug = "channel" if pl == "c" else "bot"
        row = [""] * len(slug_header)
        row[i_login] = login
        row[i_slug] = slug
        if "тип" in slug_header:
            row[slug_header.index("тип")] = tip_slug
        if "заметка" in slug_header:
            row[slug_header.index("заметка")] = f"batch2 Actions≈{actions}"
        slug_new.append(row)
        existing_slug_logins.add(login.lower())

    if slug_new:
        slug_ws.append_rows(slug_new, value_input_option="USER_ENTERED")
    print(f"Слаги added={len(slug_new)}")
    for login, tip, pl, title, link, actions in TARGETS:
        if login not in slug_map:
            for r in slug_vals[1:]:
                if str(r[i_login]).strip().lstrip("@").lower() == login.lower():
                    slug_map[login] = str(r[i_slug]).strip()
        print(f"  @{login} → {slug_map[login]} ({pl})")

    # --- 50 codes ---
    today = date.today().isoformat()
    codes: list[str] = []
    svyazki_rows: list[list[str]] = []
    sv_ws = ss.worksheet("Связки")
    sv_header = sv_ws.get_all_values()[0]
    existing_sp = {
        r[0].strip()
        for r in sv_ws.get_all_values()[1:]
        if r and r[0].startswith("tga_")
    }

    def cell(name: str, default: str = "") -> str:
        return default

    for login, tip, pl, title, link, actions in TARGETS:
        slug = slug_map[login]
        for tx in TEXTS:
            sp = f"tga_{pl}_x_{tx}_s_{slug}_eur"
            codes.append(sp)
            if sp in existing_sp:
                print(f"SKIP existing {sp}")
                continue
            row_map = {
                "start_param": sp,
                "ad_id": "",
                "ads_url": "",
                "cab": "eur",
                "pl": pl,
                "cr": "x",
                "tx": tx,
                "scope": "s",
                "slug": slug,
                "дата": today,
                "статус": "к заливке",
                "cpm": CPM_DEFAULT[pl],
                "budget": BUDGET,
                "daily_budget": DAILY,
                "promote_url": f"https://t.me/getSurfVpnBot?start={sp}",
                "промокод в админке": "нет",
                "заметка": f"batch2 @{login}; Blanc Actions≈{actions}; target {link}",
            }
            svyazki_rows.append([row_map.get(h, "") for h in sv_header])

    if svyazki_rows:
        sv_ws.append_rows(svyazki_rows, value_input_option="USER_ENTERED")
    print(f"Связки draft rows added={len(svyazki_rows)}")

    OUT.write_text("\n".join(codes) + "\n", encoding="utf-8")
    print(f"codes file={OUT} count={len(codes)}")
    for c in codes:
        print(c)


if __name__ == "__main__":
    main()
