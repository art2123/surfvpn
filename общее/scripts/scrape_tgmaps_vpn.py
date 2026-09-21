# -*- coding: utf-8 -*-
"""Парсинг VPN-креативов Telegram Ads из cabinet.tgmaps.ru.

Нужна сессия: общее/tgads-snapshots/_tgmaps_cookies.json
  (remember_web_* + опционально bearer_token).

Запуск:
  python общее/scripts/scrape_tgmaps_vpn.py
  python общее/scripts/scrape_tgmaps_vpn.py --max-brands 100 --sleep 0.5
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import http.cookiejar
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from http.cookiejar import Cookie
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "tgads-snapshots"
SNAP.mkdir(exist_ok=True)
COOKIES_PATH = SNAP / "_tgmaps_cookies.json"

BASE = "https://cabinet.tgmaps.ru"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
)

OWN = re.compile(r"surf|blanc|fck.?rkn|getsurf", re.I)
GIVEAWAY_RE = re.compile(
    r"розыгрыш|giveaway|iphone|айфон|выигрыш|выиграй|айпад|macbook|\btesla\b|"
    r"миллион подпис|бесплатн\w*\s+конфиг|раздач\w*\s+ключ|mtproto|прокси\s+бесплат",
    re.I,
)
NON_RU_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]|"  # Arabic
    r"[\u06A9\u06CC]|"  # Persian letters often
    r"\b(download now|best vpn|unlimited bandwidth|click here)\b",
    re.I,
)
LOGIN_RE = re.compile(
    r"(?:t\.me/|telegram\.me/|@)([A-Za-z][A-Za-z0-9_]{3,31})",
    re.I,
)

# Exact defaults from frontend f2() — Cyrillic «Все» required
FILTER_BASE = {
    "title": "",
    "entity": "",
    "link": "",
    "sponsor_type": "Все",
    "text": "",
    "category": "Все",
    "show": "0",
    "with_banner": False,
    "is_video_ad": False,
    "date_period": "all",
    "date_from": "",
    "date_to": "",
    "uuids": [],
}


def angle(text: str) -> str:
    t = (text or "").lower()
    tags = []
    if re.search(r"бел(ый|ые|ых)\s*спис|white.?list|бс\b", t):
        tags.append("white_lists")
    if re.search(r"youtube|ютуб", t):
        tags.append("youtube")
    if re.search(r"триал|бесплатн|free|дн(я|ей|ь) знаком|тест|пробн", t):
        tags.append("trial_free")
    if re.search(r"скорост|быстр|gigabit|гигабит", t):
        tags.append("speed")
    if re.search(r"министер|одобрен|гос|легальн", t):
        tags.append("gov_legal")
    if re.search(r"розыгрыш|giveaway|выигра|iphone|айфон", t):
        tags.append("giveaway")
    if re.search(r"\bai\b|gpt|gemini|нейро", t):
        tags.append("ai")
    if re.search(r"обход|блокир|рпн|рпкн|роскомнадзор|глушил", t):
        tags.append("bypass_blocks")
    return "|".join(tags) if tags else "other"


def clean_login(value: str) -> str:
    if not value:
        return ""
    value = str(value).strip()
    value = re.sub(r"^https?://(t|telegram)\.me/", "", value, flags=re.I)
    login = value.lstrip("@").split("?")[0].split("/")[0].strip()
    if login.startswith("+"):
        return ""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", login):
        return ""
    return login


def destination_from_row(row: dict) -> str:
    for key in ("identity", "url"):
        login = clean_login(row.get(key) or "")
        if login:
            return login
    m = LOGIN_RE.search(row.get("url") or "") or LOGIN_RE.search(row.get("message") or "")
    return clean_login(m.group(1)) if m else ""


def start_param(url: str) -> str:
    if not url:
        return ""
    try:
        q = parse_qs(urlparse(url).query)
        vals = q.get("start") or q.get("startapp") or []
        return vals[0] if vals else ""
    except Exception:
        return ""


def creative_hash(row: dict) -> str:
    blob = "|".join(
        [
            (row.get("message") or "").strip(),
            (row.get("url") or "").strip(),
            (row.get("identity") or "").strip().lower(),
            (row.get("title") or "").strip(),
        ]
    )
    return hashlib.sha1(blob.encode("utf-8", errors="replace")).hexdigest()[:12]


def is_vpn_candidate(row: dict) -> bool:
    title = row.get("title") or ""
    msg = row.get("message") or ""
    identity = (row.get("identity") or "").lower()
    url = (row.get("url") or "").lower()
    blob = f"{title}\n{msg}\n{identity}\n{url}"
    if OWN.search(blob):
        return False
    if GIVEAWAY_RE.search(blob) and not re.search(r"\bvpn\b|впн", blob, re.I):
        return False
    if NON_RU_RE.search(msg) and not re.search(r"[А-Яа-яЁё]", msg):
        return False
    # ChatGPT / AI wrappers that say «без VPN»
    if re.search(r"chatgpt|claude|gemini|нейронк", blob, re.I) and re.search(
        r"без\s*vpn|без\s*впн", blob, re.I
    ):
        return False
    if re.search(r"chatgpt|claude", blob, re.I) and not re.search(
        r"\bvpn\b|впн", identity + " " + title, re.I
    ):
        return False
    # must look like VPN product
    if re.search(r"\bvpn\b|впн", blob, re.I):
        return True
    if identity.endswith("bot") and re.search(r"vpn|впн", identity):
        return True
    return False


def looks_ru(row: dict) -> bool:
    msg = row.get("message") or ""
    title = row.get("title") or ""
    if re.search(r"[А-Яа-яЁё]", msg) or re.search(r"[А-Яа-яЁё]", title):
        return True
    # RU bots often still have Latin titles; keep if VPN keyword strong
    return bool(re.search(r"\bvpn\b|впн", f"{title} {msg}", re.I))


class TgMapsClient:
    def __init__(self, cookies: dict[str, str], bearer: str = "", sleep: float = 0.45):
        self.sleep = sleep
        self.bearer = bearer
        self.ctx = ssl.create_default_context()
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self.ctx),
            urllib.request.HTTPCookieProcessor(self.cj),
        )
        for name, value in cookies.items():
            if not value or name == "bearer_token":
                continue
            domain = ".cabinet.tgmaps.ru"
            if name.startswith(("_ym", "__ddg", "mdd")):
                domain = ".tgmaps.ru"
            if name.startswith("remember") or name in {
                "XSRF-TOKEN",
                "tgmaps_cabinet_session",
            }:
                domain = ".cabinet.tgmaps.ru"
            self._set_cookie(name, value, domain)

    def _set_cookie(self, name: str, value: str, domain: str) -> None:
        self.cj.set_cookie(
            Cookie(
                0,
                name,
                value,
                None,
                False,
                domain,
                True,
                domain.startswith("."),
                "/",
                True,
                True,
                None,
                False,
                None,
                None,
                {},
                False,
            )
        )

    def _xsrf(self) -> str:
        for c in self.cj:
            if c.name == "XSRF-TOKEN":
                return urllib.parse.unquote(c.value)
        return ""

    def csrf(self) -> None:
        self.request("GET", "/sanctum/csrf-cookie", expect_json=False)

    def request(
        self,
        method: str,
        path: str,
        data: dict | None = None,
        expect_json: bool = True,
        retries: int = 3,
    ):
        url = path if path.startswith("http") else BASE + path
        last_err: Exception | None = None
        for attempt in range(retries):
            if method.upper() != "GET" or "sanctum" not in path:
                # ensure csrf for mutating / API calls
                if not self._xsrf() or attempt > 0:
                    try:
                        req0 = urllib.request.Request(
                            BASE + "/sanctum/csrf-cookie",
                            headers={"User-Agent": UA, "Accept": "application/json"},
                        )
                        self.opener.open(req0, timeout=60)
                    except Exception:
                        pass
            headers = {
                "User-Agent": UA,
                "Accept": "application/json, text/plain, */*",
                "Referer": BASE + "/creatives",
                "Origin": BASE,
                "X-Requested-With": "XMLHttpRequest",
            }
            xsrf = self._xsrf()
            if xsrf:
                headers["X-XSRF-TOKEN"] = xsrf
            if self.bearer:
                headers["Authorization"] = f"Bearer {self.bearer}"
            body = None
            if data is not None:
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                headers["Content-Type"] = "application/json;charset=UTF-8"
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            try:
                time.sleep(self.sleep)
                with self.opener.open(req, timeout=90) as resp:
                    raw = resp.read()
                    if not expect_json:
                        return resp.status, raw
                    if not raw:
                        return resp.status, {}
                    return resp.status, json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                raw = exc.read() if hasattr(exc, "read") else b""
                last_err = exc
                if exc.code in {419, 401, 429, 500, 502, 503} and attempt + 1 < retries:
                    wait = 2.5 * (attempt + 1)
                    if exc.code == 429:
                        wait = 8.0 * (attempt + 1)
                    time.sleep(wait)
                    continue
                try:
                    return exc.code, json.loads(raw.decode("utf-8"))
                except Exception:
                    return exc.code, {"message": raw[:500].decode("utf-8", "replace")}
            except Exception as exc:
                last_err = exc
                time.sleep(1.0 * (attempt + 1))
        raise RuntimeError(f"request failed {method} {path}: {last_err}")

    def user(self) -> dict:
        st, data = self.request("GET", "/api/user")
        if st != 200 or not isinstance(data, dict) or "id" not in data:
            raise SystemExit(f"auth failed /api/user -> {st} {data}")
        return data

    def find_creatives(self, text: str, page: int = 1, sponsor_type: str = "Все") -> dict:
        filt = dict(FILTER_BASE)
        filt["text"] = text
        filt["sponsor_type"] = sponsor_type
        st, data = self.request(
            "POST", f"/api/creatives/find?page={page}", data={"filter": filt}
        )
        if st != 200 or not isinstance(data, dict):
            raise RuntimeError(f"find failed page={page} text={text!r}: {st} {data}")
        return data

    def creative_channels(self, uuid: str, page: int = 1) -> dict:
        st, data = self.request(
            "GET", f"/api/creatives/creative?uuid={uuid}&page={page}"
        )
        if st != 200 or not isinstance(data, dict):
            raise RuntimeError(f"creative detail failed {uuid} p={page}: {st} {data}")
        return data


def load_auth() -> tuple[dict[str, str], str]:
    if not COOKIES_PATH.exists():
        raise SystemExit(
            f"нет {COOKIES_PATH} — сначала экспортируй cookies из Cursor-браузера"
        )
    payload = json.loads(COOKIES_PATH.read_text(encoding="utf-8"))
    cookies = payload.get("map") or payload
    bearer = payload.get("bearer_token") or cookies.pop("bearer_token", "") or ""
    # fallback hardcoded last known localStorage token if present in file notes
    if not bearer:
        bearer = payload.get("x_xsrf_token") or ""
    return cookies, bearer


def collect_creatives(
    client: TgMapsClient,
    max_brands: int,
    max_pages_per_query: int,
    seed: list[dict] | None = None,
) -> list[dict]:
    queries = [
        ("VPN", "Все"),
        ("ВПН", "Все"),
        ("vpn", "Все"),
        ("VPN", "1"),  # Бот
        ("ВПН", "1"),
        ("VPN", "2"),  # Канал
        ("прокси", "1"),
        ("глушил", "Все"),
        ("белый список", "Все"),
        ("Happ", "1"),
    ]
    by_uuid: dict[str, dict] = {}
    brands: set[str] = set()

    for row in seed or []:
        uuid = row.get("uuid") or str(row.get("id") or "")
        if not uuid:
            continue
        dest = row.get("_destination") or destination_from_row(row)
        if not dest:
            continue
        row = dict(row)
        row["_destination"] = dest
        row["_hash"] = row.get("_hash") or creative_hash(row)
        row["_angle"] = row.get("_angle") or angle(row.get("message") or "")
        row["_start"] = row.get("_start") or start_param(row.get("url") or "")
        by_uuid[uuid] = row
        brands.add(dest.lower())
    if seed:
        print(f"resume seed: creatives={len(by_uuid)} brands={len(brands)}")

    for text, sponsor_type in queries:
        if len(brands) >= max_brands:
            break
        try:
            first = client.find_creatives(text, page=1, sponsor_type=sponsor_type)
        except Exception as exc:
            print(f"skip query text={text!r} sponsor={sponsor_type!r}: {exc}")
            continue
        meta = first.get("meta") or {}
        total = meta.get("total") or 0
        last_page = meta.get("last_page") or 1
        last_page = min(int(last_page), max_pages_per_query)
        print(
            f"query text={text!r} sponsor={sponsor_type!r} total={total} pages={last_page}"
        )

        pages_data = [first]
        for page in range(2, last_page + 1):
            if len(brands) >= max_brands:
                break
            try:
                pages_data.append(
                    client.find_creatives(text, page=page, sponsor_type=sponsor_type)
                )
            except Exception as exc:
                print(f"  page {page} fail: {exc}")
                time.sleep(12)
                try:
                    pages_data.append(
                        client.find_creatives(text, page=page, sponsor_type=sponsor_type)
                    )
                except Exception as exc2:
                    print(f"  page {page} retry fail: {exc2}")
                    break

        for payload in pages_data:
            for row in payload.get("data") or []:
                if not is_vpn_candidate(row):
                    continue
                if not looks_ru(row):
                    continue
                dest = destination_from_row(row)
                if not dest:
                    continue
                uuid = row.get("uuid") or str(row.get("id"))
                if uuid in by_uuid:
                    # keep richer channels_count if newer
                    prev = by_uuid[uuid]
                    if int(row.get("channels_count") or 0) > int(
                        prev.get("channels_count") or 0
                    ):
                        row = dict(row)
                        row["_destination"] = dest
                        row["_hash"] = creative_hash(row)
                        row["_angle"] = angle(row.get("message") or "")
                        row["_start"] = start_param(row.get("url") or "")
                        by_uuid[uuid] = row
                    continue
                row = dict(row)
                row["_destination"] = dest
                row["_hash"] = creative_hash(row)
                row["_angle"] = angle(row.get("message") or "")
                row["_start"] = start_param(row.get("url") or "")
                by_uuid[uuid] = row
                brands.add(dest.lower())
                if len(brands) >= max_brands:
                    break
        print(f"  brands so far: {len(brands)} creatives: {len(by_uuid)}")

    return list(by_uuid.values())


def fetch_placements(
    client: TgMapsClient,
    creatives: list[dict],
    max_channel_pages: int = 20,
    existing: list[dict] | None = None,
) -> list[dict]:
    placements: list[dict] = list(existing or [])
    done_uuid = {p.get("creative_uuid") for p in placements if p.get("creative_uuid")}
    todo = [r for r in creatives if r.get("uuid") not in done_uuid]
    print(f"placements resume: have={len(done_uuid)} todo={len(todo)}")
    for i, row in enumerate(todo, 1):
        uuid = row.get("uuid")
        if not uuid:
            continue
        expected = int(row.get("channels_count") or 0)
        page = 1
        seen = 0
        while page <= max_channel_pages:
            try:
                detail = client.creative_channels(uuid, page=page)
            except Exception as exc:
                print(f"  placement fail {uuid} p={page}: {exc}")
                time.sleep(10)
                break
            if page == 1 and detail.get("creative"):
                # enrich creative fields
                cr = detail["creative"]
                for k, v in cr.items():
                    row.setdefault(k, v)
                    if k in {"channels_count", "message", "url", "title", "identity"}:
                        row[k] = v
            ch = detail.get("channels") or {}
            data = ch.get("data") or []
            last_page = int(ch.get("last_page") or 1)
            for ch_row in data:
                login = clean_login(ch_row.get("username") or "")
                placements.append(
                    {
                        "creative_uuid": uuid,
                        "creative_id": row.get("id"),
                        "destination": row.get("_destination") or destination_from_row(row),
                        "creative_hash": row.get("_hash") or creative_hash(row),
                        "channel_id": ch_row.get("id") or ch_row.get("channel_id"),
                        "channel_login": login,
                        "channel_title": ch_row.get("title") or "",
                        "posts_times": ch_row.get("posts_times") or 1,
                        "channel_uuid": ch_row.get("uuid") or "",
                        "category_id": ch_row.get("category_id") or "",
                    }
                )
                seen += 1
            if page >= last_page or not data:
                break
            page += 1
        if i % 10 == 0 or i == len(todo):
            print(
                f"placements {i}/{len(todo)} rows={len(placements)} "
                f"last={row.get('_destination')} expected≈{expected} got={seen}"
            )
    return placements


def load_latest_snapshot() -> tuple[list[dict], list[dict]]:
    paths = sorted(SNAP.glob("*_tgmaps_vpn_creatives.json"))
    if not paths:
        return [], []
    payload = json.loads(paths[-1].read_text(encoding="utf-8"))
    print(f"loaded snapshot {paths[-1].name}")
    return list(payload.get("creatives") or []), list(payload.get("placements") or [])


def write_outputs(
    creatives: list[dict], placements: list[dict], snap_at: str
) -> tuple[Path, Path, Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    raw_path = SNAP / f"{stamp}_tgmaps_vpn_creatives.json"
    raw_path.write_text(
        json.dumps(
            {
                "snapshot_at": snap_at,
                "source": "tgmaps",
                "creatives": creatives,
                "placements": placements,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    creatives_csv = ROOT / "tgmaps-vpn-creatives.csv"
    fields = [
        "snapshot_at",
        "source",
        "uuid",
        "ad_id",
        "destination",
        "title",
        "text",
        "url",
        "start_param",
        "sponsor_type_id",
        "channels_count",
        "first_date",
        "end_date",
        "angle",
        "creative_hash",
        "media",
    ]
    with creatives_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in creatives:
            dates = row.get("dates") or {}
            w.writerow(
                {
                    "snapshot_at": snap_at,
                    "source": "tgmaps",
                    "uuid": row.get("uuid") or "",
                    "ad_id": row.get("id") or "",
                    "destination": row.get("_destination")
                    or destination_from_row(row),
                    "title": row.get("title") or "",
                    "text": row.get("message") or "",
                    "url": row.get("url") or "",
                    "start_param": row.get("_start")
                    or start_param(row.get("url") or ""),
                    "sponsor_type_id": row.get("sponsor_type_id") or "",
                    "channels_count": row.get("channels_count") or 0,
                    "first_date": dates.get("first_date") or "",
                    "end_date": dates.get("end_date") or "",
                    "angle": row.get("_angle") or angle(row.get("message") or ""),
                    "creative_hash": row.get("_hash") or creative_hash(row),
                    "media": row.get("media") or "",
                }
            )

    placements_csv = ROOT / "tgmaps-vpn-placements.csv"
    pfields = [
        "creative_uuid",
        "creative_id",
        "destination",
        "creative_hash",
        "channel_login",
        "channel_title",
        "posts_times",
        "channel_id",
        "channel_uuid",
        "category_id",
    ]
    with placements_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pfields)
        w.writeheader()
        for row in placements:
            w.writerow({k: row.get(k, "") for k in pfields})

    digest = ROOT / "tgmaps-vpn-digest.md"
    digest.write_text(
        build_digest(creatives, placements, snap_at), encoding="utf-8"
    )
    return raw_path, creatives_csv, placements_csv, digest


def build_digest(creatives: list[dict], placements: list[dict], snap_at: str) -> str:
    brands = Counter()
    brand_creatives: dict[str, list[dict]] = defaultdict(list)
    for row in creatives:
        dest = (row.get("_destination") or destination_from_row(row)).lower()
        brands[dest] += 1
        brand_creatives[dest].append(row)

    # creative_hash -> channels
    by_hash_channels: dict[str, set[str]] = defaultdict(set)
    by_hash_meta: dict[str, dict] = {}
    for row in creatives:
        h = row.get("_hash") or creative_hash(row)
        by_hash_meta[h] = row
    for p in placements:
        h = p.get("creative_hash") or ""
        login = p.get("channel_login") or ""
        if h and login:
            by_hash_channels[h].add(login.lower())

    ranked = sorted(
        by_hash_channels.items(), key=lambda kv: (-len(kv[1]), kv[0])
    )

    lines = [
        f"# VPN TG Ads — TgMaps digest — {snap_at}",
        "",
        f"Источник: cabinet.tgmaps.ru `/api/creatives/find` + `/api/creatives/creative`.",
        f"Креативов: **{len(creatives)}**. Уникальных destination: **{len(brands)}**. "
        f"Строк placement: **{len(placements)}**.",
        "",
        "## Топ destination (по числу креативов)",
        "",
    ]
    for dest, n in brands.most_common(40):
        sample = brand_creatives[dest][0]
        title = (sample.get("title") or "")[:60]
        max_ch = max(int(r.get("channels_count") or 0) for r in brand_creatives[dest])
        lines.append(
            f"- **@{dest}** — {n} креатив(ов), max channels_count={max_ch} — _{title}_"
        )

    lines += ["", "## Креативы с максимальным N площадок (идеал: одно объявление → много каналов)", ""]
    for h, chans in ranked[:30]:
        meta = by_hash_meta.get(h) or {}
        dest = meta.get("_destination") or destination_from_row(meta)
        text = (meta.get("message") or "").replace("\n", " ")
        if len(text) > 140:
            text = text[:140] + "…"
        top = ", ".join(f"@{c}" for c in sorted(chans)[:12])
        more = f" …+{len(chans)-12}" if len(chans) > 12 else ""
        lines.append(
            f"- **@{dest}** — **{len(chans)}** площадок (hash `{h}`)\n"
            f"  - _{text}_\n"
            f"  - {top}{more}"
        )

    # brands by total unique placement channels across all creatives
    brand_places: dict[str, set[str]] = defaultdict(set)
    for p in placements:
        d = (p.get("destination") or "").lower()
        login = (p.get("channel_login") or "").lower()
        if d and login:
            brand_places[d].add(login)
    lines += ["", "## Бренды по охвату площадок (уник. channel_login)", ""]
    for dest, chans in sorted(brand_places.items(), key=lambda kv: -len(kv[1]))[:30]:
        lines.append(f"- **@{dest}** — {len(chans)} уник. площадок")

    lines += [
        "",
        "## Файлы",
        "",
        "- `общее/tgmaps-vpn-creatives.csv`",
        "- `общее/tgmaps-vpn-placements.csv`",
        "- `общее/tgads-snapshots/*_tgmaps_vpn_creatives.json`",
        "",
    ]
    return "\n".join(lines) + "\n"


def ensure_bearer(cookies: dict) -> str:
    bearer = cookies.get("bearer_token") or ""
    if bearer:
        return bearer
    # try localStorage extract
    ls = (
        Path.home()
        / "AppData/Roaming/Cursor/Partitions/cursor-browser/Local Storage/leveldb"
    )
    if not ls.exists():
        return ""
    for p in ls.glob("*"):
        if not p.is_file() or p.name in {"LOCK", "LOG", "LOG.old", "CURRENT"}:
            continue
        try:
            data = p.read_bytes()
        except Exception:
            continue
        m = re.search(
            rb"x_xsrf_token.{0,20}(eyJpdiI6[A-Za-z0-9+/=_-]{50,})", data
        )
        if m:
            return m.group(1).decode("ascii", errors="ignore")
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-brands", type=int, default=100)
    ap.add_argument("--max-pages", type=int, default=40, help="max pages per query")
    ap.add_argument("--sleep", type=float, default=0.45)
    ap.add_argument(
        "--skip-placements",
        action="store_true",
        help="only creatives, no channel lists",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="continue from latest *_tgmaps_vpn_creatives.json",
    )
    ap.add_argument(
        "--placements-only-new",
        action="store_true",
        help="with --resume, only fetch placements for creatives missing them",
    )
    ap.add_argument(
        "--placements-only",
        action="store_true",
        help="do not search creatives; only fill missing placements from latest snapshot",
    )
    args = ap.parse_args()

    cookies, bearer = load_auth()
    if not bearer:
        bearer = ensure_bearer(cookies)
    # persist bearer for next runs
    if bearer:
        payload = {"map": {k: v for k, v in cookies.items() if k != "bearer_token"}}
        payload["bearer_token"] = bearer
        COOKIES_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    client = TgMapsClient(cookies, bearer=bearer, sleep=args.sleep)
    client.csrf()
    user = client.user()
    print(
        f"auth ok: {user.get('name')} <{user.get('email')}> "
        f"sub={((user.get('subscription') or {}).get('subscription_id'))}"
    )

    snap_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    seed_creatives: list[dict] = []
    seed_placements: list[dict] = []
    if args.resume or args.placements_only:
        seed_creatives, seed_placements = load_latest_snapshot()

    if args.placements_only:
        creatives = seed_creatives
        print(
            f"placements-only: creatives={len(creatives)} "
            f"brands={len({(c.get('_destination') or '').lower() for c in creatives})}"
        )
    else:
        creatives = collect_creatives(
            client, args.max_brands, args.max_pages, seed=seed_creatives or None
        )
        print(
            f"collected creatives={len(creatives)} brands="
            f"{len({(c.get('_destination') or '').lower() for c in creatives})}"
        )

    placements: list[dict] = []
    if args.skip_placements:
        placements = seed_placements
        print(f"skip-placements: keeping {len(placements)} existing rows")
    else:
        # prioritize high channels_count
        creatives.sort(key=lambda r: int(r.get("channels_count") or 0), reverse=True)
        if args.resume or args.placements_only_new or args.placements_only:
            placements = fetch_placements(
                client, creatives, existing=seed_placements
            )
        else:
            placements = fetch_placements(client, creatives)

    raw, c_csv, p_csv, digest = write_outputs(creatives, placements, snap_at)
    print("wrote", raw)
    print("wrote", c_csv)
    print("wrote", p_csv)
    print("wrote", digest)


if __name__ == "__main__":
    main()
