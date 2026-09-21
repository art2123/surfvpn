# -*- coding: utf-8 -*-
"""Build first competitor-kill pack from tgads-competitor-creatives.csv.

Excludes Surf aliases and already-live Связки slugs.
Writes Слаги + VPN-сервисы + Связки drafts; prints admin codes.
Does NOT Create Ad (admin gate).
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from google.oauth2.service_account import Credentials
import gspread

CREDS = r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json"
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
CSV = Path(__file__).resolve().parent.parent / "tgads-competitor-creatives.csv"
OUT = Path(__file__).resolve().parent / "tgads-competitor-pack1-codes.txt"
PACK_N = 15  # platforms → ×2 texts
OWN_LOGINS = {
    "surfvpn",
    "getsurfvpnbot",
    "getsurfvpnb",
    "surfvpnb",
    "surf_vpn",
}


def slugify(login: str) -> str:
    s = re.sub(r"[^a-z0-9]", "", login.lower())
    if s.endswith("bot") and len(s) > 12:
        # keep bot suffix compressed
        base = s[:-3]
        s = (base[:9] + "bot") if len(base) > 9 else s
    return s[:12]


def tip_of(login: str) -> tuple[str, str]:
    """Return (sheet tip, pl code)."""
    low = login.lower()
    if low.endswith("bot") or "_bot" in low or low.endswith("robot"):
        return "Бот", "b"
    return "Канал", "c"


def main() -> None:
    rows = list(csv.DictReader(CSV.open(encoding="utf-8-sig", newline="")))
    by: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "mau": 0, "sample": "", "adv": set()}
    )
    for r in rows:
        d = (r.get("destination") or "").strip()
        if not d:
            continue
        m = re.search(r"(?:t\.me/|@)?([A-Za-z0-9_]+)", d, re.I)
        if not m:
            continue
        login = m.group(1)
        low = login.lower()
        if low in OWN_LOGINS or low in ("share", "joinchat", "addstickers"):
            continue
        by[login]["n"] += 1
        try:
            mau = int(float(r.get("bot_mau") or 0))
        except ValueError:
            mau = 0
        by[login]["mau"] = max(by[login]["mau"], mau)
        by[login]["sample"] = d
        if r.get("advertiser"):
            by[login]["adv"].add(r["advertiser"])

    ranked = sorted(
        by.items(), key=lambda kv: (-kv[1]["n"], -kv[1]["mau"], kv[0].lower())
    )

    ss = gspread.authorize(
        Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    ).open_by_key(SHEET_ID)

    # existing slugs + live
    slug_ws = ss.worksheet("Слаги")
    slug_vals = slug_ws.get_all_values()
    slug_h = slug_vals[0]
    slug_idx = {c: i for i, c in enumerate(slug_h)}
    login_to_slug = {}
    used_slugs = set()
    for row in slug_vals[1:]:
        while len(row) < len(slug_h):
            row.append("")
        login = row[slug_idx["логин"]].lstrip("@").strip()
        slug = row[slug_idx["slug"]].strip()
        if login:
            login_to_slug[login.lower()] = slug
        if slug:
            used_slugs.add(slug.lower())

    sv = ss.worksheet("Связки").get_all_values()
    sh = sv[0]
    si = {c: i for i, c in enumerate(sh)}
    live_logins = set()
    live_slugs = set()
    existing_sp = set()
    for row in sv[1:]:
        while len(row) < len(sh):
            row.append("")
        sp = row[si["start_param"]].strip()
        existing_sp.add(sp)
        st = row[si["статус"]]
        if any(
            x in st
            for x in ("Deleted", "удален", "Declined", "fail", "дорогой клик", "скрутка", "накрученный")
        ):
            # still don't re-create same start_param
            pass
        slug = row[si["slug"]].strip().lower()
        if slug:
            live_slugs.add(slug)
        m = re.search(r"_s_([a-z0-9]+)_", sp)
        if m:
            live_slugs.add(m.group(1))

    inv = ss.worksheet("VPN-сервисы").get_all_values()
    inv_h = inv[0]
    inv_logins = {
        (r[inv_h.index("Логин")] if "Логин" in inv_h and len(r) > inv_h.index("Логин") else "")
        .lstrip("@")
        .lower()
        for r in inv[1:]
    }

    picks = []
    skipped = []
    for login, meta in ranked:
        low = login.lower()
        tip, pl = tip_of(login)
        slug = login_to_slug.get(low) or slugify(login)
        # collide slug uniqueness
        base = slug
        n = 2
        while slug.lower() in used_slugs and login_to_slug.get(low) != slug:
            slug = (base[: 12 - len(str(n))] + str(n))[:12]
            n += 1
        if slug.lower() in live_slugs or low in {x.lower() for x in live_logins}:
            skipped.append((login, "already live"))
            continue
        # also skip if any start_param already for this slug
        if any(f"_s_{slug}_" in sp for sp in existing_sp):
            skipped.append((login, "start_param exists"))
            continue
        picks.append(
            {
                "login": login,
                "slug": slug,
                "tip": tip,
                "pl": pl,
                "n": meta["n"],
                "mau": meta["mau"],
                "url": f"https://t.me/{login}",
            }
        )
        used_slugs.add(slug.lower())
        if len(picks) >= PACK_N:
            break

    print(f"ranked={len(ranked)} picks={len(picks)} skipped_sample={skipped[:8]}")
    for p in picks:
        print(
            f"  {p['n']:2d} creatives mau={p['mau']:6d} {p['pl']} @{p['login']} → {p['slug']}"
        )

    # upsert Слаги
    slug_new = []
    for p in picks:
        if p["login"].lower() in login_to_slug:
            continue
        tip_s = "бот" if p["pl"] == "b" else "канал"
        slug_new.append(
            [
                p["login"],
                p["slug"],
                tip_s,
                f"competitor-pack1 {date.today().isoformat()}; creatives≈{p['n']}",
            ]
        )
    if slug_new:
        slug_ws.append_rows(slug_new, value_input_option="USER_ENTERED")
    print(f"slugs_added={len(slug_new)}")

    # upsert VPN-сервисы
    inv_new = []
    for p in picks:
        if p["login"].lower() in inv_logins:
            continue
        # Тип, Название, Логин, Ссылка, ...
        row = [""] * len(inv_h)
        row[inv_h.index("Тип")] = p["tip"]
        row[inv_h.index("Название")] = p["login"]
        row[inv_h.index("Логин")] = p["login"]
        row[inv_h.index("Ссылка")] = p["url"]
        if "Подписчики" in inv_h and p["mau"]:
            # mau is bot mau not subs — leave note
            pass
        inv_new.append(row)
    if inv_new:
        ss.worksheet("VPN-сервисы").append_rows(
            inv_new, value_input_option="USER_ENTERED"
        )
    print(f"inventory_added={len(inv_new)}")

    # Связки drafts
    texts = ("t01", "t04")
    sv_rows = []
    codes = []
    for p in picks:
        for tx in texts:
            sp = f"tga_{p['pl']}_x_{tx}_s_{p['slug']}_eur"
            if sp in existing_sp:
                continue
            codes.append(sp)
            promote = f"https://t.me/getSurfVpnBot?start={sp}"
            note = (
                f"competitor-pack1; @{p['login']}; creatives≈{p['n']}; "
                f"mau≈{p['mau']}; CPM/budget/daily €5; гасим конкурента"
            )
            row_map = {
                "start_param": sp,
                "ad_id": "",
                "ads_url": "",
                "cab": "eur",
                "pl": p["pl"],
                "cr": "x",
                "tx": tx,
                "scope": "s",
                "slug": p["slug"],
                "дата": date.today().isoformat(),
                "статус": "к заливке",
                "cpm": "5",
                "budget": "5",
                "daily_budget": "5",
                "promote_url": promote,
                "промокод в админке": "нет",
                "заметка": note,
            }
            sv_rows.append([row_map.get(c, "") for c in sh])

    if sv_rows:
        ss.worksheet("Связки").append_rows(sv_rows, value_input_option="USER_ENTERED")
    print(f"svyazki_added={len(sv_rows)}")

    OUT.write_text("\n".join(codes) + "\n", encoding="utf-8")
    print("\n=== ADMIN PASTE ===")
    print("\n".join(codes))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
