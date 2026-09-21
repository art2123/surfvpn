# Surf VPN — общее

Рабочая документация и ops Telegram Ads. Кода продукта в этом репозитории нет.

**SoT** (source of truth) — единственный источник правды по теме. При конфликте побеждает он, не локальный CSV и не `blnc/`.

| Тема | SoT |
|---|---|
| Что можно обещать в рекламе | [техспека.md](техспека.md) |
| Макросы поддержки | [поддержка.md](поддержка.md) |
| Инвентарь, Связки, статусы ads | [Google Sheet](https://docs.google.com/spreadsheets/d/1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI/edit) |
| Поля кабинета / лестница CPM | [tgads-кабинет.md](tgads-кабинет.md) |
| Нейминг `tga_` | [tgads-нейминг.md](tgads-нейминг.md) |

`blnc/` в корне репо — локальный архив конкурента. Можно открыть конкретный файл. Не коммитить и никуда не грузить. Факты про Surf оттуда не брать.

## Куда класть файлы

| Папка | Что |
|---|---|
| этот корень | живые md и кэши CSV (таблица важнее CSV) |
| [scripts/](scripts/) | повторяемые скрипты |
| [archive/](archive/) | паки/батчи после заливки |
| [tmp/](tmp/) | одноразовые `_tmp_*` (можно удалять) |
| [tgads-snapshots/](tgads-snapshots/) | слепки кабинета и Связок |
| [imports/](imports/) | дроп CSV/JSON с Telemetr/TGStat |
| [secrets/](secrets/) | куки, профили браузера, разовые JSON |

Не класть одноразовые `.py`/`.json` в этот корень.

## Живые документы

| Файл | О чём |
|---|---|
| [техспека.md](техспека.md) | Витрина + смарты/роутинг: что можно обещать в рекламе |
| [поддержка.md](поддержка.md) | Макросы поддержки |
| [продукт.md](продукт.md) | Воронка входа, A/B, команда |
| [цифры.md](цифры.md) | Срез админки (сток, деньги) — может устареть |
| [метрики.md](метрики.md) | SUR-1: NSM, activation |
| [posthog.md](posthog.md) | SUR-2: доски и события |
| [рост.md](рост.md) | 8 недель: PPC, рассылки, Директ |
| [бэклог.md](бэклог.md) | Linear |
| [tgads-кабинет.md](tgads-кабинет.md) | Create Ad и лестница CPM |
| [tgads-нейминг.md](tgads-нейминг.md) | `tga_{pl}_{cr}_{tx}_{scope}_{slug}_{cab}` |
| [tgads-api.md](tgads-api.md) | Внутренний RPC кабинета |
| [tgads-мертвые-площадки.md](tgads-мертвые-площадки.md) | Рабочий список мёртвых |
| [tgads-quality-media.md](tgads-quality-media.md) | Гибриды / качество медиа |
| [tgmaps-vpn-digest.md](tgmaps-vpn-digest.md) | Дайджест tgmaps |
| [tgads-competitor-digest.md](tgads-competitor-digest.md) | Дайджест конкурентов |

Правило: админку не дублировать. PostHog — воронка, эксперимент, канал, коннект. Деньги lifetime — в панели.

Частые команды:

```bash
python общее/scripts/export_tgads_admin_campaigns.py
python общее/scripts/snapshot_cabinet_ads.py path/to/adslist.json
python общее/scripts/tgads_pace_check.py [--apply]
```
