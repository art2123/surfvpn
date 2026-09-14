# -*- coding: utf-8 -*-
"""Каналы, где VPN-реклама уже показывалась (не биржа слотов)."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "tg-ads-площадки.csv"
BOTS_SRC = ROOT / "tg-ads-обнаруженные.csv"
SKIP_BOTS = {
    "stickers", "gif", "botfather", "tg_analytics_bot", "getemojiidbot",
}

# Топ каналов со страниц рекламодателей tgadsspy:
# «Top channels where ads appeared» — факт показа VPN-креатива в канале.
# Подписчики как в карточке; отсекаем <20к и >2м (без розыгрышных мегаканалов).
PLACEMENTS = [
    # login, name, subs, vpn_ads, advertisers
    ("shukavpn", "Щука VPN", 1_323_000, 20, "synatra"),
    ("quattrovpn_news", "Quattro VPN — Новости", 1_107_000, 15, "synatra"),
    ("sotavpn", "Sota VPN — Канал", 980_100, 43, "synatra"),
    ("egorikvtg", "ЕГОР ШКРЕД", 707_200, 3, "velvet"),
    ("velvet_vpn", "Velvet VPN · Telegram Proxy", 468_000, 9, "synatra, velvet"),
    ("d_code", "Код.ру", 383_000, 7, "slig"),
    ("cafe_citaty", "Cafe de Flore • Цитаты • Мемы", 265_200, 4, "velvet"),
    ("velvet_vpn_health", "Velvet VPN Статус", 264_500, 5, "velvet"),
    ("shadownetvpnchannel", "Shadownet VPN - Официальный канал", 248_500, 28, "panda"),
    ("doktorgpt", "Доктор GPT", 246_100, 6, "slig"),
    ("lagomvpn", "Lagom VPN — Новости ВПН", 223_000, 17, "vanya"),
    ("voxiproxynews", "VoxiProxy News", 201_800, 45, "elusion"),
    ("youfastvpn", "Новости безопасности от YouFast VPN™", 198_700, 21, "panda"),
    ("ultimavpn", "Ultima VPN — Новости", 149_200, 12, "synatra"),
    ("horizon_vpn", "Horizon VPN Новости", 141_200, 14, "bebra, vanya"),
    ("news_kotvpn", "Новости - KotVPN", 133_700, 14, "bebra"),
    ("hermitvpn", "Hermit VPN", 125_000, 22, "panda, atlanta"),
    ("pantherpinkvpn", "Panther VPN - новости", 121_500, 12, "synatra"),
    ("sueta_games", "ИГРЫ ДЛЯ СУЕТЫ", 117_700, 5, "groza"),
    ("lastdepvpn", "LastdepVPN", 112_000, 18, "vanya"),
    ("juliusspeak", "Юлик", 112_100, 4, "velvet"),
    ("steamfreeru", "Игры Стим|Steam", 102_600, 3, "velvet"),
    ("android1_ru", "Новинки игр и приложений", 90_400, 5, "groza"),
    ("nashvpnnews", "NashVPN | Новости", 66_900, 20, "panda, greenvpn"),
    ("kyravpn", "Kyra VPN & Proxy | Канал", 66_600, 8, "atlanta"),
    ("internetdostupen", "Max | ПРО бизнес на ВПН", 63_300, 36, "elusion, panda, open21"),
    ("durevvpn", "Durev VPN | Новости", 61_400, 3, "ejx"),
    ("modsdroid", "Твоя мама не одобрит", 59_600, 5, "groza"),
    ("rustore_games", "RuStore Игры", 58_600, 5, "groza"),
    ("shivavpn", "SHIVA", 57_800, 11, "synatra"),
    ("potatofreevpn", "FreeVPN | Бесплатный VPN | Новости", 54_100, 26, "panda"),
    ("green_vpn", "Green VPN | Channel", 49_200, 3, "ejx"),
    ("vpnmagnum", "Magnum • Новости", 44_300, 15, "bebra, greenvpn"),
    ("vinnypux_vpn", "Винни-Пух", 38_300, 7, "greenvpn"),
    ("palkavpn", "PalkaVPN - новостной канал", 37_500, 25, "panda, elusion, open21"),
    ("mtproxy4free", "MTProto прокси для Telegram", 35_800, 13, "open21"),
    ("vrpirate", "VRPirate VR игры", 35_200, 5, "groza"),
    ("lampa_channel", "Lampa - Основной канал", 29_300, 25, "elusion"),
    ("super_t2026", "SuperVPN2026", 29_800, 12, "atlanta"),
    ("zoomerskydostup", "Новости Зумера", 28_600, 5, "groza"),
    ("esimpsonconnection", "ESIMPSON - Telegram Free Proxy", 26_600, 31, "elusion"),
    ("nbbvpn", "NBB VPN - Работает в России!", 26_500, 21, "panda"),
    ("na_svyazi_helpdesk", "НА СВЯЗИ | Служба техподдержки", 26_400, 10, "atlanta"),
    ("kinatvideo", "KinatVideo: Лучшие игры", 25_700, 5, "groza"),
    ("gameofpctg", "Игры на пк", 23_500, 5, "groza"),
    ("abyss_guard", "Abyss Guard | VPN", 21_700, 14, "open21"),
    # крупные медиа, где VPN уже показывали, но не 4–5м розыгрыши
    ("rhymestg", "Рифмы и Панчи", 1_400_000, 11, "slig"),
    ("shot_shot", "SHOT", 1_300_000, 10, "slig"),
    ("pravdadirty", "ВПШ", 1_400_000, 9, "slig"),
    ("exilemusic13", "Exile", 1_400_000, 6, "slig"),
    ("bbbreaking", "Раньше всех. Ну почти.", 1_973_000, 5, "slig"),
]


def fmt(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")


def load_bots() -> list[dict]:
    rows = []
    if not BOTS_SRC.exists():
        return rows
    with BOTS_SRC.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if not (row.get("Тип") or "").startswith("Бот"):
                continue
            mau = (row.get("Месячная аудитория") or "").replace(" ", "")
            if not mau.isdigit() or int(mau) < 10_000:
                continue
            login = (row.get("Логин") or "").lstrip("@").lower()
            if login in SKIP_BOTS:
                continue
            src = row.get("Источник") or ""
            if "Telega.in" in src:
                continue
            rows.append(row)
    return rows


def main() -> None:
    fields = [
        "Тип", "Название", "Логин", "Ссылка", "Подписчики",
        "Месячная аудитория", "Креативов VPN", "VPN-рекламодатели",
    ]
    channels = []
    for login, name, subs, ads, advertisers in sorted(PLACEMENTS, key=lambda x: -x[2]):
        channels.append({
            "Тип": "Канал",
            "Название": name,
            "Логин": f"@{login}",
            "Ссылка": f"https://t.me/{login}",
            "Подписчики": fmt(subs),
            "Месячная аудитория": "",
            "Креативов VPN": ads,
            "VPN-рекламодатели": advertisers,
        })
    bots = []
    for row in load_bots():
        bots.append({
            "Тип": row.get("Тип") or "Бот",
            "Название": row.get("Название") or "",
            "Логин": row.get("Логин") or "",
            "Ссылка": row.get("Ссылка") or "",
            "Подписчики": row.get("Подписчики") or "",
            "Месячная аудитория": row.get("Месячная аудитория") or "",
            "Креативов VPN": row.get("Креативов") or "",
            "VPN-рекламодатели": "",
        })

    def bot_key(r):
        mau = (r.get("Месячная аудитория") or "").replace(" ", "")
        return -int(mau) if mau.isdigit() else 0

    bots.sort(key=bot_key)
    all_rows = channels + bots
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"каналы где уже крутили VPN: {len(channels)}")
    print(f"боты-рекламодатели MAU>=10к: {len(bots)}")
    print(OUT.name)
    print("топ каналов:")
    for row in channels[:12]:
        print(f"  {row['Подписчики']:>10}  {row['Креативов VPN']:>3} креативов  {row['Логин']}  {row['VPN-рекламодатели']}")


if __name__ == "__main__":
    main()
