# -*- coding: utf-8 -*-
"""Build technoinsider lookalike shortlist, write sheet + batch files."""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

from google.oauth2.service_account import Credentials
import gspread

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
CREDS = r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json"
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
IMPORTS = ROOT / "imports"
SNAP = ROOT / "tgads-snapshots"
IMPORTS.mkdir(exist_ok=True)
SNAP.mkdir(exist_ok=True)

# Curated shortlist after Telemetr similar + vpn-native-hosts + profile checks.
# tab: other = Все остальное, vpn = VPN-сервисы (only if product channel)
# priority A = hybrid tech+VPN / RKN like TI; B = tech/OSINT/blocks media
CANDIDATES: list[dict] = [
    {
        "login": "technoinsider",
        "title": "Техно Инсайдер",
        "subs": 75672,
        "views": 15020,
        "er": 19.86,
        "er_daily": 16.1,
        "reason": "etalon",
        "note": "эталон good: Blanc purchases + Surf trials; Gru VPN media; ER~20%",
        "tab": "other",
        "priority": "A",
        "batch": False,  # already live
    },
    {
        "login": "grumarket",
        "title": "ГрюМаркет - Новости | GRUMARKET",
        "subs": 79958,
        "views": 7338,
        "er": 10.42,
        "reason": "same-ecosystem",
        "note": "та же семья Gru; ER ниже TI; cross-promo",
        "tab": "other",
        "priority": "B",
        "batch": False,  # ER <12 and same brand family — skip ads for now
    },
    {
        "login": "sotavpn",
        "title": "Sota VPN — Канал",
        "subs": 1004830,
        "views": 263322,
        "er": 27.3,
        "reason": "similar+high-er",
        "note": "TI similar #6; VPN news mega; ER 27%",
        "tab": "vpn",
        "priority": "A",
        "batch": True,
    },
    {
        "login": "legendaryvpn_news",
        "title": "Legendary VPN — Новостной канал",
        "subs": 5380,
        "views": 1557,
        "er": None,
        "reason": "similar",
        "note": "TI similar; мал (<20k) — watchlist, не в батч",
        "tab": "vpn",
        "priority": "C",
        "batch": False,
    },
    {
        "login": "vpn1_news",
        "title": "VPN #1 | Новости",
        "subs": None,
        "views": None,
        "er": None,
        "reason": "vpn-news-hybrid",
        "note": "уже Batch-2; hybrid news как TI",
        "tab": "vpn",
        "priority": "A",
        "batch": False,
    },
    {
        "login": "amnezia_vpn_news_ru",
        "title": "Amnezia VPN Новости",
        "subs": None,
        "views": None,
        "er": None,
        "reason": "vpn-news-hybrid",
        "note": "уже Batch-2",
        "tab": "vpn",
        "priority": "A",
        "batch": False,
    },
    {
        "login": "proton_vpn_news",
        "title": "Proton VPN | News",
        "subs": None,
        "views": None,
        "er": None,
        "reason": "vpn-news-hybrid",
        "note": "уже Batch-2",
        "tab": "vpn",
        "priority": "A",
        "batch": False,
    },
    {
        "login": "aprelteam",
        "title": "Aprel Team",
        "subs": 15608,
        "views": 2549,
        "er": None,
        "reason": "similar",
        "note": "TI similar; около-VPN инфлюенсер",
        "tab": "other",
        "priority": "B",
        "batch": True,
    },
    {
        "login": "olegaprel",
        "title": "Oleg Aprel",
        "subs": 17788,
        "views": 2729,
        "er": None,
        "reason": "similar",
        "note": "TI similar; связан с Aprel",
        "tab": "other",
        "priority": "B",
        "batch": True,
    },
    {
        "login": "estradavoice",
        "title": "Голос Эстрады",
        "subs": 20454,
        "views": None,
        "er": None,
        "reason": "native-host-rkn",
        "note": "vpn-native: посты про РКН/VPN; 19 посевов",
        "tab": "other",
        "priority": "A",
        "batch": True,
    },
    {
        "login": "kolezev",
        "title": "Колезев",
        "subs": 59893,
        "views": None,
        "er": None,
        "reason": "native-host-blanc",
        "note": "vpn-native: Blanc/Paper посевы; author blog",
        "tab": "other",
        "priority": "A",
        "batch": True,
    },
    # From vpn-native IT/tech/blocks — usernames filled after CSV parse / telemetr
]

