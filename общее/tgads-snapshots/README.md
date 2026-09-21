# Слепки TG Ads

Нулевая точка и повторные замеры: CTR (склик ≥10%), **темп слива бюджета / переплата CPM**, нулевые показы после Active.

## Кабинет adsList (предпочтительно)

Снять список объявлений из вкладки `ads.telegram.org/account` (browser CDP) в JSON-файл:
`OwnerAds.getAdsList()` (предпочтительно) или `Aj.apiRequest('adsList', …)`, затем:

```bash
python общее/scripts/snapshot_cabinet_ads.py path/to/adslist.json
```

Пишет:

- `YYYY-MM-DD_HHMMSS_cabinet_ads.json`
- `latest_cabinet_ads.json`
- при повторном снимке — `prev_cabinet_ads.json` (бывший latest)

Поля: `ad_id`, `title`, `status`, `views`, `clicks`, `cpm`, `spent`, `budget`, `daily_budget`, `snapshot_at`.

### Темп слива / переплата CPM

Кабинет не даёт «spent сегодня» — скорость = **Δspent** между двумя слепками. Правило лестницы: [tgads-кабинет.md](../tgads-кабинет.md).

```bash
# через 2–3 часа после первого снимка — второй snapshot_cabinet_ads.py, затем:
python общее/scripts/tgads_pace_check.py
# или явно:
python общее/scripts/tgads_pace_check.py snap_t0.json snap_t1.json

# пометка в Связки.заметка (статус/CPM в кабинете не трогает):
python общее/scripts/tgads_pace_check.py --apply
```

Флаги:

| флаг | условие | заметка |
|---|---|---|
| `быстрый_слив` | ≥50% daily_t0 за &lt;6ч | `быстрый слив …` |
| `переплата_cpm` | ≥80% daily_t0 за &lt;3ч | `переплата CPM …` |

Отчёт: `latest_pace_report.json`. CPM −~20% — только по явной команде после разбора.

## Слепок Связок (+ опционально row scrape)

```bash
python общее/scripts/snapshot_tgads_svyazki.py
python общее/scripts/snapshot_tgads_svyazki.py path/to/cabinet_raw.json
```

Файлы: `YYYY-MM-DD_HHMMSS_Europe-Berlin.json` + `.csv` + `_cabinet.csv`, плюс `latest.json`.

## Baseline

`2026-09-17_161800_Europe-Berlin.*` — до перевода в Active, после заливки кодов в админку. Все 17 live = On Hold, views/clicks/spent = 0.

Первый cabinet-слепок после Active: `2026-09-18_*_cabinet_ads.json` / `latest_cabinet_ads.json` (83 ads). Следующий снимок через 2–3ч → `tgads_pace_check.py [--apply]`.
