# -*- coding: utf-8 -*-
"""Собирает таблицу каналов/ботов для импорта в Google Sheets."""

from __future__ import annotations

import csv
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLNC = ROOT / "blnc" / "blnc_docs_1"
SHEETS = BLNC / "sheets-tgads"
ADS = BLNC / "Anitgravity projects" / "tg ads report creator"
OUT_DIR = Path(__file__).resolve().parent

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
JUNK_USERNAMES = {
    "stickers",
    "emojidevbot",
    "verificationcodes",
    "getemojiidbot",
    "tg_analytics_bot",
    "fkwalletio_bot",
    "moverstoresupportbot",
    "moverstorechatbot",
    "adwordsshopchatbot",
    "shop_ads_bot",
    "accs_postman_bot",
    "smsfast_oauth_bot",
    "onlinesim_en_bot",
    "mail_top_shop",
    "petrg12333",
}
OWN_BRANDS = ("blanc", "fck_rkn", "fckrkn")
SUPPORT_TOKENS = {
    "support", "sup", "help", "helper", "assistant", "поддержка", "техподдерж",
}

PROCESS_VPNS = [
    "okvpn", "itxvpn", "dedvpn", "vpnrus", "GruVPN", "vpngen", "vpn_get", "vezarys",
    "sotavpn", "prayvpn", "vpnUral", "infvpnru", "shpunvpn", "vpnbelka", "green_vpn",
    "LagomVPN", "vpndvizh", "dancevpn", "inviz_vpn", "paper_vpn", "vpnbober", "net4ebur",
    "notvpn_ru", "ullubiytg", "siriusvpn", "itopvpn_ru", "followNeo", "altvpncom",
    "seed4me_ru", "hitvpnapp", "VPNsafeRu", "vpnwizard", "hitvpn_news", "vpnsatoshi",
    "vpn_liberty", "aveselov_ru", "vpn_vasilek", "vpn_chel_news", "planetvpnru",
    "vpn_one_click", "out_vpn_news", "cyberteamVPN", "BrowsecVPNru", "vpnforrussia",
    "internetoved", "fastestvpnrus", "lantern_russia", "vpnfreeservers", "VPN_GROZA_NEWS",
    "avpnbot_channel", "vpn_wireguard1", "your_vpn_channel", "VPN_Raketa_news",
    "Proton_VPN_News", "ctrl_vpn_channel", "wireguard_vpn_free", "amnezia_vpn_news_ru",
    "highloadofficial", "wireguardsiberia", "unitechcorporation", "TurboVpnOfficial_RU",
    "VPN_WireGuard_Channel", "vpnproxymaster_russia", "matreshkavpn_official",
    "hidemyname_ru", "klassvpn", "vpnaxonews", "uboostrussia", "opengate_community",
    "planetavpna", "highloadvpn", "kovalenkovpns", "YouFastVPN", "vmvapp", "idea_vpn_news",
    "atelecomprovpn", "hitvpn_bitbot", "proxyLine_bot", "proxylinenet", "vanyavpn",
    "VanyaSupportBot", "BEBRA_VPN_BOT", "raytun_vpn_bot", "VPN_Raketa_bot", "HiiiitVpnbot",
    "ChikChirikVPNbot", "VPNPPLBot", "synatra_bot", "volgavpnbot",
]


def clean_login(value: str) -> str:
    if not value:
        return ""
    value = re.sub(r"^https?://t\.me/", "", value.strip(), flags=re.I)
    return value.lstrip("@").split("?")[0].split("/")[0].strip()


def compact_num(value) -> int | None:
    if value is None or value == "":
        return None
    raw = str(value).strip().replace("\xa0", " ")
    if not raw or raw.upper() in {"N/A", "NA", "ERROR", "NONE"}:
        return None
    raw = raw.replace(" ", "").replace(",", ".")
    mult = 1
    if raw.upper().endswith("K"):
        mult = 1_000
        raw = raw[:-1]
    elif raw.upper().endswith("M"):
        mult = 1_000_000
        raw = raw[:-1]
    raw = re.sub(r"[^\d.]", "", raw)
    if not raw:
        return None
    try:
        return int(float(raw) * mult)
    except ValueError:
        return None


