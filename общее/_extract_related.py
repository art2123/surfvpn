# -*- coding: utf-8 -*-
"""Pull support / sister channels / chats / bots from t.me descriptions."""
from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from collections import defaultdict
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
    "Поддержка",
    "Связанные каналы",
    "Чаты",
    "Боты",
]

SKIP_MENTIONS = {
    "botfather", "gif", "stickers", "telegram", "durov", "boost", "premium",
    "gmail", "google", "youtube", "instagram", "twitter", "facebook",
}
AD_HINT = re.compile(
    r"(реклам|сотруднич|менеджер|по рекламе|ads?\b|\bad\b|pr\b|предложка|"
    r"для связи|для предложений|advert|reklama|подбор)",
    re.I,
)
SUP_HINT = re.compile(r"(поддерж|support|help|техподдерж|служба забот|разбан|помощ)", re.I)
CHAT_HINT = re.compile(r"(чат|chat|community|комьюнити|форум|обсужд)", re.I)
BOT_HINT = re.compile(r"(бот|bot|подключить|купить доступ|купить vpn|кабинет)", re.I)
CHAN_HINT = re.compile(r"(канал|новост|news|отзыв|статус|health|live)", re.I)
AD_LOGIN = re.compile(r"(reklama|advert|_ads|adbot|ads_|_ad$)", re.I)

MENTION_RE = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z][A-Za-z0-9_]{3,})|@([A-Za-z][A-Za-z0-9_]{3,})",
    re.I,
)
NON_TG = re.compile(
    r"(teletype\.in|boosty\.to|youtube\.com|youtu\.be|vk\.com|instagram\.com|"
    r"gosuslugi|cutt\.ly|clck\.ru|rknn\.|github\.com|apps\.apple\.com)",
    re.I,
)


def parse_count(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ").strip())


def is_dummy_desc(desc: str) -> bool:
    d = (desc or "").strip()
    return (
        d.startswith("If you have Telegram")
        or d.startswith("You can view and join")
        or d.startswith("You can contact")
        or not d
    )


def parse_html_card(login: str, html_s: str) -> dict:
    title = ""
    m = re.search(r'og:title" content="([^"]+)"', html_s)
    if m:
        title = html.unescape(m.group(1).replace(" — Telegram", "").strip())
        title = re.sub(r"\s*—\s*Telegram$", "", title)
    desc = ""
    m = re.search(r'class="tgme_page_description"[^>]*>(.*?)</div>', html_s, re.S)
    if m:
        raw = re.sub(r"<br\s*/?>", "\n", m.group(1), flags=re.I)
        raw = re.sub(r"<[^>]+>", " ", raw)
        desc = html.unescape(re.sub(r"\s+", " ", raw)).strip()
    if is_dummy_desc(desc):
        m = re.search(r'class="tgme_channel_info_description"[^>]*>(.*?)</div>', html_s, re.S)
        if m:
            raw = re.sub(r"<br\s*/?>", "\n", m.group(1), flags=re.I)
            raw = re.sub(r"<a [^>]*>(.*?)</a>", r" \1 ", raw)
            raw = re.sub(r"<[^>]+>", " ", raw)
            desc = html.unescape(re.sub(r"\s+", " ", raw)).strip()
    if is_dummy_desc(desc):
        m = re.search(r'og:description" content="([^"]*)"', html_s)
        if m:
            desc = html.unescape(m.group(1).replace("\t", " "))
    extras = [parse_count(x) for x in re.findall(r'class="tgme_page_extra">([^<]+)', html_s)]
    extra = ""
    for cand in extras:
        if re.search(r"monthly|subscribers|members", cand, re.I):
            extra = cand
            break
    if not extra:
        # /s/ counter: "1 234 subscribers"
        counts = re.findall(
            r'class="tgme_channel_info_counter_value">([^<]+)</span>\s*'
            r'<span class="tgme_channel_info_counter_type">([^<]+)',
            html_s,
        )
        parts = []
        for val, typ in counts:
            parts.append(f"{parse_count(val)} {typ.strip()}")
        extra = ", ".join(parts)
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
        "desc": (desc or "")[:800],
        "extra": extra,
        "kind": kind,
        "html_ok": True,
    }


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode("utf-8", "ignore")


def fetch_card(login: str) -> dict:
    login = login.lstrip("@")
    try:
        html_s = fetch_url(f"https://t.me/{login}")
        card = parse_html_card(login, html_s)
        if is_dummy_desc(card.get("desc") or "") or not card.get("extra"):
            try:
                html_s2 = fetch_url(f"https://t.me/s/{login}")
                card2 = parse_html_card(login, html_s2)
                if not is_dummy_desc(card2.get("desc") or "") or card2.get("extra"):
                    if is_dummy_desc(card.get("desc") or ""):
                        card["desc"] = card2.get("desc") or card.get("desc")
                    if card2.get("title") and not card.get("title"):
                        card["title"] = card2["title"]
                    if card2.get("extra"):
                        card["extra"] = card2["extra"]
                        card["kind"] = card2["kind"]
            except Exception:
                pass
        return card
    except Exception as e:
        return {"login": login, "error": str(e)[:120]}


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
    d = re.sub(r"[^\d]", "", s or "")
    return int(d) if d else 0


