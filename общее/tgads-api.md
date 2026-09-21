# Внутренний RPC кабинета Telegram Ads

Неофициальный AJAX, которым UI `ads.telegram.org` сам ходит при кликах Save / Create / Edit. Снято из `https://telegram.org/js/promote.js` (и `main-aj.js`) 17 сентября 2026. Это **не** публичный документированный Ads API и **не** Bot API.

Поля формы Create Ad — в [tgads-кабинет.md](tgads-кабинет.md). Именование связок — [tgads-нейминг.md](tgads-нейминг.md). Любой вызов, который меняет объявление, в том же заходе пишем в вкладку **Связки**.

---

## Транспорт

```text
POST https://ads.telegram.org/api?hash=<session_hash>
Content-Type: application/x-www-form-urlencoded
Cookie: сессия кабинета (withCredentials)
```

Обёртка во фронте:

```js
Aj.apiRequest(method, data, onSuccess)
// → $.ajax(Aj.apiUrl, { type: 'POST', data: { ...data, method }, dataType: 'json', xhrFields: { withCredentials: true } })
```

- `Aj.apiUrl` ≈ `/api?hash=…` (hash привязан к сессии; без cookies 401 → `/auth`)
- В теле всегда есть поле `method` = имя RPC
- Ответ JSON: успех с полями вроде `ad`, `error`, иногда `field` (какое поле формы подсветить)
- Вызывать удобнее из уже открытой вкладки кабинета (`Runtime.evaluate` / DevTools), а не с голого curl без сессии

Отдельно в кабинете есть **token** (`revokeToken`, `saveApiSettings` / IP allowlist) — намёк на другой, токенный API. Публичной доки у нас нет; этот файл описывает только UI-RPC.

---

## Методы, которые нам нужны в операционке

Все правки объявления требуют `owner_id` + `ad_id`. После успеха UI обновляет строку через `OwnerAds.updateAd(result.ad)` — у нас параллельно колонка `статус` / `cpm` / `budget` / `daily_budget` в **Связках**.

| method | Параметры | Эквивалент в UI |
|---|---|---|
| **editAdStatus** | `owner_id`, `ad_id`, `active` (`1` Active / `0` On Hold); опц. `activate_date`, `deactivate_date`, `schedule`, `schedule_tz_custom`, `schedule_tz` | Edit Status → Save |
| **editAdCPM** | `owner_id`, `ad_id`, `cpm` | Edit CPM |
| **incrAdBudget** | `owner_id`, `ad_id`, `amount`, часто `popup: 1` | увеличить Budget |
| **decrAdBudget** | `owner_id`, `ad_id`, `amount`; опц. `check_only: 1` (проверка до unlock UI) | Decrease / Withdraw from budget. После недавнего Active — ждать ~5–10 мин, иначе error *recently active* |
| **editAdDailyBudget** | `owner_id`, `ad_id`, `daily_budget`, часто `popup: 1` | Daily budget |
| **editAdTitle** | `owner_id`, `ad_id`, `title` | Edit title (= наш `start_param`) |
| **getAdsList** | `owner_id`, `offset_id` | подгрузка таблицы аккаунта |
| **deleteAd** | `owner_id`, `ad_id`; затем повтор с `confirm_hash` из первого ответа | Delete (двухшагово: confirm → delete). В **Связках** строку не удаляем — `статус=Deleted` |

Пример статуса (как при массовом Active 17.09.2026):

```js
Aj.apiRequest('editAdStatus', {
  owner_id: Aj.state.ownerId,
  ad_id: 33,
  active: 1
}, console.log);
```

---

## Создание и черновики

