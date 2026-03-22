"""
Диагностика: смотрим структуру __NEXT_DATA__ на OLX.uz
Запусти один раз: python olx_debug.py
"""

import json
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://www.olx.uz/",
})

print("Загружаю страницу...")
resp = session.get(TARGET_URL, timeout=20)
print(f"HTTP статус: {resp.status_code}")
print(f"Размер ответа: {len(resp.content)} байт")

soup = BeautifulSoup(resp.text, "html.parser")

# ── 1. Проверяем __NEXT_DATA__ ─────────────────────────────
tag = soup.find("script", {"id": "__NEXT_DATA__"})
if not tag:
    print("\n❌ __NEXT_DATA__ НЕ НАЙДЕН")
else:
    print("\n✅ __NEXT_DATA__ найден")
    try:
        data = json.loads(tag.string)

        # Сохраняем полный JSON для изучения
        with open("next_data_full.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("📄 Полный JSON сохранён в: next_data_full.json")

        # Показываем верхний уровень ключей
        print(f"\nВерхние ключи: {list(data.keys())}")

        props = data.get("props", {})
        print(f"props ключи: {list(props.keys())}")

        page_props = props.get("pageProps", {})
        print(f"pageProps ключи: {list(page_props.keys())}")

        # Ищем объявления по разным путям
        paths_to_check = [
            ["props", "pageProps", "ads"],
            ["props", "pageProps", "data", "ads"],
            ["props", "pageProps", "listing", "ads"],
            ["props", "pageProps", "initialProps", "ads"],
            ["props", "pageProps", "offers"],
            ["props", "pageProps", "data", "offers"],
        ]

        for path in paths_to_check:
            obj = data
            for key in path:
                if isinstance(obj, dict):
                    obj = obj.get(key)
                else:
                    obj = None
                    break
            if obj and isinstance(obj, list) and len(obj) > 0:
                print(f"\n✅ Объявления найдены по пути: {' → '.join(path)}")
                print(f"   Количество: {len(obj)}")
                print(f"\n   Ключи первого объявления: {list(obj[0].keys())}")
                print(f"\n   Первое объявление (сокращённо):")
                first = obj[0]
                for k, v in first.items():
                    val_str = str(v)[:120]
                    print(f"     {k}: {val_str}")
                break
        else:
            print("\n⚠️  Объявления не найдены по стандартным путям")
            print("   Ищу любые списки с ключами похожими на объявления...")

            def find_lists(obj, path="root", depth=0):
                if depth > 5:
                    return
                if isinstance(obj, list) and len(obj) >= 5:
                    if isinstance(obj[0], dict) and any(
                        k in obj[0] for k in ("id", "title", "url", "href", "price")
                    ):
                        print(f"   Возможно объявления: {path} (кол-во: {len(obj)})")
                        print(f"   Ключи: {list(obj[0].keys())[:15]}")
                elif isinstance(obj, dict):
                    for k, v in obj.items():
                        find_lists(v, f"{path}.{k}", depth + 1)

            find_lists(data)

    except Exception as e:
        print(f"❌ Ошибка парсинга JSON: {e}")

# ── 2. Проверяем CSS-карточки ──────────────────────────────
cards = soup.select("[data-cy='l-card']")
print(f"\n── CSS карточки [data-cy='l-card']: {len(cards)} шт.")

# ── 3. Ищем ссылки на объявления ──────────────────────────
links = soup.find_all("a", href=re.compile(r"/d/obyavlenie/"))
unique_ids = set()
for a in links:
    m = re.search(r"-(ID[A-Za-z0-9]+)\.html", a.get("href", ""))
    if m:
        unique_ids.add(m.group(1))
print(f"── Уникальных ID объявлений в HTML: {len(unique_ids)}")
if unique_ids:
    sample = list(unique_ids)[:5]
    print(f"   Примеры: {sample}")

print("\n✅ Диагностика завершена.")
print("Открой next_data_full.json и найди путь к массиву объявлений.")