DROP = {
    "tmamont",
    "fenix_vpn_ru",
    "mems_skam",
    "crypta_ai",
    "alexbachtech",  # too small
    "scamrsalert",
    "scamsociety",
}


def make_slug(login: str) -> str:
    s = re.sub(r"[^a-z0-9]", "", login.lower().lstrip("@"))
    return s[:12]


def load_native_tech() -> list[dict]:
    path = ROOT / "vpn-native-hosts-telemetr.csv"
    out = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            cat = (r.get("категории") or "").lower()
            name = r.get("канал") or ""
            user = (r.get("username") or "").strip().lstrip("@")
            gold = (r.get("золото") or "").strip().lower()
            quality = (r.get("качество") or "").strip().lower()
            if quality.startswith("исключ"):
                continue
            blob = f"{cat} {name}".lower()
            techish = any(
                x in blob
                for x in (
                    "ит",
                    "наук",
                    "технолог",
                    "osint",
                    "блокиров",
                    "хакер",
                    "кибер",
                )
            )
            if not techish:
                continue
            if not user:
                continue
            try:
                subs = int(str(r.get("подписчики") or "0").replace(" ", "").replace(",", ""))
            except ValueError:
                subs = 0
            out.append(
                {
                    "login": user.lower(),
                    "title": name,
                    "subs": subs,
                    "views": None,
                    "er": None,
                    "reason": "native-host-tech",
                    "note": f"vpn-native посевов={r.get('vpn_посевов')}; {r.get('категории')}",
                    "tab": "other",
                    "priority": "A" if gold == "да" or "блокиров" in blob else "B",
                    "batch": 20000 <= subs <= 250000,
                }
            )
    return out


def merge_candidates() -> list[dict]:
    by: dict[str, dict] = {}
    for c in CANDIDATES:
        by[c["login"].lower()] = dict(c)
    for c in load_native_tech():
        login = c["login"].lower()
        if login in DROP:
            continue
        if login in by:
            # enrich note
            by[login]["note"] = by[login].get("note", "") + " | " + c["note"]
            if by[login].get("subs") is None:
                by[login]["subs"] = c["subs"]
            continue
        by[login] = c
    # drop known bad
    for d in DROP:
        by.pop(d, None)
    return list(by.values())


def ss_connect():
    return gspread.authorize(
        Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    ).open_by_key(SHEET_ID)


