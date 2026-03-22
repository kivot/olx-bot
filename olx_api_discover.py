"""
Ищем внутренний API OLX.uz
Запусти: python olx_api_discover.py
"""

import json
import requests

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9",
})

# Пробуем разные варианты API endpoint
endpoints = [
    # Вариант 1: стандартный OLX API
    "https://www.olx.uz/api/v1/offers/?offset=0&limit=10&sort_by=created_at%3Adesc&filter_enum_model%5B0%5D=cobalt&category_id=108",
    # Вариант 2: другой category_id
    "https://www.olx.uz/api/v1/offers/?offset=0&limit=10&sort_by=created_at%3Adesc&filter_enum_model%5B0%5D=cobalt&category_id=11",
    # Вариант 3: без category_id
    "https://www.olx.uz/api/v1/offers/?offset=0&limit=10&sort_by=created_at%3Adesc&filter_enum_model%5B0%5D=cobalt",
    # Вариант 4: другой путь
    "https://www.olx.uz/api/v1/offers/?offset=0&limit=10&order=created_at%3Adesc&filter_enum_model%5B0%5D=cobalt",
]

print("Ищем API endpoint...\n")

for url in endpoints:
    try:
        resp = session.get(url, timeout=10)
        print(f"GET {url[:80]}...")
        print(f"  HTTP {resp.status_code} | {len(resp.content)} байт")
        if resp.status_code == 200:
            try:
                data = resp.json()
                print(f"  ✅ JSON получен! Ключи: {list(data.keys())}")
                # Сохраняем ответ
                with open("olx_api_response.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"  💾 Сохранено в olx_api_response.json")

                # Смотрим на объявления
                ads = data.get("data", data.get("ads", data.get("offers", [])))
                if ads and isinstance(ads, list):
                    print(f"  📋 Объявлений: {len(ads)}")
                    if ads:
                        print(f"  Ключи первого: {list(ads[0].keys())}")
                        # Ищем дату
                        for key in ("created_at", "createdAt", "last_refresh_time", "date"):
                            if key in ads[0]:
                                print(f"  📅 Дата ({key}): {ads[0][key]}")
                print()
                break
            except Exception as e:
                print(f"  ⚠️  Не JSON: {e}")
                print(f"  Начало ответа: {resp.text[:200]}")
        print()
    except Exception as e:
        print(f"  ❌ Ошибка: {e}\n")

# Также попробуем найти API через HTML страницы
print("\nИщем API URL в HTML страницы...")
from bs4 import BeautifulSoup

session.headers["Accept"] = "text/html"
resp = session.get(
    "https://www.olx.uz/transport/legkovye-avtomobili/chevrolet/"
    "?currency=UZS&search%5Border%5D=created_at%3Adesc&search%5Bfilter_enum_model%5D%5B0%5D=cobalt",
    timeout=20
)
soup = BeautifulSoup(resp.text, "html.parser")

# Ищем упоминание API в скриптах
for script in soup.find_all("script"):
    text = script.string or ""
    if "api/v1" in text or "apollo" in text.lower():
        # Находим все URL-ы похожие на API
        import re
        urls = re.findall(r'https?://[^\s"\']+api[^\s"\']+', text)
        for u in urls[:5]:
            print(f"  Найден URL: {u}")
