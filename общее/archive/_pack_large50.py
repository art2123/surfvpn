# -*- coding: utf-8 -*-
"""€250 large VPN pack: fill missing t01/t04/t05–t11 on top channels/bots.

Does NOT Create Ad. User pastes codes into Marketing Panel first.
CPM: channels €1.50, bots €2; budget/daily €5; cr=x, scope=s, cab=eur.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
CREDS = r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json"
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
OUT_CODES = ROOT / "tgads-large50-pack-codes.txt"
OUT_MD = ROOT / "tgads-large50-pack.md"
NOTE = f"pack €250 large {date.today().isoformat()}"

# pl, login, slug, texts to add, cpm
PACK: list[tuple[str, str, str, list[str], str]] = [
    ("c", "shukavpn", "shukavpn", ["t05", "t06", "t07", "t08", "t09", "t10", "t11"], "1.5"),
    ("c", "quattrovpn_news", "quattrovpnne", ["t05", "t06", "t07", "t08", "t09", "t10", "t11"], "1.5"),
    ("c", "sotavpn", "sotavpn", ["t01", "t04", "t07", "t09", "t10", "t11"], "1.5"),
    ("c", "amnezia_vpn_news_ru", "amneziavpnne", ["t05", "t06", "t07", "t08", "t09", "t10", "t11"], "1.5"),
    ("b", "sota", "sota", ["t05", "t06", "t07", "t08", "t09", "t10", "t11"], "2"),
    ("b", "velvet_vpn_bot", "velvetvpnbot", ["t05", "t06", "t07", "t08", "t09", "t10", "t11"], "2"),
    ("b", "atlantavpn_bot", "atlantavpnbo", ["t05", "t06", "t07", "t08", "t09", "t10", "t11"], "2"),
    ("c", "barryvpn", "barryvpn", ["t01", "t04"], "1.5"),
]


def main() -> None:
    ss = gspread.authorize(
        Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    ).open_by_key(SHEET_ID)

    sv_ws = ss.worksheet("Связки")
    sv_vals = sv_ws.get_all_values()
    headers = sv_vals[0]
    existing_sp = {
        (row[0] if row else "").strip()
        for row in sv_vals[1:]
        if row
    }

    codes: list[str] = []
    sv_rows: list[list[str]] = []
    skipped: list[str] = []

    for pl, login, slug, texts, cpm in PACK:
        for tx in texts:
            sp = f"tga_{pl}_x_{tx}_s_{slug}_eur"
            if sp in existing_sp:
                skipped.append(sp)
                continue
            promote = f"https://t.me/getSurfVpnBot?start={sp}"
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
                "дата": date.today().isoformat(),
                "статус": "к заливке",
                "cpm": cpm,
                "budget": "5",
                "daily_budget": "5",
                "promote_url": promote,
                "промокод в админке": "нет",
                "заметка": f"{NOTE}; @{login}; CPM €{cpm}; budget/daily €5",
            }
            sv_rows.append([row_map.get(c, "") for c in headers])
            codes.append(sp)
            existing_sp.add(sp)

    if len(codes) != 50:
        print(f"WARN expected 50 codes, got {len(codes)}; skipped={len(skipped)}")
        for s in skipped:
            print(f"  SKIP {s}")

    if sv_rows:
        sv_ws.append_rows(sv_rows, value_input_option="USER_ENTERED")

    OUT_CODES.write_text("\n".join(codes) + "\n", encoding="utf-8")

    lines = [
        f"# Large €250 pack — {date.today().isoformat()}",
        "",
        f"**{len(codes)} связок**, budget/daily **€5**, CPM канал €1.50 / бот €2, "
        "`cr=x`, `scope=s`, `_eur`, статус `к заливке`.",
        "",
        "Коды: [`tgads-large50-pack-codes.txt`](tgads-large50-pack-codes.txt)",
        "",
        "## Сетка",
        "",
        "| pl | login | slug | texts | ads |",
        "|---|---|---|---|---:|",
    ]
    for pl, login, slug, texts, cpm in PACK:
        n = sum(1 for tx in texts if f"tga_{pl}_x_{tx}_s_{slug}_eur" in codes)
        lines.append(
            f"| {pl} | @{login} | `{slug}` | {','.join(texts)} | {n} |"
        )
    lines += [
        "",
        "## Админка",
        "",
        f"Вставить **{len(codes)}** кодов в Marketing Panel, затем Create Ad → Active.",
        "",
        "### Коды",
        "",
        "```",
        *codes,
        "```",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote svyazki={len(sv_rows)} codes={len(codes)}")
    print(f"wrote {OUT_CODES}")
    print(f"wrote {OUT_MD}")
    for c in codes:
        print(c)


if __name__ == "__main__":
    main()
