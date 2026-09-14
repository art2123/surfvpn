# -*- coding: utf-8 -*-
"""Новые VPN-площадки из TG Ads и CSV-экспортов TGStat/Telemetr.

Источники:
  1) Telegram Ads Spy (публичный API) — кто прямо сейчас крутит TG Ads.
  2) Папка imports/ — CSV/XLSX, выгруженные из каталога посевов TGStat/Telemetr.
  3) Опционально TGSTAT_TOKEN — поиск рекламных постов через TGStat Search API.

Запуск:
  python общее/discover_vpn_ads.py
"""

from __future__ import annotations

import csv
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMPORTS = ROOT / "imports"
SECRETS = ROOT / "secrets"
KNOWN_CSV = ROOT / "tg-ads-каналы-и-боты.csv"
OUT_ALL = ROOT / "tg-ads-обнаруженные.csv"
OUT_NEW = ROOT / "tg-ads-новые.csv"

SPY_BASE = "https://tgadsspy.com/api/v1"
TGSTAT_SEARCH = "https://api.tgstat.ru/posts/search"
UA = "SurfVPN-research/1.0"
PAGE = 50
SLEEP = 1.05
OWN = ("blanc", "fck_rkn", "fckrkn", "surfvpn")
SKIP_LOGINS = {
    "stickers", "gif", "botfather", "spaminfo", "previews", "discussbot", "gamee",
}
MIN_BOT_MAU = 10_000
MIN_CHANNEL_SUBS = 20_000
MAX_CHANNEL_SUBS = 2_000_000
MIN_REACH = 0.06
MAX_REACH = 0.50
LOCAL_BOT_CSVS = [
    ROOT.parent / "blnc" / "blnc_docs_1" / "Anitgravity projects" / "tg ads report creator" / "telegram_chats.csv",
    ROOT.parent / "blnc" / "blnc_docs_1" / "sheets-tgads" / "requested_bot_user_counts.csv",
]
GIVEAWAY_RE = re.compile(
    r"розыгрыш|giveaway|iphone|айфон|выигрыш|выиграй|айпад|macbook|\btesla\b|миллион подпис",
    re.I,
)
OUT_QUALITY = ROOT / "tg-ads-площадки.csv"
LOGIN_RE = re.compile(
    r"(?:@|t\.me/|telegram\.me/)([A-Za-z][A-Za-z0-9_]{4,31})",
    re.I,
)


def clean_login(value: str) -> str:
    if not value:
        return ""
    value = str(value).strip()
    value = re.sub(r"^https?://(t|telegram)\.me/", "", value, flags=re.I)
    login = value.lstrip("@").split("?")[0].split("/")[0].strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", login):
        return ""
    return login


def is_bot(login: str) -> bool:
    login = login.lower()
    return login.endswith("bot") or login.endswith("robot")


def is_own(login: str, name: str = "") -> bool:
    blob = re.sub(r"[_\-\s\.]", "", f"{name} {login}".lower())
    if login.lower() in SKIP_LOGINS:
        return True
    return any(x.replace("_", "") in blob for x in OWN)


def fmt_num(value) -> str:
    if value in (None, "", 0):
        return ""
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(value)


def load_spy_key() -> str:
    env = os.environ.get("TGADSSPY_API_KEY", "").strip()
    if env:
        return env
    path = SECRETS / "tgadsspy.key"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


class SpyQuarantine(RuntimeError):
    pass


def http_json(url: str, timeout: int = 30, api_key: str = "") -> dict:
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if api_key:
        headers["X-Api-Key"] = api_key
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            plan = resp.headers.get("X-Plan", "")
            body = json.loads(resp.read().decode("utf-8"))
            if plan and isinstance(body, dict):
                body.setdefault("_plan", plan)
            return body
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        if exc.code == 429 and "identity_quarantined" in detail:
            raise SpyQuarantine("tgadsspy identity_quarantined 24h") from exc
        if exc.code == 429:
            wait = 8
            try:
                wait = max(8, int(json.loads(detail).get("retryAfter") or 8))
            except Exception:
                pass
            wait = min(wait, 30)
            print(f"  429, жду {wait}с", flush=True)
            time.sleep(wait)
            return http_json(url, timeout=timeout, api_key=api_key)
        raise RuntimeError(f"HTTP {exc.code} {url}: {detail[:300]}") from exc


