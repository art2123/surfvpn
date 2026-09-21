# -*- coding: utf-8 -*-
"""Audience check for contested VPN pack platforms (targets)."""
from __future__ import annotations

import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
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
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
CTX = ssl.create_default_context()


def compact_num(raw: str) -> int | None:
    s = raw.replace("\xa0", " ").replace(" ", "").replace(",", ".")
    if not s:
        return None
    mult = 1
    if s.upper().endswith("K"):
        mult = 1_000
        s = s[:-1]
    elif s.upper().endswith("M"):
        mult = 1_000_000
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        digits = re.sub(r"\D", "", raw)
        return int(digits) if digits else None


def load_codes() -> set[str]:
    out: set[str] = set()
    for name in (
        "tgads-contested-vpn-pack-codes.txt",
        "tgads-contested-vpn-pack2-codes.txt",
    ):
        p = ROOT / name
        if p.exists():
            out.update(x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip())
    return out


def telemetr_subs(login: str, cookie: str) -> tuple[int | None, str]:
    url = (
        "https://telemetr.me/api/v1/catalog/channels/search?query="
        + urllib.parse.quote(login)
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Cookie": cookie,
            "Referer": "https://telemetr.me/",
        },
    )
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=25) as resp:
            j = json.loads(resp.read().decode())
    except Exception as exc:
        return None, f"err:{exc}"[:60]
    login_l = login.lower()
    for it in j.get("items") or []:
        un = ((it.get("links") or {}).get("userName") or it.get("username") or "").lower()
        if un != login_l:
            continue
        st = it.get("statistics") or {}
        count = (st.get("subscribers") or {}).get("count")
        if isinstance(count, dict):
            count = count.get("total")
        if count is None:
            count = (st.get("participants") or {}).get("count")
            if isinstance(count, dict):
                count = count.get("total")
        return (int(count) if count is not None else None), "telemetr"
    return None, "miss"


def tme_stats(login: str) -> tuple[int | None, int | None]:
    req = urllib.request.Request(f"https://t.me/{login}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=20) as resp:
            html = resp.read().decode("utf-8", "ignore")
    except Exception:
        return None, None
    mau = None
    subs = None
    m = re.search(r">([\d\s\.,MK]+)monthly users<", html, re.I) or re.search(
        r"([\d\s\.,MK]+)\s*monthly users", html, re.I
    )
    if m:
        mau = compact_num(m.group(1))
    m2 = re.search(r"([\d\s\.,MK]+)\s*subscribers", html, re.I)
    if m2:
        subs = compact_num(m2.group(1))
    m3 = re.search(r"([\d\s\.,MK]+)\s*members", html, re.I)
    if m3 and not subs:
        subs = compact_num(m3.group(1))
    return mau, subs


def main() -> None:
    codes = load_codes()
    ss = gspread.authorize(
        Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    ).open_by_key(SHEET_ID)
    slugs = {
        str(r["slug"]).strip(): str(r["логин"]).strip().lstrip("@")
        for r in ss.worksheet("Слаги").get_all_records()
        if r.get("slug")
    }
    vals = ss.worksheet("Связки").get_all_values()
    h = vals[0]
    idx = {c: i for i, c in enumerate(h)}
    by_login: dict[str, dict] = {}
    for r in vals[1:]:
        while len(r) < len(h):
            r.append("")
        sp = r[idx["start_param"]].strip()
        if sp not in codes:
            continue
        slug = r[idx["slug"]].strip()
        login = slugs.get(slug, slug).lower()
        rec = by_login.setdefault(
            login, {"slug": slug, "statuses": set(), "sps": [], "ad_ids": []}
        )
        rec["statuses"].add(r[idx["статус"]])
        rec["sps"].append(sp)
        if r[idx["ad_id"]].strip():
            rec["ad_ids"].append(r[idx["ad_id"]].strip())

    cookie_map = json.loads(
        (ROOT.parent / "tgads-snapshots/_telemetr_cookies.json").read_text(encoding="utf-8")
    ).get("map") or {}
    cookie = "; ".join(f"{k}={v}" for k, v in cookie_map.items() if v)

    rows = []
    for login, meta in sorted(by_login.items()):
        time.sleep(0.22)
        subs, tsrc = telemetr_subs(login, cookie)
        mau, tsubs = tme_stats(login)
        aud = subs if subs is not None else tsubs
        src = "telemetr" if subs is not None else ("t.me" if tsubs is not None else tsrc)
        metric = "subscribers"
        if aud is None and mau is not None:
            aud = mau
            metric = "mau"
            src = "t.me"
        rows.append(
            {
                "login": login,
                "slug": meta["slug"],
                "aud": aud,
                "metric": metric,
                "src": src,
                "n": len(meta["sps"]),
                "active_n": sum(1 for s in meta["sps"] if True),
                "statuses": ",".join(sorted(meta["statuses"])),
                "mau": mau,
                "tsubs": tsubs,
            }
        )

    print(f"platforms={len(rows)} ads={len(codes)}")
    print()
    print("ALL (sorted by audience asc):")
    for r in sorted(rows, key=lambda x: (x["aud"] is None, x["aud"] or 0)):
        aud = r["aud"] if r["aud"] is not None else "?"
        print(
            f"@{r['login']:28} {aud:>10} {r['metric']:12} [{r['src']:8}] "
            f"n={r['n']} {r['statuses']}"
        )

    print()
    print("=== < 10 000 ===")
    low10 = [r for r in rows if r["aud"] is not None and r["aud"] < 10_000]
    unk = [r for r in rows if r["aud"] is None]
    for r in sorted(low10, key=lambda x: x["aud"]):
        print(f"@{r['login']} {r['aud']} ({r['metric']}) — {r['n']} связок, {r['statuses']}")
    if unk:
        print("unknown:")
        for r in unk:
            print(f"@{r['login']} — {r['n']} связок, {r['statuses']} src={r['src']}")

    print()
    print("=== < 25 000 (includes <10k) ===")
    low25 = [r for r in rows if r["aud"] is not None and r["aud"] < 25_000]
    for r in sorted(low25, key=lambda x: x["aud"]):
        print(f"@{r['login']} {r['aud']} ({r['metric']}) — {r['n']} связок, {r['statuses']}")

    print()
    print("=== >= 25 000 OK to keep ===")
    ok = [r for r in rows if r["aud"] is not None and r["aud"] >= 25_000]
    for r in sorted(ok, key=lambda x: -x["aud"]):
        print(f"@{r['login']} {r['aud']} ({r['metric']}) — {r['n']} связок")


if __name__ == "__main__":
    main()