def fmt_num(value: int | None) -> str:
    if value is None:
        return ""
    return f"{value:,}".replace(",", " ")


def looks_like_bot(login: str, name: str = "") -> bool:
    login_l = login.lower()
    return login_l.endswith("bot") or login_l.endswith("robot") or "бот" in (name or "").lower()


def looks_like_support(login: str, name: str = "") -> bool:
    text = f"{name or ''} {login or ''}".lower()
    tokens = set(re.split(r"[_\-\s\.]", text))
    if tokens & SUPPORT_TOKENS:
        return True
    return any(kw in login.lower() for kw in ("support", "helper") if len(kw) >= 5)


def is_junk(login: str, name: str = "", row_type: str = "") -> bool:
    if not login:
        return True
    login_l = login.lower()
    if login_l in JUNK_USERNAMES or login.isdigit():
        return True
    blob = re.sub(r"[_\-\s\.]", "", f"{name} {login}".lower())
    if any(b.replace("_", "") in blob for b in OWN_BRANDS):
        return True
    return row_type in {"User", "Saved Messages"}


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def add_entity(store: dict, login: str, **kwargs):
    login = clean_login(login)
    if not login:
        return
    key = login.lower()
    item = store.setdefault(
        key,
        {
            "login": login,
            "type": "",
            "name": "",
            "subscribers": None,
            "mau": None,
        },
    )
    if len(login) > len(item["login"]):
        item["login"] = login
    if kwargs.get("type") and not item["type"]:
        item["type"] = kwargs["type"]
    name = kwargs.get("name")
    if name and (not item["name"] or len(name) > len(item["name"])):
        item["name"] = name
    for field in ("subscribers", "mau"):
        val = kwargs.get(field)
        if val is not None and (item[field] is None or val > item[field]):
            item[field] = val


def classify(item: dict) -> str:
    login, name = item["login"], item["name"]
    if item["type"] == "Канал":
        return "Канал"
    if looks_like_support(login, name) or item["type"] == "Бот поддержки":
        return "Бот поддержки"
    if item["type"] == "Бот" or looks_like_bot(login, name):
        return "Бот"
    return "Канал"


def fetch_tg_page(login: str, is_bot: bool) -> dict:
    url = f"https://t.me/{login}" if is_bot else f"https://t.me/s/{login}"
    out = {"name": "", "subscribers": None, "mau": None}
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except Exception:
        if not is_bot:
            return fetch_tg_page(login, True)
        return out

    title = re.search(r'og:title"\s+content="([^"]+)"', html)
    if not title:
        title = re.search(r'class="tgme_page_title"[^>]*>\s*<span[^>]*>([^<]+)', html)
    if title:
        out["name"] = re.sub(r"\s+", " ", title.group(1)).strip()

    mau = re.search(r">([\d\s\.,MK]+)monthly users<", html, re.I)
    if mau:
        out["mau"] = compact_num(mau.group(1))
    subs = re.search(r"([\d\s\.,MK]+)subscribers", html, re.I)
    if not subs:
        subs = re.search(r">([\d\s\.,MK]+)subscribers<", html, re.I)
    if subs:
        out["subscribers"] = compact_num(subs.group(1))
    return out