def upsert_inventory(ss, candidates: list[dict]) -> None:
    for tab_name, tab_key in (("Все остальное", "other"), ("VPN-сервисы", "vpn")):
        ws = ss.worksheet(tab_name)
        vals = ws.get_all_values()
        header = vals[0]
        login_i = header.index("Логин")
        existing = {}
        for idx, r in enumerate(vals[1:], start=2):
            if len(r) <= login_i:
                continue
            key = str(r[login_i]).strip().lstrip("@").lower()
            if key:
                existing[key] = idx

        def setc(row: list, name: str, val: str) -> None:
            if name in header:
                row[header.index(name)] = val

        new_rows = []
        for c in candidates:
            if c.get("tab") != tab_key:
                continue
            login = c["login"].lower()
            note = c.get("note") or ""
            metrics = []
            if c.get("subs"):
                metrics.append(f"subs={c['subs']}")
            if c.get("er") is not None:
                metrics.append(f"ER={c['er']}%")
            if c.get("views"):
                metrics.append(f"views/post={c['views']}")
            metrics.append(f"reason={c.get('reason')}")
            metrics.append(f"prio={c.get('priority')}")
            full_note = "; ".join(metrics + ([note] if note else []))

            if login == "technoinsider" and login in existing:
                # update note column if present
                row_idx = existing[login]
                if "Заметка" in header:
                    ws.update_cell(row_idx, header.index("Заметка") + 1, full_note)
                elif "заметка" in header:
                    ws.update_cell(row_idx, header.index("заметка") + 1, full_note)
                print(f"updated note {tab_name} @{login}")
                continue

            if login in existing:
                print(f"skip existing {tab_name} @{login}")
                continue

            row = [""] * len(header)
            setc(row, "Тип", "Канал")
            setc(row, "Название", c.get("title") or login)
            setc(row, "Логин", f"@{login}")
            setc(row, "Ссылка", f"https://t.me/{login}")
            if c.get("subs") and "Подписчики" in header:
                setc(row, "Подписчики", str(c["subs"]))
            for col in ("Заметка", "заметка"):
                if col in header:
                    setc(row, col, full_note[:500])
            if "VPN-рекламодатели" in header and c.get("reason", "").startswith("native"):
                setc(row, "VPN-рекламодатели", "vpn-native-hosts")
            new_rows.append(row)

        if new_rows:
            ws.append_rows(new_rows, value_input_option="USER_ENTERED")
        print(f"{tab_name} added={len(new_rows)}")


def upsert_slugs(ss, candidates: list[dict]) -> dict[str, str]:
    slug_ws = ss.worksheet("Слаги")
    vals = slug_ws.get_all_values()
    header = vals[0]
    i_login = header.index("логин") if "логин" in header else 0
    i_slug = header.index("slug") if "slug" in header else 1
    existing = {}
    used = set()
    for r in vals[1:]:
        if len(r) <= max(i_login, i_slug):
            continue
        login = str(r[i_login]).strip().lstrip("@").lower()
        slug = str(r[i_slug]).strip().lower()
        if login:
            existing[login] = slug
        if slug:
            used.add(slug)

    slug_map = dict(existing)
    new_rows = []
    for c in candidates:
        login = c["login"].lower()
        if login in slug_map:
            continue
        base = make_slug(login)
        slug = base
        n = 2
        while slug in used:
            suffix = str(n)
            slug = (base[: 12 - len(suffix)] + suffix)[:12]
            n += 1
        used.add(slug)
        slug_map[login] = slug
        row = [""] * len(header)
        row[i_login] = login
        row[i_slug] = slug
        if "тип" in header:
            row[header.index("тип")] = "channel"
        if "заметка" in header:
            row[header.index("заметка")] = f"ti-lookalike {c.get('reason')}"
        new_rows.append(row)

    if new_rows:
        slug_ws.append_rows(new_rows, value_input_option="USER_ENTERED")
    print(f"Слаги added={len(new_rows)}")
    return slug_map


