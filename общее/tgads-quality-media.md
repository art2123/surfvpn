# TG Ads quality media (Technoinsider etalon)

Эталон аудитории для Surf TG Ads: **@technoinsider** (Техно Инсайдер).
Blanc-покупки + Surf trials ≈ половина trials с медиа-сегмента — сегмент однозначно рабочий.

## Что такое «гибрид» (не science-каталог)

| Класс | Суть | Пример |
|---|---|---|
| `hybrid_vpn_brand_media` | tech/новости + RKN/VPN + свой продукт | technoinsider (Gru), blokirovki_runeta (Durev) |
| `hybrid_media_tech` | tech/gadgets/TG-ecosystem, в ленте регулярно VPN/RKN/блокировки | rozetked, tginfo |
| `hybrid_vpn_brand_news` | новостной канал бренда VPN (не чистый sales-bot) | lagomvpn, amnezia_vpn_news_ru, quattrovpn_news |
| `rights_blocks` | права/блокировки без tech-тона | roskomsvoboda |

**Не берём:** чистый science/tech без VPN-интента; политику с одним упоминанием «блокировка»; EN/AR/FA; раздачи конфигов/ключей; каналы с ⛔ Telemetr / угнанным логином.

## Метрики эталона (Telemetr)

- TI: ~75k подп., ER ~20%, ~15–20k views/post.
- Ориентир shortlist: ER ≥12%, живая RU-аудитория, желательно TI-scale или больше при ясном гибрид-интенте.

## Shortlist для batch Channels `scope=s`

Источник: `общее/imports/ti_hybrid_shortlist.json`.

Приоритет 1 (снять ER / sanity ✓):

1. `blokirovki_runeta` — структурный близнец TI (47k, ER~47%)
2. `tginfo` — 83k, ER~24%
3. `rozetked` — 658k, ER~16%
4. `lagomvpn` — 230k, ER~22%
5. `amnezia_vpn_news_ru` — 517k, ER~19%

Приоритет 2: `quattrovpn_news` (огромный), `roskomsvoboda` (права/блоки).

Пропуск: `it_teech` / `techno_novinki` (⛔), `vpn1_news` (hijack), `hightech_fm` (мало + ER&lt;12%), политика.

## Запуск

- Вкладка «Все остальное» + «Слаги»; заметка у technoinsider: эталон гибрида.
- Admin gate: кампании `tga_…` в Marketing Panel **до** Create Ad.
- Формат: `tga_c_{cr}_{tx}_s_{slug}_eur`, destination `@surfvpn`.
- Тест: Initial/Daily €8, Daily views 1, On Hold, CPM Channels €1.50.
- CTR ≥10% после ~1k impressions → On Hold в тот же день.