def collect() -> dict:
    store: dict[str, dict] = {}

    chats = ADS / "telegram_chats.csv"
    if chats.exists():
        for row in load_csv(chats):
            login = clean_login(row.get("username", ""))
            row_type = (row.get("type") or "").strip()
            name = (row.get("name") or "").strip()
            if is_junk(login, name, row_type) or row_type not in {"Bot", "Channel", "Supergroup"}:
                continue
            kind = "Канал" if row_type in {"Channel", "Supergroup"} else (
                "Бот поддержки" if looks_like_support(login, name) else "Бот"
            )
            add_entity(
                store, login, type=kind, name=name,
                mau=compact_num(row.get("bot_active_users", "")),
            )

    requested = SHEETS / "requested_bot_user_counts.csv"
    if requested.exists():
        for row in load_csv(requested):
            login = clean_login(row.get("Логин", ""))
            if is_junk(login):
                continue
            kind = "Бот поддержки" if looks_like_support(login) else "Бот"
            add_entity(store, login, type=kind, mau=compact_num(row.get("Численность", "")))

    for username in PROCESS_VPNS:
        login = clean_login(username)
        if is_junk(login):
            continue
        kind = "Бот поддержки" if looks_like_support(login) else (
            "Бот" if looks_like_bot(login) else "Канал"
        )
        add_entity(store, login, type=kind)

    bots_from_desc = SHEETS / "all_bots_from_channel_descriptions.csv"
    if bots_from_desc.exists():
        for row in load_csv(bots_from_desc):
            channel = clean_login(row.get("Канал", ""))
            bot = clean_login(row.get("Бот", ""))
            marker = (row.get("Маркер поддержки") or "").lower()
            if channel and not is_junk(channel):
                add_entity(store, channel, type="Канал")
            if bot and not is_junk(bot):
                kind = "Бот поддержки" if marker or looks_like_support(bot) else "Бот"
                add_entity(store, bot, type=kind)

    support_final = SHEETS / "support_bots_from_channel_descriptions_final.csv"
    if support_final.exists():
        for row in load_csv(support_final):
            channel = clean_login(row.get("Канал", ""))
            bot = clean_login(row.get("Бот поддержки", "") or row.get("Бот", ""))
            if channel and not is_junk(channel):
                add_entity(store, channel, type="Канал")
            if bot and not is_junk(bot):
                add_entity(store, bot, type="Бот поддержки")

    return store


def refresh_live(store: dict) -> None:
    items = list(store.values())
    total = len(items)
    print(f"Обновляю цифры с t.me по {total} площадкам...")
    done = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(fetch_tg_page, item["login"], classify(item) != "Канал"): item
            for item in items
        }
        for fut in as_completed(futures):
            item = futures[fut]
            done += 1
            try:
                live = fut.result()
            except Exception as exc:
                print(f"  [{done}/{total}] @{item['login']} ошибка: {exc}")
                continue
            if live.get("name") and not item["name"]:
                item["name"] = live["name"]
            elif live.get("name") and len(live["name"]) > len(item["name"]):
                item["name"] = live["name"]
            if live.get("subscribers") is not None:
                item["subscribers"] = live["subscribers"]
            if live.get("mau") is not None:
                item["mau"] = live["mau"]
            if done % 25 == 0 or done == total:
                print(f"  {done}/{total}")
            time.sleep(0.05)


def main():
    store = collect()
    refresh_live(store)

    rows = []
    for item in store.values():
        kind = classify(item)
        rows.append({
            "Тип": kind,
            "Название": item["name"],
            "Логин": f"@{item['login']}",
            "Ссылка": f"https://t.me/{item['login']}",
            "Подписчики": fmt_num(item["subscribers"]),
            "Месячная аудитория": fmt_num(item["mau"]),
        })

    type_order = {"Канал": 0, "Бот": 1, "Бот поддержки": 2}

    def sort_key(row):
        subs = compact_num(row["Подписчики"]) or 0
        mau = compact_num(row["Месячная аудитория"]) or 0
        return (type_order.get(row["Тип"], 9), -(subs or mau), row["Логин"].lower())

    rows.sort(key=sort_key)

    out = OUT_DIR / "tg-ads-каналы-и-боты.csv"
    fields = ["Тип", "Название", "Логин", "Ссылка", "Подписчики", "Месячная аудитория"]
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    counts = {}
    for row in rows:
        counts[row["Тип"]] = counts.get(row["Тип"], 0) + 1
    print(f"Готово: {len(rows)} строк -> {out}")
    for kind in ("Канал", "Бот", "Бот поддержки"):
        print(f"  {kind}: {counts.get(kind, 0)}")


if __name__ == "__main__":
    main()
