"""
Запусти: python olx_find_cards.py
Покажет какие селекторы работают сейчас на OLX.
"""

import re
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
})

print("Загружаю страницу...")
resp = session.get(TARGET_URL, timeout=20)
print(f"HTTP {resp.status_code} | {len(resp.content):,} байт")

# Сохраняем HTML для ручного просмотра
with open("olx_page.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
print("HTML сохранён в olx_page.html\n")

soup = BeautifulSoup(resp.text, "html.parser")

# Проверяем разные селекторы карточек
selectors = [
    "[data-cy='l-card']",
    "[data-testid='l-card']",
    "li[data-cy]",
    "div[data-cy]",
    "[data-cy*='card']",
    "[data-cy*='listing']",
    "article",
    ".css-1sw3lxy",   # типичные OLX классы
    "[class*='listing']",
    "[class*='offer']",
]

print("── Проверяю селекторы карточек ──")
for sel in selectors:
    found = soup.select(sel)
    if found:
        print(f"  ✅ {sel:<35} → {len(found)} шт.")
    else:
        print(f"  ❌ {sel}")

# Ищем ссылки на объявления — они точно есть
print("\n── Ссылки на объявления ──")
links = soup.find_all("a", href=re.compile(r"/d/obyavlenie/"))
unique_ids = set()
for a in links:
    m = re.search(r"-(ID[A-Za-z0-9]+)\.html", a.get("href", ""))
    if m:
        unique_ids.add(m.group(1))
print(f"  Уникальных объявлений: {len(unique_ids)}")

# Смотрим на родительский элемент первой ссылки
if links:
    first = links[0]
    parent = first.parent
    print(f"\n── Родитель первой ссылки ──")
    print(f"  Тег: <{parent.name}>")
    print(f"  data-cy: {parent.get('data-cy', 'нет')}")
    print(f"  data-testid: {parent.get('data-testid', 'нет')}")
    print(f"  class: {parent.get('class', 'нет')}")

    # Поднимаемся выше чтобы найти карточку
    for i in range(5):
        parent = parent.parent
        if not parent:
            break
        cy = parent.get("data-cy", "")
        testid = parent.get("data-testid", "")
        cls = " ".join(parent.get("class", []))[:60]
        print(f"  +{i+1} уровень <{parent.name}> data-cy='{cy}' data-testid='{testid}' class='{cls}'")

print("\nОткрой olx_page.html в браузере и посмотри структуру карточек.")