def extract_mentions(desc: str, self_login: str) -> dict[str, list[str]]:
    found = {"support": [], "channels": [], "chats": [], "bots": []}
    if not desc:
        return found
    text = html.unescape(desc.replace("&#33;", "!"))
    text = re.sub(r"https?://(?!(?:t\.me|telegram\.me)/)\S+", " ", text)
    text = NON_TG.sub(" ", text)
    seen = set()
    for m in MENTION_RE.finditer(text):
        login = (m.group(1) or m.group(2) or "").lower()
        if not login or login == self_login or login in SKIP_MENTIONS:
            continue
        if login in seen:
            continue
        if login in {"addlist", "share", "joinchat", "s", "plus", "boost", "pwoodo", "nbbadm", "maxvpnboss"}:
            continue
        seen.add(login)
        prev = text[max(0, m.start() - 50):m.start()].lower()
        ctx = prev
        if AD_LOGIN.search(login) or AD_HINT.search(ctx):
            continue
        if (
            SUP_HINT.search(login)
            or any(x in login for x in ("support", "_help", "helpdesk", "_sup", "supp"))
            or re.search(r"(техподдерж|поддержк|support|help)\s*[:\-—]?\s*$", prev)
        ):
            found["support"].append(login)
        elif CHAT_HINT.search(login) or login.endswith("chat") or re.search(
            r"(чат|chat|community|комьюнити|форум)\s*[:\-—]?\s*$", prev
        ):
            found["chats"].append(login)
        elif login.endswith(("bot", "robot")) or re.search(
            r"(бот|bot|подключить|купить)\s*[:\-—]?\s*$", prev
        ):
            if any(x in login for x in ("support", "help", "sup")):
                found["support"].append(login)
            else:
                found["bots"].append(login)
        else:
            found["channels"].append(login)
    return found


def links(logins: list[str]) -> str:
    return " | ".join(f"https://t.me/{x}" for x in logins)


def type_from_card(card: dict, login: str, role: str) -> str:
    kind = card.get("kind")
    if kind == "chat" or "chat" in login:
        return "Чат"
    if role == "support" or any(x in login for x in ("support", "help", "sup")):
        return "Бот поддержки" if (kind == "bot" or login.endswith(("bot", "robot"))) else "Канал"
    if kind == "bot" or login.endswith(("bot", "robot")):
        return "Бот"
    if kind == "channel":
        return "Канал"
    if login.endswith(("bot", "robot")):
        return "Бот"
    return "Канал"


def should_keep_new(login: str, card: dict, src_tab: str) -> bool:
    title = card.get("title") or ""
    desc = card.get("desc") or ""
    extra = card.get("extra") or ""
    blob = f"{title} {desc} {login}"
    if card.get("error"):
        return False
    if ARABIC.search(blob):
        return False
    if re.search(r"(mtproto|ключи для|warp plus|free proxy|фильтршкен)", blob, re.I):
        return False
    if AD_LOGIN.search(login):
        return False
    if title.lower().startswith("telegram: contact"):
        return False
    looks_entity = bool(
        card.get("kind") in {"channel", "bot", "chat"}
        or re.search(r"monthly|subscribers|members", extra, re.I)
        or login.endswith(("bot", "robot"))
        or "chat" in login
    )
    if not looks_entity:
        return False
    if login in {"boost", "job_code", "pardonkdbot", "jobatlanta"}:
        return False
    # skip tiny review/ghost channels unless support/chat
    subs, mau = parse_audience(extra)
    n = to_num(subs) or to_num(mau)
    if n and n < 400 and "chat" not in login and not login.endswith(("bot", "robot")):
        return False
    return True


def sort_key(it: dict) -> tuple:
    order = {"Канал": 0, "Чат": 1, "Бот": 2, "Бот поддержки": 3}
    return (order.get(it.get("type"), 9), -to_num(it.get("subs")), -to_num(it.get("mau")))


def write_tab(ss, title: str, items: list, index: int) -> None:
    try:
        ws = ss.worksheet(title)
        ss.del_worksheet(ws)
    except gspread.WorksheetNotFound:
        pass
    rows = [HEADER]
    for it in items:
        login = it["login"].lstrip("@")
        rel = it.get("related") or {}
        rows.append(
            [
                it.get("type") or "",
                html.unescape(it.get("name") or login),
                f"@{login}",
                it.get("url") or f"https://t.me/{login}",
                it.get("subs") or "",
                it.get("mau") or "",
                it.get("creatives") or "",
                it.get("advertisers") or "",
                links(rel.get("support") or []),
                links(rel.get("channels") or []),
                links(rel.get("chats") or []),
                links(rel.get("bots") or []),
            ]
        )
    cols = len(HEADER)
    ws = ss.add_worksheet(title=title, rows=max(len(rows) + 15, 40), cols=cols, index=index)
    ws.update(rows, value_input_option="USER_ENTERED")
    ws.resize(rows=len(rows) + 4, cols=cols)
    ws.freeze(rows=1)
    bg = {"red": 0.15, "green": 0.35, "blue": 0.55} if title.startswith("VPN") else {
        "red": 0.25, "green": 0.4, "blue": 0.28
    }
    ws.format(
        "A1:L1",
        {
            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
            "backgroundColor": bg,
        },
    )
    try:
        ws.columns_auto_resize(0, cols)
    except Exception:
        pass