def spy_pages(path: str, api_key: str, extra: dict | None = None) -> list[dict]:
    items = []
    offset = 0
    plan = "ANON"
    while True:
        params = {"limit": str(PAGE), "offset": str(offset)}
        if extra:
            params.update({k: str(v) for k, v in extra.items() if v not in (None, "")})
        url = f"{SPY_BASE}/{path}?{urllib.parse.urlencode(params)}"
        payload = http_json(url, api_key=api_key)
        plan = payload.get("_plan") or (payload.get("meta") or {}).get("plan") or plan
        batch = payload.get("data") or []
        meta = payload.get("meta") or {}
        items.extend(batch)
        total = meta.get("total")
        print(
            f"    {path} offset={offset} +{len(batch)} (всего {len(items)}"
            f"{f'/{total}' if total else ''}, план {plan})",
            flush=True,
        )
        if not batch:
            break
        offset += len(batch)
        max_offset = int(meta.get("maxOffset") or (10_000 if plan != "ANON" else 1_000))
        reachable = int(meta.get("totalReachable") or total or 0)
        if total and offset >= int(total):
            break
        if reachable and offset >= reachable:
            break
        if offset >= max_offset:
            break
        time.sleep(SLEEP)
    return items


def compact_num(value) -> int | None:
    if value in (None, ""):
        return None
    raw = str(value).strip().replace("\xa0", " ").replace(" ", "").replace(",", ".")
    if not raw or raw.upper() in {"N/A", "NA"}:
        return None
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


def fetch_tg_stats(login: str, kind: str) -> dict:
    url = f"https://t.me/{login}" if kind == "Бот" else f"https://t.me/s/{login}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    out = {"name": "", "mau": None, "subscribers": None}
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return out
    title = re.search(r'og:title"\s+content="([^"]+)"', html)
    if title:
        out["name"] = re.sub(r"\s+", " ", title.group(1)).strip()
    mau = re.search(r">([\d\s\.,MK]+)monthly users<", html, re.I)
    if mau:
        out["mau"] = compact_num(mau.group(1))
    subs = re.search(r"([\d\s\.,MK]+)subscribers", html, re.I)
    if subs:
        out["subscribers"] = compact_num(subs.group(1))
    return out


