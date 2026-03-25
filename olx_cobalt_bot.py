"""
╔══════════════════════════════════════════════════════════════╗
║       OLX.uz — Мониторинг Chevrolet Cobalt v17              ║
║       + Фильтр стоп-слов (кредит, лизинг, аренда...)       ║
╚══════════════════════════════════════════════════════════════╝

ЗАВИСИМОСТИ:
    pip install requests python-telegram-bot

ЗАПУСК:
    python olx_cobalt_bot.py
"""

import asyncio
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import requests
from telegram import Bot
from telegram.error import TelegramError

# ─────────────────────────────────────────────────────────────
#  ⚙️  CONFIG
# ─────────────────────────────────────────────────────────────

import os
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID   = os.environ["CHAT_ID"]

API_URL = (
    "https://www.olx.uz/api/v1/offers/"
    "?offset=0"
    "&limit=50"
    "&sort_by=last_refresh_time%3Adesc"
    "&filter_enum_model%5B0%5D=cobalt"
)

# ── Фильтры по параметрам ─────────────────────────────────────
PRICE_MIN:   int | None = None   # например: 50_000_000
PRICE_MAX:   int | None = None   # например: 150_000_000
YEAR_MIN:    int | None = None   # например: 2020
YEAR_MAX:    int | None = None   # например: 2023
MILEAGE_MAX: int | None = None   # например: 100_000

# Показывать только объявления поднятые не позднее N часов назад
MAX_AGE_HOURS = 2

CHECK_INTERVAL = 20  # секунды (базовый интервал)

# ─────────────────────────────────────────────────────────────
#  🚫  Стоп-слова
# ─────────────────────────────────────────────────────────────
# Объявления содержащие эти слова в заголовке или описании
# будут автоматически пропущены.

STOP_WORDS = re.compile(
    r"kredit|credit|кредит"          # кредит (рус/лат)
    r"|lizing|leasing|лизинг"        # лизинг (рус/лат)
    r"|arenda|аренда|ijara|ижара"    # аренда (рус/лат/узб)
    r"|nasiya|nasya|рассрочка"       # рассрочка (рус/узб)
    r"|aksiya|акция",                # акция (рус/лат)
    re.IGNORECASE
)

# ─────────────────────────────────────────────────────────────
#  📋  Логирование
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("olx_cobalt_bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  🕐  Время
# ─────────────────────────────────────────────────────────────

TZ_TASHKENT = timezone(timedelta(hours=5))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(s: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def fmt_tashkent(dt: datetime) -> str:
    local = dt.astimezone(TZ_TASHKENT)
    now_local = now_utc().astimezone(TZ_TASHKENT)
    if local.date() == now_local.date():
        return f"Сегодня в {local:%H:%M}"
    elif (now_local.date() - local.date()).days == 1:
        return f"Вчера в {local:%H:%M}"
    else:
        return local.strftime("%d.%m.%Y в %H:%M")

# ─────────────────────────────────────────────────────────────
#  📦  Модель
# ─────────────────────────────────────────────────────────────

@dataclass
class Listing:
    listing_id: int
    title: str
    description: str           # полный текст объявления для проверки стоп-слов
    price: str
    price_num: int
    location: str
    created_dt: datetime
    refresh_dt: datetime
    year: str
    year_num: int
    mileage: str
    mileage_num: int
    url: str
    phone: str = "—"

# ─────────────────────────────────────────────────────────────
#  🌐  API запрос
# ─────────────────────────────────────────────────────────────

USER_AGENTS = [
    # Windows Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Mac Chrome
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Mac Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Windows Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Samsung Galaxy S23) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    # iPhone
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
]


def make_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }


def fetch_listings() -> list[Listing] | None:
    try:
        resp = requests.get(API_URL, headers=make_headers(), timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.error(f"Ошибка API: {e}")
        return None

    ads = data.get("data", [])
    listings = []
    for ad in ads:
        try:
            l = _parse_ad(ad)
            if l:
                listings.append(l)
        except Exception as e:
            log.debug(f"  Ошибка [{ad.get('id')}]: {e}")
    return listings


def _parse_ad(ad: dict) -> Listing | None:
    lid = ad.get("id")
    if not lid:
        return None

    title = ad.get("title", "—")
    description = ad.get("description", "")

    url_raw = ad.get("url", "")
    url = ("https://www.olx.uz" + url_raw if url_raw.startswith("/") else url_raw).split("?")[0]

    created_dt = parse_iso(ad.get("created_time", ""))
    refresh_dt = parse_iso(ad.get("last_refresh_time", ""))
    if not created_dt or not refresh_dt:
        return None

    # Цена
    price_num, price_str = 0, "—"
    for p in ad.get("params", []):
        if p.get("key") == "price":
            val = p.get("value", {})
            price_num = int(val.get("value", 0) or 0)
            currency = val.get("currency", "сум")
            negotiable = val.get("negotiable", False)
            price_str = (
                f"{price_num:,}".replace(",", " ") + f" {currency}"
                + (" (Договорная)" if negotiable else "")
                if price_num else "Договорная"
            )
            break

    # Год и пробег
    year, year_num, mileage, mileage_num = "—", 0, "—", 0
    for p in ad.get("params", []):
        key = p.get("key", "")
        val = p.get("value", {})
        label = str(val.get("label", "") or val.get("key", "") or "")

        if key == "year" and re.match(r"^20\d{2}$", label):
            year, year_num = label, int(label)

        if key == "mileage":
            digits = re.sub(r"[^\d]", "", label)
            if digits:
                mileage_num = int(digits)
                mileage = f"{mileage_num:,}".replace(",", " ") + " км"

    if year == "—":
        ym = re.search(r"\b(20[012]\d)\b", title)
        if ym:
            year, year_num = ym.group(1), int(ym.group(1))

    loc = ad.get("location", {})
    city = loc.get("city", {}).get("name", "")
    district = loc.get("district", {}).get("name", "")
    location = ", ".join(filter(None, [city, district])) or "—"

    return Listing(
        listing_id=lid, title=title, description=description,
        price=price_str, price_num=price_num,
        location=location,
        created_dt=created_dt, refresh_dt=refresh_dt,
        year=year, year_num=year_num,
        mileage=mileage, mileage_num=mileage_num,
        url=url,
    )

# ─────────────────────────────────────────────────────────────
#  🔍  Фильтры
# ─────────────────────────────────────────────────────────────

def has_stop_words(l: Listing) -> bool:
    """True если заголовок или описание содержат стоп-слова."""
    text = f"{l.title} {l.description}"
    return bool(STOP_WORDS.search(text))


def passes_filters(l: Listing) -> bool:
    if PRICE_MIN and l.price_num and l.price_num < PRICE_MIN:
        return False
    if PRICE_MAX and l.price_num and l.price_num > PRICE_MAX:
        return False
    if YEAR_MIN and l.year_num and l.year_num < YEAR_MIN:
        return False
    if YEAR_MAX and l.year_num and l.year_num > YEAR_MAX:
        return False
    if MILEAGE_MAX and l.mileage_num and l.mileage_num > MILEAGE_MAX:
        return False
    if has_stop_words(l):
        return False
    return True


def is_fresh(l: Listing) -> bool:
    return (now_utc() - l.refresh_dt) <= timedelta(hours=MAX_AGE_HOURS)

# ─────────────────────────────────────────────────────────────
#  📞  Телефон
# ─────────────────────────────────────────────────────────────

def get_phone(l: Listing) -> str:
    try:
        resp = requests.get(
            f"https://www.olx.uz/api/v1/offers/{l.listing_id}/phones/",
            headers={**make_headers(), "Referer": l.url},
            timeout=10,
        )
        if resp.status_code == 200:
            phones = resp.json().get("data", [])
            if phones:
                p = phones[0]
                return p.get("phone", str(p)) if isinstance(p, dict) else str(p)
    except Exception as e:
        log.debug(f"  Phones API: {e}")
    return "—"

# ─────────────────────────────────────────────────────────────
#  📨  Форматирование
# ─────────────────────────────────────────────────────────────

def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_message(l: Listing) -> str:
    if l.phone and l.phone != "—":
        clean = re.sub(r"[^\d+]", "", l.phone)
        phone_line = f"\n📞 <a href='tel:{clean}'>{esc(l.phone)}</a>"
    else:
        phone_line = f"\n📞 <a href='{l.url}'>Показать номер</a>"

    posted = fmt_tashkent(l.refresh_dt)

    return (
        f"🚗 <b>Новый Chevrolet Cobalt!</b>\n\n"
        f"📌 <b>{esc(l.title)}</b>\n"
        f"💰 {esc(l.price)}\n"
        f"📅 Год: <b>{esc(l.year)}</b>  |  🛣 Пробег: <b>{esc(l.mileage)}</b>\n"
        f"📍 {esc(l.location)}\n"
        f"🕐 {posted}"
        f"{phone_line}\n\n"
        f"🔗 <a href='{l.url}'>Открыть объявление</a>"
    )

# ─────────────────────────────────────────────────────────────
#  🤖  Отправка
# ─────────────────────────────────────────────────────────────

async def send_listing(bot: Bot, l: Listing):
    loop = asyncio.get_event_loop()
    try:
        l.phone = await asyncio.wait_for(
            loop.run_in_executor(None, get_phone, l),
            timeout=10,
        )
        log.info(f"    📞 {l.phone}")
    except asyncio.TimeoutError:
        l.phone = "—"

    await bot.send_message(
        chat_id=CHAT_ID,
        text=format_message(l),
        parse_mode="HTML",
        disable_web_page_preview=False,
    )
    await asyncio.sleep(0.5)

# ─────────────────────────────────────────────────────────────
#  🚀  Основной цикл
# ─────────────────────────────────────────────────────────────

async def run():
    bot = Bot(token=BOT_TOKEN)
    seen_ids: set[int] = set()
    check_count = 0

    filter_lines = []
    if PRICE_MIN or PRICE_MAX:
        pmin = f"{PRICE_MIN:,}".replace(",", " ") if PRICE_MIN else "0"
        pmax = f"{PRICE_MAX:,}".replace(",", " ") if PRICE_MAX else "∞"
        filter_lines.append(f"💰 {pmin} — {pmax} сум")
    if YEAR_MIN or YEAR_MAX:
        filter_lines.append(f"📅 {YEAR_MIN or '...'} — {YEAR_MAX or '...'} год")
    if MILEAGE_MAX:
        filter_lines.append(f"🛣 до {MILEAGE_MAX:,} км".replace(",", " "))
    filter_lines.append(f"⏳ поднято не позднее {MAX_AGE_HOURS} ч. назад")
    filter_lines.append("🚫 без кредита, лизинга, аренды, рассрочки, акций")
    filter_text = "\n".join(filter_lines)

    n = now_utc()
    log.info(
        f"Бот запущен. "
        f"UTC: {n:%H:%M:%S} | "
        f"Ташкент: {n.astimezone(TZ_TASHKENT):%H:%M:%S} | "
        f"MAX_AGE={MAX_AGE_HOURS}ч"
    )

    # Первый запуск — запоминаем все текущие ID
    listings = fetch_listings() or []
    for l in listings:
        seen_ids.add(l.listing_id)

    log.info(f"  Старт: запомнено {len(seen_ids)} ID. Жду новые…")

    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=(
                "✅ <b>OLX Cobalt Bot v17 запущен</b>\n\n"
                "🔍 Chevrolet Cobalt · OLX.uz\n"
                f"⏱ Проверка каждые {CHECK_INTERVAL} сек\n"
                "📞 Автопоиск телефона\n\n"
                f"<b>Фильтры:</b>\n{filter_text}\n\n"
                f"Запомнено {len(seen_ids)} объявлений. Жду новые…"
            ),
            parse_mode="HTML",
        )
    except TelegramError as e:
        log.error(f"Стартовое сообщение: {e}")

    while True:
        check_count += 1
        log.info(f"─── Проверка #{check_count} ───")

        listings = fetch_listings()
        if listings is None:
            await asyncio.sleep(CHECK_INTERVAL + random.randint(-5, 5))
            continue

        current_ids = {l.listing_id for l in listings}
        log.info(f"  Объявлений: {len(listings)}")

        new_listings = [l for l in listings if l.listing_id not in seen_ids]

        if new_listings:
            log.info(f"  🆕 Новых ID: {len(new_listings)}")

            fresh, old = [], []
            for l in new_listings:
                if is_fresh(l):
                    fresh.append(l)
                else:
                    age_h = int((now_utc() - l.refresh_dt).total_seconds() / 3600)
                    log.info(
                        f"  ⏳ Старое ({age_h}ч) [{l.listing_id}] "
                        f"«{l.title[:35]}» — пропуск"
                    )
                    old.append(l)

            log.info(f"  Свежих: {len(fresh)} | Старых: {len(old)}")

            to_send = [l for l in fresh if passes_filters(l)]
            blocked = len(fresh) - len(to_send)
            if blocked:
                # Логируем что именно заблокировано стоп-словами
                for l in fresh:
                    if not passes_filters(l) and has_stop_words(l):
                        m = STOP_WORDS.search(f"{l.title} {l.description}")
                        word = m.group(0) if m else "?"
                        log.info(
                            f"  🚫 Стоп-слово «{word}» [{l.listing_id}] "
                            f"«{l.title[:35]}» — пропуск"
                        )
                log.info(f"  После фильтров: {len(to_send)}")

            for l in to_send:
                age_m = int((now_utc() - l.refresh_dt).total_seconds() / 60)
                log.info(
                    f"  → [{l.listing_id}] «{l.title[:40]}» | "
                    f"{l.year} | {l.mileage} | {fmt_tashkent(l.refresh_dt)} ({age_m}м)"
                )
                try:
                    await send_listing(bot, l)
                    log.info(f"  ✅ Отправлено [{l.listing_id}]")
                except TelegramError as e:
                    log.error(f"  ✗ {e}")

            seen_ids.update(l.listing_id for l in new_listings)
        else:
            log.info("  Новых нет.")

        seen_ids &= current_ids | {l.listing_id for l in new_listings}
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run())
