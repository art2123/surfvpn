# -*- coding: utf-8 -*-
"""Find TI-like hybrids: tech + VPN/RKN/blocks in feed."""
from __future__ import annotations

import csv
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0"
OUT = ROOT / "imports"
OUT.mkdir(exist_ok=True)

# Seed logins from TI similar + known VPN-news hybrids + candidates to probe
SEEDS = [
    "technoinsider",
    "sotavpn",
    "dedvpn",
    "legendaryvpn_news",
    "vpn1_news",
    "amnezia_vpn_news_ru",
    "proton_vpn_news",
    "grumarket",
    "fenix_vpn_ru",
    "vpnural",
    "siriusvpn",
    "planetavpna",
    "green_vpn",
    "vezarys",
    "adguardru",
    "amneziavpn",
]

PAT = {
    "vpn": re.compile(r"\bvpn\b|впн", re.I),
    "rkn": re.compile(r"ркн|роскомнадзор", re.I),
    "block": re.compile(r"блокир|обход|белый список|white.?list|замедл|цензур", re.I),
    "tech": re.compile(
        r"технолог|гаджет|нейросет|\bии\b|\bai\b|iphone|android|инновац|стартап|chatgpt|openai",
        re.I,
    ),
}


def fetch_tme(login: str) -> dict:
    url = f"https://t.me/s/{login}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    title_m = re.search(r'og:title" content="([^"]+)', html)
    desc_m = re.search(r'og:description" content="([^"]+)', html)
    extra_m = re.search(r'tgme_page_extra">([^<]+)', html)
    posts = re.findall(r'class="tgme_widget_message_text[^>]*>([\s\S]*?)</div>', html)
    texts = []
    for p in posts[:12]:
        t = re.sub(r"<[^>]+>", " ", p)
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            texts.append(t)
    desc = desc_m.group(1) if desc_m else ""
    blob = (" ".join(texts) + " " + desc).lower()
    flags = [k for k, rx in PAT.items() if rx.search(blob) or rx.search(desc)]
    # hybrid score: need tech AND (vpn|rkn|block)
    has_tech = "tech" in flags or bool(
        re.search(r"технолог|новост.*тех|tech talk|it\b", desc, re.I)
    )
    has_vpnish = bool({"vpn", "rkn", "block"} & set(flags)) or bool(
        re.search(r"vpn|впн|ркн|блокир", desc, re.I)
    )
    # product VPN channel (bio is mainly VPN sell)
    product = bool(
        re.search(r"бот\s*[—\-:]|@\w*vpn|конфиг|outline|vless|подписк", desc, re.I)
    ) and not has_tech
    cls = "other"
    if has_tech and has_vpnish:
        cls = "hybrid"
    elif has_vpnish and product:
        cls = "vpn_product"
    elif has_vpnish:
        cls = "vpn_news"
    elif has_tech:
        cls = "tech_only"
    return {
        "login": login,
        "title": title_m.group(1) if title_m else "",
        "desc": desc[:220],
        "extra": extra_m.group(1).strip() if extra_m else "",
        "flags": flags,
        "class": cls,
        "samples": texts[:3],
    }


def from_native_csv() -> list[str]:
    path = ROOT / "vpn-native-hosts-telemetr.csv"
    logins = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            q = (r.get("качество") or "")
            if q.startswith("исключ"):
                continue
            user = (r.get("username") or "").strip().lstrip("@")
            if not user:
                continue
            cat = (r.get("категории") or "").lower()
            name = (r.get("канал") or "").lower()
            blob = cat + " " + name
            if any(
                x in blob
                for x in (
                    "ит",
                    "наук",
                    "технолог",
                    "osint",
                    "хакер",
                    "блокиров",
                    "кибер",
                )
            ):
                logins.append(user.lower())
    return logins


def main() -> None:
    logins = []
    seen = set()
    for login in SEEDS + from_native_csv():
        login = login.lower().lstrip("@")
        if login in seen:
            continue
        seen.add(login)
        logins.append(login)

    results = []
    for login in logins:
        try:
            results.append(fetch_tme(login))
            print(f"ok @{login} -> {results[-1]['class']} {results[-1]['flags']}")
        except Exception as e:
            print(f"fail @{login}: {e}")
            results.append({"login": login, "class": "error", "err": str(e)})

    hybrids = [r for r in results if r.get("class") == "hybrid"]
    vpn_news = [r for r in results if r.get("class") == "vpn_news"]
    (OUT / "ti_hybrid_scan.json").write_text(
        json.dumps(
            {
                "hybrids": hybrids,
                "vpn_news": vpn_news,
                "all": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("--- HYBRIDS ---")
    for r in hybrids:
        print(f"  @{r['login']}: {r.get('title')} | {r.get('flags')}")
    print("--- VPN_NEWS ---")
    for r in vpn_news:
        print(f"  @{r['login']}: {r.get('title')} | {r.get('flags')}")
    print(f"saved {OUT / 'ti_hybrid_scan.json'} total={len(results)}")


if __name__ == "__main__":
    main()