def write_batch(ss, candidates: list[dict], slug_map: dict[str, str]) -> None:
    batch = [c for c in candidates if c.get("batch")]
    # Prefer A then B; cap 10 platforms → 20 ads
    batch.sort(key=lambda c: (0 if c.get("priority") == "A" else 1, -(c.get("subs") or 0)))
    batch = batch[:10]
    texts = ("t01", "t04")
    today = date.today().isoformat()

    codes = []
    payloads = []
    sv_rows = []
    for c in batch:
        login = c["login"].lower()
        slug = slug_map.get(login) or make_slug(login)
        for tx in texts:
            code = f"tga_c_x_{tx}_s_{slug}_eur"
            codes.append(code)
            payloads.append(
                {
                    "title": code,
                    "promote_url": f"https://t.me/surfvpn?start={code}",
                    "target_type": "channels",
                    "channels": f"https://t.me/{login}",
                    "cpm": 1.5,
                    "budget": 8,
                    "daily_budget": 8,
                    "views_per_user": 1,
                    "active": False,
                    "status": "On Hold",
                    "text_id": tx,
                    "login": login,
                }
            )

    # Связки
    sv = ss.worksheet("Связки")
    sv_vals = sv.get_all_values()
    sv_h = sv_vals[0]
    existing_codes = {
        str(r[sv_h.index("start_param")]).strip()
        for r in sv_vals[1:]
        if len(r) > sv_h.index("start_param") and r[sv_h.index("start_param")]
    }
    for p in payloads:
        code = p["title"]
        if code in existing_codes:
            continue
        row = [""] * len(sv_h)

        def setc(name: str, val: str) -> None:
            if name in sv_h:
                row[sv_h.index(name)] = val

        setc("start_param", code)
        setc("cab", "eur")
        setc("pl", "c")
        setc("cr", "x")
        setc("tx", p["text_id"])
        setc("scope", "s")
        setc("slug", code.split("_s_")[1].rsplit("_", 1)[0])
        setc("статус", "к заливке")
        setc("cpm", "1.5")
        setc("budget", "8")
        setc("daily_budget", "8")
        setc("promote_url", p["promote_url"])
        setc("промокод в админке", "нет")
        setc("заметка", f"ti-lookalike batch4 {today}; @{p['login']}")
        sv_rows.append(row)

    if sv_rows:
        sv.append_rows(sv_rows, value_input_option="USER_ENTERED")
    print(f"Связки added={len(sv_rows)}")

    (ROOT / "tgads-batch4-codes.txt").write_text("\n".join(codes) + "\n", encoding="utf-8")
    (ROOT / "tgads-batch4-create-payloads.json").write_text(
        json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Batch 4 — TI lookalikes (Channels scope=s)",
        "",
        f"Дата: {today}. **{len(batch)} площадок × t01+t04** = {len(codes)} связок, `cr=x`, `_eur`.",
        "",
        "Коды: [`tgads-batch4-codes.txt`](tgads-batch4-codes.txt)",
        "Payloads: [`tgads-batch4-create-payloads.json`](tgads-batch4-create-payloads.json)",
        "",
        "**До Create Ad:** вставить коды в Marketing Panel. Потом Create Ad: CPM €1.50, Initial/Daily €8, views/user 1, On Hold. Destination `@surfvpn`.",
        "",
        "## Площадки",
        "",
        "| # | Логин | slug | subs | ER | Почему |",
        "|---|---|---|---:|---:|---|",
    ]
    for i, c in enumerate(batch, 1):
        login = c["login"].lower()
        slug = slug_map.get(login) or make_slug(login)
        lines.append(
            f"| {i} | @{login} | {slug} | {c.get('subs') or '—'} | {c.get('er') if c.get('er') is not None else '—'} | {c.get('reason')}: {c.get('note','')[:80]} |"
        )
    lines += [
        "",
        "## Статус",
        "",
        "- **Все остальное / VPN-сервисы / Слаги:** обновлены скриптом `_ti_lookalike_build.py`",
        "- **Связки:** строки `к заливке`, `промокод в админке=нет`",
        "- **Create Ad:** ещё не запускался — после вставки кодов в админку",
        "",
    ]
    (ROOT / "tgads-batch4.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote batch4 files", len(codes), "codes")


def main() -> None:
    candidates = merge_candidates()
    (IMPORTS / "ti_lookalike_shortlist.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"shortlist size={len(candidates)}")
    for c in sorted(candidates, key=lambda x: (x.get("priority") or "Z", -(x.get("subs") or 0))):
        print(
            f"  [{c.get('priority')}] @{c['login']:24} tab={c.get('tab')} batch={c.get('batch')} "
            f"subs={c.get('subs')} er={c.get('er')} :: {c.get('reason')}"
        )

    ss = ss_connect()
    upsert_inventory(ss, candidates)
    slug_map = upsert_slugs(ss, candidates)
    write_batch(ss, candidates, slug_map)
    print("DONE")


if __name__ == "__main__":
    main()