def fill_missing_stats(store: dict) -> None:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    pending = []
    for item in store.values():
        kind = item.get("kind") or ("Бот" if is_bot(item["login"]) else "Канал")
        need_mau = kind == "Бот" and not item.get("mau")
        need_subs = kind == "Канал" and not item.get("subscribers")
        need_name = not item.get("name")
        if need_mau or need_subs or need_name:
            pending.append(item)
    if not pending:
        return
    print(f"  добираю цифры с t.me для {len(pending)} площадок...", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {}
        for item in pending:
            kind = item.get("kind") or ("Бот" if is_bot(item["login"]) else "Канал")
            futs[pool.submit(fetch_tg_stats, item["login"], kind)] = item
        for fut in as_completed(futs):
            item = futs[fut]
            done += 1
            try:
                live = fut.result()
            except Exception:
                live = {}
            if live.get("mau") and not item.get("mau"):
                item["mau"] = live["mau"]
            if live.get("subscribers") and not item.get("subscribers"):
                item["subscribers"] = live["subscribers"]
            if live.get("name") and (not item["name"] or len(live["name"]) > len(item["name"])):
                item["name"] = live["name"]
            if done % 40 == 0 or done == len(pending):
                print(f"    {done}/{len(pending)}", flush=True)


def channel_reach(item: dict) -> float | None:
    subs = item.get("subscribers")
    views = item.get("avg_views")
    if not subs or views in (None, ""):
        return None
    return int(views) / int(subs)


def keep_quality(item: dict) -> bool:
    login = item["login"]
    name = item.get("name") or ""
    if GIVEAWAY_RE.search(name) or GIVEAWAY_RE.search(login):
        return False
    kind = item.get("kind") or ("Бот" if is_bot(login) else "Канал")
    if kind == "Бот" or is_bot(login):
        mau = item.get("mau") or 0
        return mau >= MIN_BOT_MAU
    subs = item.get("subscribers") or 0
    if subs < MIN_CHANNEL_SUBS or subs > MAX_CHANNEL_SUBS:
        return False
    reach = channel_reach(item)
    if reach is None:
        return True
    if reach < MIN_REACH or reach > MAX_REACH:
        return False
    return True


def load_known() -> set[str]:
    known = set()
    if not KNOWN_CSV.exists():
        return known
    with KNOWN_CSV.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            login = clean_login(row.get("Логин") or row.get("Ссылка") or "")
            if login:
                known.add(login.lower())
    return known


def upsert(store: dict, login: str, **kwargs):
    login = clean_login(login)
    if not login or is_own(login, kwargs.get("name", "")):
        return
    key = login.lower()
    item = store.setdefault(
        key,
        {
            "login": login,
            "name": "",
            "mau": None,
            "subscribers": None,
            "avg_views": None,
            "sources": set(),
            "creatives": 0,
            "last_seen": "",
            "first_seen": "",
            "kind": "",
        },
    )
    if kwargs.get("name") and len(kwargs["name"]) >= len(item["name"]):
        item["name"] = kwargs["name"]
    if kwargs.get("kind") and not item["kind"]:
        item["kind"] = kwargs["kind"]
    for field in ("mau", "subscribers", "avg_views"):
        val = kwargs.get(field)
        if val not in (None, "") and (item[field] is None or int(val) > int(item[field] or 0)):
            item[field] = int(val)
    if kwargs.get("source"):
        item["sources"].add(kwargs["source"])
    creatives = kwargs.get("creatives") or 0
    if creatives:
        item["creatives"] = max(item["creatives"], int(creatives))
    last_seen = kwargs.get("last_seen") or ""
    if last_seen and (not item["last_seen"] or last_seen > item["last_seen"]):
        item["last_seen"] = last_seen
    first_seen = kwargs.get("first_seen") or ""
    if first_seen and (not item["first_seen"] or first_seen < item["first_seen"]):
        item["first_seen"] = first_seen


def fetch_spy_advertisers(api_key: str) -> dict:
    store: dict[str, dict] = {}
    rows = spy_pages("advertisers", api_key, {"niche": "vpn", "sort": "recent"})
    for row in rows:
        login = row.get("tgUsername") or row.get("name") or ""
        upsert(
            store,
            login,
            name=row.get("name") or "",
            source="TG Ads",
            kind="Бот" if is_bot(login) else "Канал",
            creatives=row.get("creativeCount") or 0,
            last_seen=(row.get("lastSeenAt") or "")[:10],
            first_seen=(row.get("firstSeenAt") or "")[:10],
        )
    return store


def fetch_spy_ads(store: dict, api_key: str) -> None:
    rows = spy_pages("ads", api_key, {"niche": "vpn", "geo": "RU", "days": "30"})
    for row in rows:
        login = row.get("ctaTargetUsername") or (row.get("advertiser") or {}).get("name") or ""
        upsert(
            store,
            login,
            name=row.get("targetTitle") or row.get("title") or "",
            mau=row.get("targetBotActiveUsers"),
            source="TG Ads",
            kind="Бот" if is_bot(login) else "Канал",
            creatives=1,
            last_seen=(row.get("lastSeenAt") or "")[:10],
            first_seen=(row.get("firstSeenAt") or "")[:10],
        )


def fetch_spy_miniapps(store: dict, api_key: str) -> None:
    rows = spy_pages("miniapps", api_key, {"niche": "vpn", "sort": "mau"})
    for row in rows:
        login = row.get("username") or ""
        upsert(
            store,
            login,
            name=row.get("title") or "",
            mau=row.get("botActiveUsers"),
            source="TG Ads",
            kind="Бот",
        )


def fetch_spy_channels(store: dict, api_key: str) -> None:
    queries = [
        {"sponsored": "eligible", "lang": "ru", "minMembers": str(MIN_CHANNEL_SUBS)},
        {"sponsored": "eligible", "q": "vpn", "minMembers": "10000"},
    ]
    for extra in queries:
        rows = spy_pages("channels", api_key, extra)
        for row in rows:
            login = row.get("username") or ""
            lang = (row.get("lang") or "").lower()
            if extra.get("q") == "vpn" and lang not in {"", "ru"}:
                continue
            upsert(
                store,
                login,
                name=row.get("title") or "",
                subscribers=row.get("members"),
                avg_views=row.get("avgViews"),
                source="TG Ads канал",
                kind="Канал",
            )


def fetch_tgstat_posts(store: dict) -> None:
    token = os.environ.get("TGSTAT_TOKEN", "").strip()
    if not token:
        print("  TGStat API: нет TGSTAT_TOKEN, пропускаю поиск посевов")
        return
    query = 'vpn (бот | bot | впн) (t.me | "подключ")'
    params = {
        "token": token,
        "q": query,
        "extendedSyntax": "1",
        "extended": "1",
        "peerType": "channel",
        "language": "russian",
        "country": "ru",
        "hideForwards": "1",
        "hideDeleted": "1",
        "limit": "50",
    }
    url = TGSTAT_SEARCH + "?" + urllib.parse.urlencode(params)
    try:
        payload = http_json(url, api_key="")
    except Exception as exc:
        print(f"  TGStat posts/search: {exc}")
        return
    items = ((payload.get("response") or {}).get("items")) or []
    for post in items:
        text = post.get("text") or ""
        for login in LOGIN_RE.findall(text):
            if is_bot(login) or "vpn" in login.lower():
                upsert(store, login, source="TGStat посевы")
        for ch in ((payload.get("response") or {}).get("channels")) or []:
            upsert(
                store,
                ch.get("username") or "",
                name=ch.get("title") or "",
                subscribers=ch.get("participants_count"),
                source="TGStat посевы",
            )
    print(f"  TGStat: {len(items)} постов")


def guess_login_field(headers: list[str]) -> str | None:
    keys = [
        "логин", "username", "user_name", "tg", "telegram", "ссылка", "link",
        "url", "advertiser", "advertised", "target", "бот", "канал", "object",
        "упоминаемый",
    ]
    lower = {h.lower().strip(): h for h in headers}
    for key in keys:
        for header_l, header in lower.items():
            if key in header_l:
                return header
    return headers[0] if headers else None


def ingest_known_inventory(store: dict) -> int:
    if not KNOWN_CSV.exists():
        return 0
    added = 0
    with KNOWN_CSV.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            login = clean_login(row.get("Логин") or row.get("Ссылка") or "")
            if not login:
                continue
            kind = row.get("Тип") or ("Бот" if is_bot(login) else "Канал")
            upsert(
                store,
                login,
                name=row.get("Название") or "",
                mau=compact_num(row.get("Месячная аудитория")),
                subscribers=compact_num(row.get("Подписчики")),
                source="историческая таблица",
                kind=kind,
            )
            added += 1
    print(f"  историческая таблица: {added}", flush=True)
    return added


def ingest_local_bot_csvs(store: dict) -> int:
    added = 0
    for path in LOCAL_BOT_CSVS:
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                login = clean_login(
                    row.get("username")
                    or row.get("Логин")
                    or row.get("link")
                    or row.get("Ссылка")
                    or ""
                )
                kind_raw = (row.get("type") or row.get("Тип") or "").lower()
                if kind_raw == "user":
                    continue
                kind = "Канал" if kind_raw == "channel" or (login and not is_bot(login) and kind_raw != "bot") else "Бот"
                if kind_raw == "channel":
                    kind = "Канал"
                elif kind_raw == "bot" or is_bot(login):
                    kind = "Бот"
                mau = compact_num(row.get("bot_active_users") or row.get("Численность") or row.get("Месячная аудитория"))
                source = "TG Ads кабинет" if "telegram_chats" in path.name else "историческая таблица"
                upsert(
                    store,
                    login,
                    name=row.get("name") or row.get("Название") or "",
                    mau=mau,
                    subscribers=compact_num(row.get("Подписчики")),
                    source=source,
                    kind=kind,
                )
                added += 1
        print(f"  локальный CSV {path.name}", flush=True)
    return added


def ingest_previous_spy(store: dict) -> int:
    if not OUT_ALL.exists():
        return 0
    added = 0
    with OUT_ALL.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            login = clean_login(row.get("Логин") or row.get("Ссылка") or "")
            if not login:
                continue
            for src in (row.get("Источник") or "TG Ads").split(","):
                upsert(
                    store,
                    login,
                    name=row.get("Название") or "",
                    mau=compact_num(row.get("Месячная аудитория")),
                    subscribers=compact_num(row.get("Подписчики")),
                    avg_views=compact_num(row.get("Средний охват поста")),
                    source=src.strip() or "TG Ads",
                    kind=row.get("Тип") or "",
                    creatives=compact_num(row.get("Креативов")) or 0,
                    first_seen=row.get("Первый раз") or "",
                    last_seen=row.get("Последний раз") or "",
                )
            added += 1
    print(f"  прошлый съём tgadsspy: {added}", flush=True)
    return added


def ingest_exports(store: dict) -> int:
    IMPORTS.mkdir(exist_ok=True)
    files = list(IMPORTS.glob("*.csv")) + list(IMPORTS.glob("*.tsv"))
    added = 0
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as f:
            sample = f.read(2048)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            reader = csv.DictReader(f, dialect=dialect)
            headers = reader.fieldnames or []
            login_field = guess_login_field(headers)
            name_field = next((h for h in headers if "назван" in h.lower() or "title" in h.lower() or "name" in h.lower()), None)
            mau_field = next((h for h in headers if "мес" in h.lower() or "mau" in h.lower() or "audience" in h.lower()), None)
            sub_field = next((h for h in headers if "подпис" in h.lower() or "subscrib" in h.lower()), None)
            source = "Telemetr/TGStat CSV"
            if "tgstat" in path.name.lower():
                source = "TGStat посевы"
            elif "telemetr" in path.name.lower():
                source = "Telemetr посевы"
            elif "telega" in path.name.lower():
                source = "Telega.in посевы"
            for row in reader:
                login = clean_login(row.get(login_field, "") if login_field else "")
                if not login:
                    blob = " ".join(str(v) for v in row.values())
                    found = LOGIN_RE.findall(blob)
                    login = found[0] if found else ""
                if not login:
                    continue
                mau = None
                subs = None
                if mau_field:
                    digits = re.sub(r"\D", "", str(row.get(mau_field) or ""))
                    mau = int(digits) if digits else None
                if sub_field:
                    digits = re.sub(r"\D", "", str(row.get(sub_field) or ""))
                    subs = int(digits) if digits else None
                upsert(
                    store,
                    login,
                    name=(row.get(name_field) if name_field else "") or "",
                    mau=mau,
                    subscribers=subs,
                    source=source,
                )
                added += 1
        print(f"  импорт {path.name}")
    if not files:
        print(f"  CSV из бирж нет, положи выгрузку в {IMPORTS}")
    return added


def to_rows(store: dict, known: set[str], quality_only: bool = False) -> list[dict]:
    rows = []
    for item in store.values():
        if quality_only and not keep_quality(item):
            continue
        login = item["login"]
        kind = item.get("kind") or ("Бот" if is_bot(login) else "Канал")
        reach = channel_reach(item)
        rows.append({
            "Тип": kind,
            "Название": item["name"],
            "Логин": f"@{login}",
            "Ссылка": f"https://t.me/{login}",
            "Подписчики": fmt_num(item["subscribers"]),
            "Месячная аудитория": fmt_num(item["mau"]),
            "Средний охват поста": fmt_num(item.get("avg_views")),
            "Охват %": f"{reach * 100:.1f}" if reach is not None else "",
            "Источник": ", ".join(sorted(item["sources"])),
            "Креативов": item["creatives"] or "",
            "Первый раз": item["first_seen"],
            "Последний раз": item["last_seen"],
            "Новый": "Да" if login.lower() not in known else "Нет",
        })

    def sort_key(row):
        kind_order = 0 if row["Тип"] == "Канал" else 1
        size = compact_num(row["Подписчики"]) or compact_num(row["Месячная аудитория"]) or 0
        return (kind_order, -size, row["Логин"].lower())

    rows.sort(key=sort_key)
    return rows


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    print("Собираю VPN-площадки...", flush=True)
    api_key = load_spy_key()
    # FREE-ключ и ANON сейчас в 24h quarantine — не жжём повторно
    api_key = ""
    store: dict[str, dict] = {}
    print("прошлые съёмы и кабинет", flush=True)
    ingest_previous_spy(store)
    ingest_known_inventory(store)
    ingest_local_bot_csvs(store)
    try:
        if os.environ.get("TGADSSPY_SKIP", "1") == "1":
            raise SpyQuarantine("skip until 24h cooldown")
        print("tgadsspy: пробую ANON", flush=True)
        print("1/3 креативы VPN RU за 30 дней", flush=True)
        fetch_spy_ads(store, api_key)
        print("2/3 VPN mini-apps (MAU)", flush=True)
        fetch_spy_miniapps(store, api_key)
        print("3/3 каналы, где крутится TG Ads", flush=True)
        fetch_spy_channels(store, api_key)
    except SpyQuarantine:
        print("  tgadsspy в карантине 24ч — работаю с локальными списками и t.me", flush=True)
    print("TGStat Search API", flush=True)
    fetch_tgstat_posts(store)
    print("CSV из imports/", flush=True)
    ingest_exports(store)
    fill_missing_stats(store)

    known = load_known()
    fields = [
        "Тип", "Название", "Логин", "Ссылка", "Подписчики", "Месячная аудитория",
        "Средний охват поста", "Охват %", "Источник", "Креативов",
        "Первый раз", "Последний раз", "Новый",
    ]
    rows = to_rows(store, known, quality_only=False)
    quality = to_rows(store, known, quality_only=True)
    write_csv(OUT_ALL, rows, fields)
    write_csv(OUT_QUALITY, quality, fields)
    new_rows = [r for r in quality if r["Новый"] == "Да"]
    write_csv(OUT_NEW, new_rows, fields)

    bots_q = sum(1 for r in quality if r["Тип"] == "Бот")
    ch_q = sum(1 for r in quality if r["Тип"] == "Канал")
    print(f"Всего сырых: {len(rows)}", flush=True)
    print(f"После фильтра (каналы 20к–2м, охват 6–50%, боты MAU≥10к): {len(quality)}", flush=True)
    print(f"  каналы: {ch_q}, боты: {bots_q}, из них новых: {len(new_rows)}", flush=True)
    print(f"  {OUT_QUALITY.name}", flush=True)
    print(f"  {OUT_NEW.name}", flush=True)
    if quality:
        print("Топ каналов:", flush=True)
        for row in [r for r in quality if r["Тип"] == "Канал"][:8]:
            print(f"  {row['Подписчики']:>10} {row['Охват %']:>5}% {row['Логин']} {row['Название'][:40]}", flush=True)
        print("Топ ботов:", flush=True)
        for row in [r for r in quality if r["Тип"] == "Бот"][:8]:
            print(f"  {row['Месячная аудитория']:>10} {row['Логин']} {row['Название'][:40]}", flush=True)


if __name__ == "__main__":
    main()
