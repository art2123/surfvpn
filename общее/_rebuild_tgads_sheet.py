# -*- coding: utf-8 -*-
"""Rebuild Surfvpn - tgads sheet: VPN-сервисы vs Все остальное."""
from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from google.oauth2.service_account import Credentials
import gspread

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "secrets" / "tme_cards.json"
CREDS = r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json"
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
ARABIC = re.compile(r"[\u0600-\u06FF]")
CYR = re.compile(r"[А-Яа-яЁё]")
HEADER = [
    "Тип",
    "Название",
    "Логин",
    "Ссылка",
    "Подписчики",
    "Месячная аудитория",
    "Креативов VPN",
    "VPN-рекламодатели",
]

# Live RU products the English-ToS heuristic would otherwise kill.
RU_KEEP = {
    "need",
    "hitvpnbot",
    "hitvpn_2bot",
    "antizapret_robot",
    "amnezia_premium_support_bot",
    "liberty_sup_bot",
    "lagomvpn",
    "lagomsupport_bot",
    "russes_vpn_bot",
    "kpacu8ovpn_bot",
    "vpn_telegrambot",
    "blancvpn",
    "fck_rkn_bot",
    "papervpnchat",
    "voxiproxy",
    "voxiproxy_bot",
    "obhodi4_bot",
    "vbuste_bot",
    "sotavpnchat",
    "quattrovpn_chat",
    "sota",
    "needapp",
}

CONFIG_LOGINS = {
    "mtproxy4free",
    "esimpsonconnection",
    "potatofreevpn",
    "outlinekeysrobot",
    "generatewarpplusbot",
    "vpndlfkskbot",
    "configplus3_bot",
    "planet_vpn_key_bot",
    "proxifyrubot",
    "outlinevpnfreebot",
    "freevpn2024_bot",
    "eloriumvpn_robot",
    "mustproxy_bot",
    "nekosocksbot",
    "gozarxbot",
}

JUNK_LOGINS = {
    "fkwalletio_bot",
    "podarkitgnft_bot",
    "smsfast_oauth_bot",
    "unlockedapp_bot",
    "velvet_vps_bot",
    "nesimka_bot",
    "vpnsmmbot",
    "gen_vpnbot",
    "wpnabot",
}

MEDIA_LOGINS = {
    "bbbreaking",
    "rhymestg",
    "pravdadirty",
    "exilemusic13",
    "shot_shot",
    "egorikvtg",
    "d_code",
    "cafe_citaty",
    "doktorgpt",
    "sueta_games",
    "juliusspeak",
    "steamfreeru",
    "android1_ru",
    "modsdroid",
    "rustore_games",
    "vrpirate",
    "lampa_channel",
    "zoomerskydostup",
    "kinatvideo",
    "gameofpctg",
    "technoinsider",
}

EXTRA = [
    ("blancvpn", "Канал", "BlancVPN"),
    ("fck_rkn_bot", "Бот", "BlancVPN | Быстрый и надежный VPN"),
    ("papervpnchat", "Чат", "форум Paper VPN"),
    ("technoinsider", "Канал", "Техно Инсайдер"),
    ("sotavpnchat", "Чат", "Sota VPN чат"),
    ("quattrovpn_chat", "Чат", "Quattro VPN чат"),
    ("sota", "Бот", "Sota VPN"),
    ("needapp", "Канал", "Need"),
]

VPN_NAME_RE = re.compile(
    r"(vpn|впн|proxy|прокси|vless|v2ray|amnezia|happ|incy|обход)",
    re.I,
)
CONFIG_HARD = re.compile(
    r"(mtproto|mtproxy|outline\s*key|warp\s*plus|ключи для|vpn ключ|"
    r"happ/incy|v2raytun ключ|раздач[аеи].*конфиг|free\s*proxy)",
    re.I,
)


