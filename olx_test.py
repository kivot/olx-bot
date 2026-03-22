"""
Тест парсера — запусти и сравни с браузером.
python olx_test.py
"""

import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

TARGET_URL = (
    "https://www.olx.uz/transport/legkovye-avtomobili/chevrolet/"
    "?currency=UZS"
    "&search%5Border%5D=created_at%3Adesc"
    "&search%5Bfilter_enum_model%5D%5B0%5D=cobalt"
)

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
})

RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

def parse_date(text):
    now = datetime.now()
    m = re.match(r"Сегодня в (\d{1,2}):(\d{2})", text)
    if m:
        return now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    m = re.match(r"Вчера в (\d{1,2}):(\d{2})", text)
    if m:
        return (now - timedelta(days=1)).replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", text)
    if m:
        month = RU_MONTHS.get(m.group(2).lower())
        if month:
            return datetime(int(m.group(3)), month, int(m.group(1)))
    return None

print(f"Загружаю страницу: {datetime.now():%H:%M:%S}")
resp = session.get(TARGET_URL, timeout=20)
print(f"HTTP {resp.status_code} | {len(resp.content):,} байт\n")

soup = BeautifulSoup(resp.text, "html.parser")
cards = soup.select("[data-cy='l-card']")
print(f"Найдено карточек: {len(cards)}\n")
print("─" * 80)

DATE_RE = re.compile(
    r"(Сегодня в \d{1,2}:\d{2}|Вчера в \d{1,2}:\d{2}|\d{1,2}\s+\w+\s+\d{4}[^\n]*)"
)

now = datetime.now()
print(f"{'#':<3} {'ID':<12} {'Дата':<22} {'Возраст':<12} {'Заголовок'}")
print("─" * 80)

for i, card in enumerate(cards, 1):
    link = card.select_one("a[href*='/d/obyavlenie/']")
    if not link:
        continue
    href = link.get("href", "")
    url = ("https://www.olx.uz" + href if href.startswith("/") else href).split("?")[0]
    m = re.search(r"-(ID[A-Za-z0-9]+)\.html", url)
    lid = m.group(1) if m else "???"

    title_tag = card.select_one("h4, h6, h3")
    title = title_tag.get_text(strip=True)[:35] if title_tag else "—"

    full = card.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in full.splitlines() if l.strip()]

    posted_at = "—"
    posted_dt = None
    for line in lines:
        dm = DATE_RE.search(line)
        if dm:
            posted_at = dm.group(1).strip()
            posted_dt = parse_date(posted_at)
            break

    if posted_dt:
        age_mins = int((now - posted_dt).total_seconds() / 60)
        if age_mins < 60:
            age_str = f"{age_mins}м назад"
        elif age_mins < 1440:
            age_str = f"{age_mins//60}ч {age_mins%60}м"
        else:
            age_str = f"{age_mins//1440}д назад"
    else:
        age_str = "НЕ РАСПОЗНАНА"

    print(f"{i:<3} {lid:<12} {posted_at:<22} {age_str:<12} {title}")

print("─" * 80)
print(f"\nВремя парсинга: {datetime.now():%H:%M:%S}")
print("\nСравни список выше с тем что видишь в браузере.")
print("Если объявление есть в браузере но нет здесь — бот его не видит.")
print("Если есть здесь но 'Возраст' = НЕ РАСПОЗНАНА — дата не парсится.")
