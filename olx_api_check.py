"""
Диагностика API OLX — запусти: python olx_api_check.py
"""
import json
import requests
from datetime import datetime, timezone, timedelta

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

TZ_TASHKENT = timezone(timedelta(hours=5))
now_utc = datetime.now(timezone.utc)
print(f"Сейчас UTC:      {now_utc:%H:%M:%S}")
print(f"Сейчас Ташкент:  {now_utc.astimezone(TZ_TASHKENT):%H:%M:%S}")
print()

# Пробуем разные варианты category_id
print("=== Тест 1: разные category_id ===")
for cat_id in [108, 11, 80, 84, 1]:
    url = f"https://www.olx.uz/api/v1/offers/?offset=0&limit=5&sort_by=created_at%3Adesc&filter_enum_model%5B0%5D=cobalt&category_id={cat_id}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        count = len(data.get("data", []))
        total = data.get("metadata", {}).get("total_elements", "?")
        print(f"  category_id={cat_id}: получено={count}, всего={total}")
    except Exception as e:
        print(f"  category_id={cat_id}: ошибка {e}")

print()
print("=== Тест 2: поиск по ключевому слову 'cobalt' ===")
url = "https://www.olx.uz/api/v1/offers/?offset=0&limit=10&sort_by=created_at%3Adesc&query=cobalt"
try:
    r = requests.get(url, headers=headers, timeout=10)
    data = r.json()
    ads = data.get("data", [])
    total = data.get("metadata", {}).get("total_elements", "?")
    print(f"  Найдено: {len(ads)}, всего в базе: {total}")
    if ads:
        print(f"  Ключи объявления: {list(ads[0].keys())}")
except Exception as e:
    print(f"  Ошибка: {e}")

print()
print("=== Тест 3: без category_id ===")
url = "https://www.olx.uz/api/v1/offers/?offset=0&limit=50&sort_by=created_at%3Adesc&filter_enum_model%5B0%5D=cobalt"
try:
    r = requests.get(url, headers=headers, timeout=10)
    data = r.json()
    ads = data.get("data", [])
    total = data.get("metadata", {}).get("total_elements", "?")
    print(f"  Найдено: {len(ads)}, всего: {total}")

    if ads:
        # Показываем первые 5 с датами
        print(f"\n  Топ-5 объявлений:")
        for ad in ads[:5]:
            created = ad.get("created_time", "")
            refresh = ad.get("last_refresh_time", "")
            title = ad.get("title", "")[:40]

            dt_created = datetime.fromisoformat(created) if created else None
            dt_refresh = datetime.fromisoformat(refresh) if refresh else None

            age_c = int((now_utc - dt_created).total_seconds() / 60) if dt_created else "?"
            age_r = int((now_utc - dt_refresh).total_seconds() / 60) if dt_refresh else "?"

            created_tashkent = dt_created.astimezone(TZ_TASHKENT).strftime("%H:%M") if dt_created else "?"
            refresh_tashkent = dt_refresh.astimezone(TZ_TASHKENT).strftime("%H:%M") if dt_refresh else "?"

            print(f"  [{ad['id']}] {title}")
            print(f"    created:  {created_tashkent} по Ташкенту ({age_c} мин назад по UTC)")
            print(f"    refresh:  {refresh_tashkent} по Ташкенту ({age_r} мин назад по UTC)")

        # Сохраняем полный ответ
        with open("api_check_result.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n  Полный ответ сохранён в api_check_result.json")
except Exception as e:
    print(f"  Ошибка: {e}")