def parse_count(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ").strip())


def fetch_card(login: str) -> dict:
    login = login.lstrip("@")
    url = f"https://t.me/{login}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", "ignore")
    except Exception as e:
        return {"login": login, "error": str(e)[:120]}
    title = ""
    m = re.search(r'og:title" content="([^"]+)"', html)
    if m:
        title = html.unescape(m.group(1).replace(" — Telegram", "").strip())
    desc = ""
    m = re.search(r'og:description" content="([^"]*)"', html)
    if m:
        desc = m.group(1)
    extras = [parse_count(x) for x in re.findall(r'class="tgme_page_extra">([^<]+)', html)]
    extra = ""
    for cand in extras:
        if re.search(r"monthly|subscribers|members", cand, re.I):
            extra = cand
            break
    if not extra and extras:
        extra = extras[-1]
    kind = "unknown"
    el = extra.lower()
    if "monthly" in el:
        kind = "bot"
    elif "member" in el:
        kind = "chat"
    elif "subscriber" in el:
        kind = "channel"
    return {
        "login": login,
        "title": title,
        "desc": desc[:500],
        "extra": extra,
        "kind": kind,
        "html_ok": True,
    }


def parse_audience(extra: str) -> tuple[str, str]:
    extra = extra or ""
    subs, mau = "", ""
    m = re.search(r"([\d\s\.,]+)\s*monthly", extra, re.I)
    if m:
        mau = parse_count(m.group(1))
    m = re.search(r"([\d\s\.,]+)\s*(subscribers|members)", extra, re.I)
    if m:
        subs = parse_count(m.group(1))
    return subs, mau


def to_num(s: str) -> int:
    if not s:
        return 0
    d = re.sub(r"[^\d]", "", s)
    return int(d) if d else 0


def classify(it: dict, card: dict) -> tuple[str, str]:
    login = it["login"].lower()
    name = it.get("name") or card.get("title") or ""
    desc = card.get("desc") or ""
    blob = f"{name} {desc} {login}"
    typ = it.get("type") or ""

    if login == "technoinsider":
        return "other", "quality-example"
    if login in {"blancvpn", "fck_rkn_bot", "papervpnchat", "sotavpnchat", "quattrovpn_chat"}:
        return "vpn", "quality-example"
    if login in JUNK_LOGINS:
        return "drop", "not-audience"
    if login in CONFIG_LOGINS:
        return "drop", "config-giveaway"
    if ARABIC.search(blob):
        return "drop", "arabic-persian"
    if CONFIG_HARD.search(blob):
        return "drop", "config-giveaway"
    if login in MEDIA_LOGINS:
        return "other", "ru-media"
    if login in RU_KEEP:
        return "vpn", "ru-keep"
    if not CYR.search(f"{name} {desc}") and len(re.findall(r"[A-Za-z]{3,}", f"{name} {desc}")) >= 2:
        return "drop", "english"
    if VPN_NAME_RE.search(blob) or "vpn" in login or "впн" in login or "поддерж" in (typ + name).lower():
        return "vpn", "vpn-product"
    if card.get("kind") == "chat":
        return "vpn", "vpn-chat"
    return "other", "ru-other"


def sheet_row(it: dict) -> list:
    login = it["login"].lstrip("@")
    return [
        it.get("type") or "",
        it.get("name") or login,
        f"@{login}",
        it.get("url") or f"https://t.me/{login}",
        it.get("subs") or "",
        it.get("mau") or "",
        it.get("creatives") or "",
        it.get("advertisers") or "",
    ]


def sort_key(it: dict) -> tuple:
    order = {"Канал": 0, "Чат": 1, "Бот": 2, "Бот поддержки": 3}
    return (order.get(it.get("type"), 9), -to_num(it.get("subs")), -to_num(it.get("mau")))