def load_tab(ws) -> list[dict]:
    raw = ws.get_all_values()
    items = []
    for r in raw[1:]:
        r = r + [""] * 12
        login = r[2].lstrip("@").lower()
        if not login or login in {"boost", "job_code", "pardonkdbot", "jobatlanta", "vpreviews", "rawivpn_reviews", "ghostvpn"}:
            continue
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
                "related": {"support": [], "channels": [], "chats": [], "bots": []},
            }
        )
    return items


def main() -> None:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    ss = gspread.authorize(
        Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    ).open_by_key(SHEET_ID)
    vpn_items = load_tab(ss.worksheet("VPN-сервисы"))
    other_items = load_tab(ss.worksheet("Все остальное"))
    all_items = [("VPN-сервисы", it) for it in vpn_items] + [("Все остальное", it) for it in other_items]
    existing = {it["login"] for _, it in all_items}

    def stale(lg: str) -> bool:
        c = cache.get(lg) or {}
        if not c.get("html_ok"):
            return True
        return is_dummy_desc(c.get("desc") or "") or not (c.get("extra") or c.get("title"))

    need = [it["login"] for _, it in all_items if stale(it["login"])]
    print("refresh", len(need))
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_card, lg): lg for lg in need}
        for i, fut in enumerate(as_completed(futs), 1):
            card = fut.result()
            cache[card["login"]] = card
            if i % 40 == 0:
                print(" ", i)
            time.sleep(0.04)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    discovered = []  # (role, login, src_login, src_tab)
    for tab, it in all_items:
        card = cache.get(it["login"], {})
        # fill stats/names
        subs, mau = parse_audience(card.get("extra") or "")
        if subs:
            it["subs"] = subs
        if mau:
            it["mau"] = mau
        if card.get("title") and not str(card["title"]).lower().startswith("telegram: contact"):
            it["name"] = html.unescape(card["title"])
        kind = card.get("kind")
        if kind == "chat":
            it["type"] = "Чат"
        rel = extract_mentions(card.get("desc") or "", it["login"])
        it["related"] = rel
        if it["type"] != "Канал":
            # user asked to walk channels; still keep mentions if present
            pass
        for role, logins in rel.items():
            for lg in logins:
                discovered.append((role, lg, it["login"], tab))

    # fetch discovered
    new_logins = sorted({lg for _, lg, _, _ in discovered if lg not in existing})
    print("new mentions", len(new_logins))
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_card, lg): lg for lg in new_logins}
        for fut in as_completed(futs):
            card = fut.result()
            cache[card["login"]] = card
            time.sleep(0.04)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    added = {"VPN-сервисы": [], "Все остальное": []}
    for role, lg, src, src_tab in discovered:
        if lg in existing:
            continue
        card = cache.get(lg, {})
        if not should_keep_new(lg, card, src_tab):
            print("skip", lg, "from", src, card.get("title"))
            continue
        existing.add(lg)
        typ = type_from_card(card, lg, role)
        subs, mau = parse_audience(card.get("extra") or "")
        name = html.unescape(card.get("title") or lg)
        dest = "VPN-сервисы" if src_tab == "VPN-сервисы" else "Все остальное"
        # media sister channels stay in other; support of media can stay in other
        row = {
            "type": typ,
            "name": name,
            "login": lg,
            "url": f"https://t.me/{lg}",
            "subs": subs,
            "mau": mau,
            "creatives": "",
            "advertisers": "",
            "related": {"support": [], "channels": [], "chats": [], "bots": []},
            "from": src,
            "role": role,
        }
        added[dest].append(row)
        safe = f"ADD {dest} {typ} @{lg} from @{src} ({role}) {subs or mau}"
        print(safe.encode("cp1251", "replace").decode("cp1251"))

    vpn_items.extend(added["VPN-сервисы"])
    other_items.extend(added["Все остальное"])
    vpn_items.sort(key=sort_key)
    other_items.sort(key=sort_key)

    write_tab(ss, "VPN-сервисы", vpn_items, 0)
    write_tab(ss, "Все остальное", other_items, 1)
    print(
        "VPN",
        len(vpn_items),
        "OTHER",
        len(other_items),
        "added",
        len(added["VPN-сервисы"]) + len(added["Все остальное"]),
    )
    # dump related for channels
    print("--- CHANNEL RELATED ---")
    for it in vpn_items + other_items:
        if it["type"] != "Канал":
            continue
        rel = it.get("related") or {}
        if any(rel.values()):
            line = f"@{it['login']}: sup={rel['support']} ch={rel['channels']} chat={rel['chats']} bot={rel['bots']}"
            print(line.encode("cp1251", "replace").decode("cp1251"))


if __name__ == "__main__":
    main()
