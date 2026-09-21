# -*- coding: utf-8 -*-
"""Prepare contested VPN-channel pack: 7 texts × 8 channels → Связки + admin codes.

Does NOT Create Ad. User pastes codes into Marketing Panel first.
CPM/budget/daily = €5. cr=x, scope=s, cab=eur, status=к заливке.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from google.oauth2.service_account import Credentials
import gspread

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
CREDS = r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json"
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
PLACEMENTS = ROOT.parent / "tgmaps-vpn-placements.csv"
OUT_CODES = ROOT / "tgads-contested-vpn-pack-codes.txt"
OUT_MD = ROOT / "tgads-contested-vpn-pack.md"

# User-approved copy (7 texts). Product-spec risks noted in заметка.
TEXTS = [
    "Постоянно отваливается VPN? Попробуйте Surf – обходит блокировки, сам выбирает рабочую локацию, не нужно постоянно включать и выключать VPN",
    "Surf VPN обходит любые блокировки. Настройка в 1 клик. Попробуйте 3 дня бесплатно",
    "Сайты не открываются, а телега тормозит? Попробуйте надежный Surf VPN – работает в России, обходит любые блокировки. 3 дня на тест за 1 рубль.",
    "3 дня за 1 рубль. Работает в России. Обходит блокировки",
    "Surf VPN от 100 ₽/мес при оплате на 24 месяца. Безлимит скорости и трафика. Работает в России.",
    "Нужен быстрый и рабочий VPN без сложных настроек? Surf — высокая скорость, автовыбор локации. Попробовать 3 дня за 1 рубль",
    "Нейросети работают с любой локации. Безлимит скорости и трафика. Подключайтесь за 1 рубль!",
]

# Preferred VPN-themed contested channels (from TgMaps placements).
PREFERRED = [
    "itopvpn_ru",
    "vpnproxymaster_russia",
    "getoutlinevpn_channel",
    "nashvpnnews",
    "aveselov_ru",
    "vless_vpns",
    "barryvpn",
    "siriusvpn",
]

VPN_HINT = re.compile(
    r"vpn|vless|proxy|прокси|обход|outline|amnezia|hiddify|v2ray|wireguard|"
    r"туннел|tunnel|белый.?спис|глушил|ркн|runet|интернет.?свобод",
    re.I,
)

BAD_STATUS = (
    "дорогой клик",
    "скрутка",
    "накрученный",
    "Deleted",
    "удален",
    "Declined",
)


def slugify(login: str) -> str:
    s = re.sub(r"[^a-z0-9]", "", login.lower())
    return s[:12]


def contested_channels() -> list[dict]:
    by: dict[str, set[str]] = defaultdict(set)
    title: dict[str, str] = {}
    for r in csv.DictReader(PLACEMENTS.open(encoding="utf-8")):
        ch = (r.get("channel_login") or "").lower().lstrip("@")
        dest = (r.get("destination") or "").lower().lstrip("@")
        if not ch or not dest:
            continue
        by[ch].add(dest)
        title[ch] = r.get("channel_title") or title.get(ch) or ""
    rows = []
    for ch, dests in by.items():
        if len(dests) < 2:
            continue
        t = title.get(ch) or ""
        is_vpn = bool(VPN_HINT.search(ch) or VPN_HINT.search(t))
        rows.append(
            {
                "login": ch,
                "title": t,
                "contested": len(dests),
                "dests": sorted(dests),
                "is_vpn": is_vpn,
            }
        )
    rows.sort(key=lambda x: (-int(x["is_vpn"]), -x["contested"], x["login"]))
    return rows


def next_tx_codes(cre_vals: list[list[str]], n: int) -> list[str]:
    header = cre_vals[0]
    # find code column
    code_col = None
    for cand in ("код", "id", "tx", "номер"):
        if cand in header:
            code_col = header.index(cand)
            break
    if code_col is None:
        # first col often code
        code_col = 0
    used = set()
    max_n = 0
    for row in cre_vals[1:]:
        if len(row) <= code_col:
            continue
        code = (row[code_col] or "").strip().lower()
        used.add(code)
        m = re.match(r"^t(\d+)$", code)
        if m:
            max_n = max(max_n, int(m.group(1)))
    out = []
    cur = max_n
    while len(out) < n:
        cur += 1
        code = f"t{cur:02d}"
        if code not in used:
            out.append(code)
    return out


def main() -> None:
    contested = contested_channels()
    by_login = {r["login"]: r for r in contested}

    ss = gspread.authorize(
        Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    ).open_by_key(SHEET_ID)

    # --- Слаги ---
    slug_ws = ss.worksheet("Слаги")
    slug_vals = slug_ws.get_all_values()
    slug_h = slug_vals[0]
    si_slug = {c: i for i, c in enumerate(slug_h)}
    login_to_slug: dict[str, str] = {}
    used_slugs: set[str] = set()
    blocked_logins: set[str] = set()
    for row in slug_vals[1:]:
        while len(row) < len(slug_h):
            row.append("")
        login = row[si_slug.get("логин", 0)].lstrip("@").strip().lower()
        slug = (row[si_slug.get("slug", 1)] or "").strip().lower()
        note = " ".join(row).lower()
        if login:
            login_to_slug[login] = slug or login_to_slug.get(login, "")
        if slug:
            used_slugs.add(slug)
        if any(b in note for b in BAD_STATUS) and login:
            blocked_logins.add(login)

    # --- Связки existing ---
    sv_ws = ss.worksheet("Связки")
    sv_vals = sv_ws.get_all_values()
    sh = sv_vals[0]
    si = {c: i for i, c in enumerate(sh)}
    existing_sp = set()
    live_slugs: set[str] = set()
    for row in sv_vals[1:]:
        while len(row) < len(sh):
            row.append("")
        sp = (row[si["start_param"]] or "").strip()
        existing_sp.add(sp)
        st = row[si["статус"]] or ""
        slug = (row[si["slug"]] or "").strip().lower()
        if slug and not any(b in st for b in BAD_STATUS):
            # already have campaigns on this slug — still OK to add new texts
            # but avoid duplicate start_param
            pass
        m = re.search(r"_s_([a-z0-9]+)_", sp)
        if m:
            live_slugs.add(m.group(1))

    # --- pick 8 channels ---
    picks: list[dict] = []
    for login in PREFERRED:
        meta = by_login.get(login.lower())
        if not meta:
            print(f"WARN preferred @{login} not in contested placements")
            meta = {
                "login": login.lower(),
                "title": login,
                "contested": 0,
                "dests": [],
                "is_vpn": True,
            }
        if login.lower() in blocked_logins:
            print(f"SKIP blocked @{login}")
            continue
        slug = login_to_slug.get(login.lower()) or slugify(login)
        base = slug
        n = 2
        while slug.lower() in used_slugs and login_to_slug.get(login.lower()) != slug:
            slug = (base[: 12 - len(str(n))] + str(n))[:12]
            n += 1
        picks.append(
            {
                "login": login.lower(),
                "title": meta["title"],
                "contested": meta["contested"],
                "dests": meta["dests"][:8],
                "slug": slug,
            }
        )
        used_slugs.add(slug.lower())
        if len(picks) >= 8:
            break

    # fill from other VPN contested if needed
    if len(picks) < 8:
        have = {p["login"] for p in picks}
        for meta in contested:
            if not meta["is_vpn"] or meta["login"] in have:
                continue
            if meta["login"] in blocked_logins:
                continue
            slug = login_to_slug.get(meta["login"]) or slugify(meta["login"])
            base = slug
            n = 2
            while slug.lower() in used_slugs and login_to_slug.get(meta["login"]) != slug:
                slug = (base[: 12 - len(str(n))] + str(n))[:12]
                n += 1
            picks.append(
                {
                    "login": meta["login"],
                    "title": meta["title"],
                    "contested": meta["contested"],
                    "dests": meta["dests"][:8],
                    "slug": slug,
                }
            )
            used_slugs.add(slug.lower())
            if len(picks) >= 8:
                break

    print(f"picks={len(picks)}")
    for p in picks:
        print(
            f"  contested={p['contested']} @{p['login']} → {p['slug']} | {p['title'][:40]}"
        )

    # --- Креативы: next tXX ---
    cre_ws = ss.worksheet("Креативы")
    cre_vals = cre_ws.get_all_values()
    cre_h = cre_vals[0]
    print("Креативы header:", cre_h)
    tx_codes = next_tx_codes(cre_vals, len(TEXTS))
    print("tx_codes:", tx_codes)

    # detect columns for creatives
    def cre_col(*names: str) -> int | None:
        for n in names:
            if n in cre_h:
                return cre_h.index(n)
        return None

    i_code = cre_col("код", "id", "tx") or 0
    i_type = cre_col("тип", "type")
    i_text = cre_col("содержимое", "текст", "text", "copy")
    i_emoji = cre_col("эмодзи", "emoji")
    i_date = cre_col("дата", "date")
    i_note = cre_col("заметка", "note", "комментарий")

    cre_new = []
    for code, text in zip(tx_codes, TEXTS):
        row = [""] * len(cre_h)
        row[i_code] = code
        if i_type is not None:
            row[i_type] = "текст"
        if i_text is not None:
            row[i_text] = text
        if i_emoji is not None:
            row[i_emoji] = "нет"
        if i_date is not None:
            row[i_date] = date.today().isoformat()
        if i_note is not None:
            row[i_note] = f"contested-vpn-pack {date.today().isoformat()}; без правок"
        cre_new.append(row)

    # --- upsert Слаги ---
    slug_new = []
    for p in picks:
        if p["login"] in login_to_slug and login_to_slug[p["login"]]:
            # ensure we use sheet slug
            p["slug"] = login_to_slug[p["login"]]
            continue
        tip_s = "канал"
        slug_new.append(
            [
                p["login"],
                p["slug"],
                tip_s,
                f"contested-vpn-pack {date.today().isoformat()}; contested={p['contested']}",
            ]
            if "заметка" not in si_slug
            else None
        )
        # rebuild by header
    slug_new = []
    for p in picks:
        if p["login"] in login_to_slug and login_to_slug[p["login"]]:
            p["slug"] = login_to_slug[p["login"]]
            continue
        row = [""] * len(slug_h)
        row[si_slug["логин"]] = p["login"]
        row[si_slug["slug"]] = p["slug"]
        if "тип" in si_slug:
            row[si_slug["тип"]] = "канал"
        if "заметка" in si_slug:
            row[si_slug["заметка"]] = (
                f"contested-vpn-pack {date.today().isoformat()}; contested={p['contested']}"
            )
        slug_new.append(row)

    # --- VPN-сервисы ---
    inv = ss.worksheet("VPN-сервисы").get_all_values()
    inv_h = inv[0]
    inv_logins = set()
    if "Логин" in inv_h:
        li = inv_h.index("Логин")
        inv_logins = {
            (r[li] if len(r) > li else "").lstrip("@").lower() for r in inv[1:]
        }
    inv_new = []
    for p in picks:
        if p["login"] in inv_logins:
            continue
        row = [""] * len(inv_h)
        if "Тип" in inv_h:
            row[inv_h.index("Тип")] = "Канал"
        if "Название" in inv_h:
            row[inv_h.index("Название")] = p["title"] or p["login"]
        if "Логин" in inv_h:
            row[inv_h.index("Логин")] = p["login"]
        if "Ссылка" in inv_h:
            row[inv_h.index("Ссылка")] = f"https://t.me/{p['login']}"
        inv_new.append(row)

    # --- Связки ---
    sv_rows = []
    codes = []
    for p in picks:
        for tx, text in zip(tx_codes, TEXTS):
            sp = f"tga_c_x_{tx}_s_{p['slug']}_eur"
            if sp in existing_sp:
                print(f"SKIP existing {sp}")
                continue
            codes.append(sp)
            promote = f"https://t.me/surfvpn?start={sp}"
            note = (
                f"contested-vpn-pack; @{p['login']}; contested={p['contested']}; "
                f"CPM/budget/daily €5; tx={tx}"
            )
            row_map = {
                "start_param": sp,
                "ad_id": "",
                "ads_url": "",
                "cab": "eur",
                "pl": "c",
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
            existing_sp.add(sp)

    # write sheet
    if cre_new:
        cre_ws.append_rows(cre_new, value_input_option="USER_ENTERED")
    if slug_new:
        slug_ws.append_rows(slug_new, value_input_option="USER_ENTERED")
    if inv_new:
        ss.worksheet("VPN-сервисы").append_rows(
            inv_new, value_input_option="USER_ENTERED"
        )
    if sv_rows:
        sv_ws.append_rows(sv_rows, value_input_option="USER_ENTERED")

    print(
        f"wrote creatives={len(cre_new)} slugs={len(slug_new)} "
        f"inv={len(inv_new)} svyazki={len(sv_rows)}"
    )

    OUT_CODES.write_text("\n".join(codes) + "\n", encoding="utf-8")

    # markdown brief
    lines = [
        f"# Contested VPN pack — {date.today().isoformat()}",
        "",
        f"**{len(codes)} связок** = {len(picks)} каналов × {len(TEXTS)} текстов. "
        f"`cr=x`, `scope=s`, `_eur`, CPM/budget/daily **€5**, статус `к заливке`.",
        "",
        "Коды для админки: [`tgads-contested-vpn-pack-codes.txt`](tgads-contested-vpn-pack-codes.txt)",
        "",
        "```bash",
        "python общее/scripts/export_tgads_admin_campaigns.py",
        "```",
        "",
        "## Площадки",
        "",
        "| login | slug | contested | title |",
        "|---|---|---:|---|",
    ]
    for p in picks:
        lines.append(
            f"| @{p['login']} | `{p['slug']}` | {p['contested']} | {p['title'][:50]} |"
        )
    lines += ["", "## Тексты", ""]
    for tx, text in zip(tx_codes, TEXTS):
        lines.append(f"- **{tx}** ({len(text)} симв.): {text}")
    lines += [
        "",
        "## Админка",
        "",
        f"Вставить **{len(codes)}** строк (одна = название и код кампании) "
        "в Marketing Panel → промокоды/кампании.",
        "После вставки — в Связках `промокод в админке=добавлен`, затем Create Ad.",
        "",
        "### Коды",
        "",
        "```",
        *codes,
        "```",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_CODES}")
    print(f"wrote {OUT_MD}")
    print(f"ADMIN count={len(codes)}")


if __name__ == "__main__":
    main()