| method | Параметры (ядро) |
|---|---|
| **createAd** | `owner_id`, `title`, `text`, `button`, `promote_url`, `website_name`, `website_photo`, `media`, `ad_info`, `cpm`, `views_per_user`, `budget`, `daily_budget`, `active`, `target_type`, `placement`, `device`; опц. `picture`, таргет-поля из selectList (`channels`/`bots`/… через `;`), `intersect_topics`, `exclude_politic` / `only_politic`, `exclude_crypto` / `only_crypto`, даты и schedule |
| **checkAdPost** | превью/валидация креатива: `text`, `promote_url`, `button`, `website_*`, `media`, `device`, `target_type`, `placement` |
| **saveAdDraft** / **clearAdDraft** | черновик формы (`clear` — `{ owner_id }`) |
| **editAd** | правка уже созданного (полный набор полей формы, как create) |
| **createDraftFromAd** | `{ owner_id, ad_id }` — клон в форму new |
| **sendTargetToReview** | `{ owner_id, ad_id }` |

Таргет после Create **нельзя** менять (жёсткое правило UI) — `editAd` не обходит это.

---

## Поиск таргетов

| method | Параметры |
|---|---|
| **searchChannel** | `owner_id`, `query`, `field` |
| **searchBot** | `query`, `field` |
| **searchTargetQuery** | `query`, `field` (Search queries) |
| **searchLocation** | params из формы локаций |
| **getSimilarChannels** | `channels`, `for` |
| **getSimilarBots** | `bots` |

---

## Аккаунт, деньги, API-токен

| method | Зачем |
|---|---|
| **sendAddFundsRequest** | заявка на пополнение (поля формы adv_type, budget, …) |
| **incrStarsBudget** | `{ owner_id, amount }` (Stars/TON-контур) |
| **getAccountsForTransfer** / **searchAccountForTransfer** / **linkAccount** | перевод бюджета между аккаунтами |
| **saveAccountInfo** | профиль |
| **saveApiSettings** | `{ owner_id, ip_list }` |
| **revokeToken** | `{ owner_id }` → новый token |
| **revokeStatsUrl** | `{ owner_id, ad_id }` — перевыпуск share-URL статистики |
| **saveAdsColumns** | `{ columns: 'views;clicks;…' }` — видимые колонки таблицы |
| **logOut** | `{}` |

---

## Audiences / Events / Pixel / модерация

Реже нужно для Surf; список полный, чтобы не гадать.

| method | Параметры |
|---|---|
| **updateAudiencesState** | `{ owner_id }` |
| **editAudienceTitle** | `owner_id`, `audience_id`, `title` |
| **createDraftFromAudience** / **deleteAudience** | `owner_id`, `audience_id` |
| **updateEventsState** | `{ owner_id }` |
| **createEvent** | `owner_id`, `title`, `type` |
| **editEventTitle** | `owner_id`, `event_id`, `title` |
| **createPixel** | `{ owner_id }` |
| **deleteEvent** | `owner_id`, `event_id` |
| **loadReviewedAds** / **loadReviewedTargets** | пагинация review-листов |
| **approveTarget** | `target`, `target_hash` |
| **declineTarget** | + `reason_id` |
| **translateAd** | `owner_id`, `ad_id` |

Из `widget-frame.js` ещё **sendVote** (опросы в виджете) — к кабинету рекламы не относится.

---

## Как обновить список

```bash
# скачать актуальный promote.js и перечислить Aj.apiRequest('…')
Invoke-WebRequest https://telegram.org/js/promote.js -OutFile promote.js
# или: python общее/scripts/_extract_tgads_api.py  (если лежит secrets/tgads-js/)
```

Источник правды по именам методов — бандл Telegram, не этот файл. Если hash/версия UI уехали, сверить `Aj.version` в кабинете.

---

## Правила использования у нас

1. Только в сессии нашего кабинета (EUR TLGM / getSurfVPN → суффикс `_eur`).
2. После **любого** мутирующего вызова — синхрон в **Связки** в том же заходе: `editAdStatus`→`статус`, `editAdCPM`→**`cpm`**, бюджеты→`budget`/`daily_budget`. Без обновления колонки правка не считается сделанной (см. алгоритм в [tgads-кабинет.md](tgads-кабинет.md)).
3. Не коммитить `hash`, cookies, `owner_id`, token.
4. Массовые правки (статус/CPM) — через RPC ок; Create Ad по возможности через UI, пока не отлажен полный `createAd` + медиа-upload.