def write_tab(ss, title: str, items: list, index: int) -> None:
    try:
        ws = ss.worksheet(title)
        ss.del_worksheet(ws)
    except gspread.WorksheetNotFound:
        pass
    rows = [HEADER] + [sheet_row(it) for it in items]
    cols = len(HEADER)
    ws = ss.add_worksheet(title=title, rows=max(len(rows) + 20, 80), cols=cols, index=index)
    ws.update(rows, value_input_option="USER_ENTERED")
    ws.resize(rows=len(rows) + 5, cols=cols)
    ws.freeze(rows=1)
    bg = {"red": 0.15, "green": 0.35, "blue": 0.55} if title.startswith("VPN") else {
        "red": 0.25, "green": 0.4, "blue": 0.28
    }
    ws.format("A1:H1", {
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
        "backgroundColor": bg,
    })
    try:
        ws.columns_auto_resize(0, cols)
    except Exception:
        pass


def main() -> None:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    ss = gspread.authorize(
        Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    ).open_by_key(SHEET_ID)
    old = None
    for name in ("tg-ads-площадки", "VPN-сервисы", "Все остальное"):
        try:
            if name == "tg-ads-площадки":
                old = ss.worksheet(name)
        except gspread.WorksheetNotFound:
            pass
    src = old or ss.sheet1
    raw = src.get_all_values()
    items = []
    seen = set()
    for r in raw[1:]:
        r = r + [""] * 8
        login = r[2].lstrip("@").lower()
        if not login or login in seen:
            continue
        seen.add(login)
        items.append(
            {
                "type": r[0],
                "name": r[1],
                "login": login,
                "url": r[3] or f"https://t.me/{login}",
                "subs": r[4],
                "mau": r[5],
                "creatives": r[6],
                "advertisers": r[7],
            }
        )
    for login, typ, name in EXTRA:
        if login.lower() in seen:
            # refresh names for quality examples
            for it in items:
                if it["login"] == login.lower():
                    it["type"] = typ
                    if not it["name"]:
                        it["name"] = name
            continue
        seen.add(login.lower())
        items.append(
            {
                "type": typ,
                "name": name,
                "login": login.lower(),
                "url": f"https://t.me/{login}",
                "subs": "",
                "mau": "",
                "creatives": "",
                "advertisers": "",
            }
        )

    need = [it["login"] for it in items if it["login"] not in cache or not cache[it["login"]].get("html_ok")]
    print(f"fetch {len(need)}")
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_card, lg): lg for lg in need}
        for i, fut in enumerate(as_completed(futs), 1):
            card = fut.result()
            cache[card["login"]] = card
            if i % 20 == 0:
                print(" ", i)
            time.sleep(0.04)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    buckets = {"vpn": [], "other": [], "drop": []}
    for it in items:
        card = cache.get(it["login"], {})
        bucket, reason = classify(it, card)
        subs, mau = parse_audience(card.get("extra") or "")
        if subs:
            it["subs"] = subs
        if mau:
            it["mau"] = mau
        title = card.get("title") or it["name"]
        it["name"] = title.replace("&amp;", "&")
        kind = card.get("kind")
        if kind == "chat":
            it["type"] = "Чат"
        elif kind == "bot" and not str(it["type"]).startswith("Бот"):
            it["type"] = "Бот"
        elif kind == "channel" and it["type"] not in {"Канал", "Бот", "Бот поддержки"}:
            it["type"] = "Канал"
        it["reason"] = reason
        buckets[bucket].append(it)

    for k in ("vpn", "other"):
        buckets[k].sort(key=sort_key)

    print("VPN", len(buckets["vpn"]), "OTHER", len(buckets["other"]), "DROP", len(buckets["drop"]))
    from collections import Counter

    print("drop", Counter(x["reason"] for x in buckets["drop"]))
    for x in buckets["drop"]:
        print(f"DROP {x['reason']}\t@{x['login']}\t{x['name']}")

    write_tab(ss, "VPN-сервисы", buckets["vpn"], 0)
    write_tab(ss, "Все остальное", buckets["other"], 1)
    keep = {"VPN-сервисы", "Все остальное", "Списки", "Слаги", "Креативы", "Связки"}
    for ws in ss.worksheets():
        if ws.title not in keep:
            ss.del_worksheet(ws)
            print("deleted tab", ws.title)
    print("done")


if __name__ == "__main__":
    main()
