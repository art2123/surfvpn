# Кабинет Telegram Ads — настройки объявления

Снято с формы **Create Your Ad** (`https://ads.telegram.org/account/ad/new`) 13 сентября 2026, аккаунт **TLGM / getSurfVPN // CR_Telegram Ads (2)**, бюджет **€1,000.00**.

Дальше в чатах и брифах — **эти лейблы**, не «кампания / ключи / объява». Именование связки и `?start` — в [tgads-нейминг.md](tgads-нейминг.md). Инвентарь площадок — [Surfvpn - tgads](https://docs.google.com/spreadsheets/d/1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI/edit).

Жёстко:

- **Target parameters can't be changed after the ad is created.**
- Пустой таргет → *Will not be shown anywhere.*
- Destination — [@surfvpn](https://t.me/surfvpn). В метке кодируем, **где показали** и **кого таргетили**.

---

## Креатив

| Поле в кабинете | Зачем | Дефолт / заметка |
|---|---|---|
| **Ad title** | Только в кабинете | = код связки `tga_…` |
| **Ad text** | Текст, который видит человек | Кастомные эмодзи через [@AdsMarkdownBot](https://t.me/AdsMarkdownBot); номер `t01`… сквозной |
| **URL you want to promote** | Куда ведёт кнопка | Channels/Bots/Users: `https://t.me/surfvpn?start=tga_…`. **Search:** `https://t.me/surfvpn` без метки |
| **Ad Button** | Текст кнопки | Для бота **OPEN** |
| **Ad photo or video** | Картинка или видео | Upload; номер `i01`/`v01` сквозной |
| **Website name** | Имя над текстом, если URL — сайт | Для бота обычно скрыто |
| **Show picture** | Превью сайта | чекбокс |
| **Conversion event** | Цель пикселя на сайте | *Create a pixel first (optional)* |

**Ad Button:** OPEN WEBSITE, SUBSCRIBE, VIEW, READ, LEARN MORE, DOWNLOAD, OPEN, SIGN UP, BUY, ORDER, PLAY, TRY, LEAVE A REQUEST.

Пиксель и Conversion event — только если ведём на сайт. На бот не нужны.

---

## Деньги, частота, статус

| Поле в кабинете | Зачем | Дефолт на старте |
|---|---|---|
| **CPM in Euro** | Потолок ставки за 1000 показов (аукцион second-price) | см. таблицу ниже |
| **Initial budget in Euro** | Сколько кладём на объявление | **€8** (коридор 5–10) |
| **Daily budget in Euro** | Потолок в день, **Set daily limit** | **= Initial budget** (€8), чтобы за день не сжечь больше теста |
| **Daily views limit per user** | Показов одному человеку за сутки | **1** |
| **Initial status** | После модерации | **On Hold**, Active — руками когда креатив и CPM проверены |
| **Start date / End date** | Вкл / пауза по времени | выкл |
| **Ad Schedule** | Почасовка | выкл |

CPM и бюджеты **не** входят в `?start`. CPM и бюджет после создания обычно можно править; таргет — нет.

### Какой CPM ставить

Текущий кабинет **TLGM / getSurfVPN** — EUR (`_eur` в коде связки). Ставки TON и евро не сравнивать как одно число.

Ориентиры RU VPN (EUR-кабинет, 2026): ниша ~€1.5–2.5, гео CIS дешевле западного. У Blanc на похожих каналах фактический CPM часто выходил примерно €2–6 при живой отдаче.

Стартовые потолки (пока нет своей статистики):

| Target | Стартовый CPM | Почему |
|---|---|---|
| Channels, один канал | **€1.50** | узкий слот, часто дешевле широкого Users |
| Channels, список `c01`… | **€2.00** | несколько аукционов сразу |
| Bots | **€2.00** | |
| Search | **€2.00** | |
| Users | **€2.50** | широкий аукцион, легче переплатить |

Как понимать, что ставка живая, а не скрутка:

1. После Active смотреть 4–6 часов (не минуты).
2. **0 показов** → поднять CPM на €0.30–0.50, не удваивать.
3. **≥80% дневного бюджета за <3 часа** → скрутка, опустить CPM на ~20% (бюджет €8 уже спас от большого слива).
4. Норма теста: бюджет доживает до вечера, есть показы, CPC не прыгает в несколько раз относительно соседних связок.
5. Если кабинет после заполнения таргета показывает recommended range — стартовать **у нижней границы**, не в середине.
6. Не сравнивать CPM Channels и Users как одно число: разный аукцион.
7. Масштаб (бюджет > €10) — только когда на €8 уже есть старты бота, не «чтобы быстрее набрать показы».

€8 при CPM €1.50 ≈ 5.3k показов на тест; при €8 CPM — всего ~1k и деньги кончатся быстро. Поэтому сначала крутим частоту ставки, не размер кошелька.

### Скликивание

CTR **≥10%** — не «удачный креатив», а кандидат в отключение: в канале часто стоит зловред, который кликает чужую рекламу. Платим за клики, до бота люди не доходят.

Порог считать по связке в кабинете, не по одному часу. Минимум порядка **1 000 показов**, иначе 8 кликов из 70 — шум.

Что делать:

1. CTR ≥10% → **On Hold** в тот же день, не «ещё посмотреть».
2. Сверить клики с стартами `@surfvpn` по этой метке. Много кликов, мало/ноль `bot_start` — склик подтверждён.
3. Есть старты и оплаты при высоком CTR — всё равно пауза и разбор: на VPN 10%+ CTR почти не бывает без накрутки.
4. `scope=s` (один канал) → в **Слаги** пометка «склик», больше не включать в списки и не запускать отдельно.
5. `scope=l` (набор) → пауза всего набора. Кто именно кликер — неизвестно, пока каналы не разнесены по одиночным связкам.
6. Search: метки нет, смотреть только CTR в кабинете; тот же порог 10%.

Нормальный CTR для сравнения: единицы процента (часто ~1–4%). 6–9% — жёлтая зона, смотреть конверсию в старт, не масштабировать.

---

## Target

Четыре вкладки — это четыре разных продукта. В форме дефолт: **Channels**. Код в `start_param`: Search `s`, Bots `b`, Users `u`, Channels `c`.

### Search

- **Target search queries** — список запросов (`Add search queries`).

### Bots

- **Target specific bots** — `t.me bot URL`.
- **Add similar bots** — похожие боты по выбранным.

### Users

Аудитория людей, не конкретный канал:

- **Target countries**
- **Target locations** — город, район (`Search locations by country`)
- **Target user languages**
- **Target topics** (+ *Only target users interested in all selected topics*)
- **Target channel audiences** — аудитория указанных каналов
- **Target device type:** All devices / iOS / Android / Mobile / Desktop
- **Show this ad in channels related to Politics & Incidents only**
- **Exclude topics**
- **Exclude channel audiences**
- **Do not show this ad in channels related to Politics & Incidents**

### Channels

То, что бьётся с вкладками инвентаря в таблице:

- **Target channel languages** — `Select languages (optional)`
- **Target topics** — `Select topics (optional)`
- **Target specific channels** — `t.me channel URL (optional)` + **Add similar channels**
- **Exclude topics**
- **Exclude specific channels** — `t.me channel URL to exclude`
- **Ad placement:** **Message in Channel** (дефолт) или **Banner in Video**

---

## Topics

Один список на include и exclude (Users и Channels):

Art & Design, Bets & Gambling, Books, Business & Entrepreneurship, Cars & Other Vehicles, Celebrities & Lifestyle, Cryptocurrencies, Culture & Events, Curious Facts, Directories of Channels & Bots, Economy & Finance, Education, Fashion & Beauty, Fitness, Food & Cooking, Foreign Language Learning, Health & Medicine, History, Hobbies & Activities, Home & Architecture, Humor & Memes, Investments, Job Listings, Kids & Parenting, Marketing & PR, Motivation & Self-development, Movies, Music, Offers & Promotions, Pets, Politics & Incidents, Psychology & Relationships, Real Estate, Recreation & Entertainment, Religion & Spirituality, Science, Sports, Technology & Internet, Travel & Tourism, Video Games, Other.

---

## Бриф одной связки

Без этих семи пунктов объявление не создаём:

1. **Target:** Search / Bots / Users / Channels
2. **URL you want to promote** — `t.me/surfvpn?start=…`, для Search без метки
3. **Ad title** (= код связки), **Ad text** (`t01`…), **Ad photo or video** (`i01`…), **Ad Button**
4. **CPM in Euro** по таблице + **Initial budget €8** + **Daily budget €8**
5. Таргет: каналы / боты / запросы; slug из **Слаги** или номер списка
6. **Initial status:** On Hold
7. **Daily views limit per user:** 1
