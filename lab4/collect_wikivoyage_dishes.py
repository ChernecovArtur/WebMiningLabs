import json
from pathlib import Path

import requests


BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "city_dishes.json"

CITIES = [
    "Пермь",
    "Кунгур",
    "Москва",
    "Санкт-Петербург",
    "Казань",
    "Уфа",
    "Новосибирск",
    "Хабаровск",
    "Петрозаводск",
]

DISHES = {
    "посикунчики": ["посикунчик", "посикунчики"],
    "пестики": ["пестики"],
    "шаньги": ["шаньга", "шаньги", "шанежка", "шанежки"],
    "чак-чак": ["чак-чак", "чакчак"],
    "эчпочмак": ["эчпочмак", "эчпочмаки"],
    "кыстыбый": ["кыстыбый"],
    "губадия": ["губадия"],
    "элеш": ["элеш"],
    "бешбармак": ["бешбармак"],
    "калитки": ["калитка", "калитки"],
    "лохикейтто": ["лохикейтто"],
    "султчина": ["султчина"],
    "корюшка": ["корюшка"],
    "кулебяка": ["кулебяка"],
    "расстегай": ["расстегай"],
    "курник": ["курник"],
    "калач": ["калач"],
    "пирог": ["пирог"],
    "уха": ["уха"],
    "хе": ["хе"],
    "пельмени": ["пельмени"],
    "борщ": ["борщ"],
    "блины": ["блины"],
    "салат": ["салат"],
}

result = json.loads(DATA_FILE.read_text(encoding="utf-8"))

response = requests.get(
    "https://ru.wikivoyage.org/w/api.php",
    params={
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "redirects": "1",
        "titles": "|".join(CITIES),
    },
    headers={"User-Agent": "EducationalLab/1.0"},
    timeout=60,
)
response.raise_for_status()

pages = response.json().get("query", {}).get("pages", [])
pages_by_title = {page["title"]: page for page in pages}

for city in CITIES:
    page = pages_by_title.get(city)

    if not page:
        print(f"{city}: страница не найдена")
        continue

    revisions = page.get("revisions", [])

    if not revisions:
        continue

    text = revisions[0].get(
        "slots", {}
    ).get("main", {}).get("content", "").lower()

    old = result.get(city, {
        "page_count": 0,
        "pages": [],
        "dishes": {},
    })

    old_count = old["page_count"]
    new_count = old_count + 1
    frequencies = {}

    for dish, variants in DISHES.items():
        old_mentions = old["dishes"].get(dish, 0) * old_count
        new_mention = any(
            variant in text
            for variant in variants
        )

        frequencies[dish] = (
            old_mentions + int(new_mention)
        ) / new_count

    result[city] = {
        "page_count": new_count,
        "pages": old["pages"] + [f"{city} — Викигид"],
        "dishes": frequencies,
    }

    found = sum(
        any(variant in text for variant in variants)
        for variants in DISHES.values()
    )
    print(f"{city}: страница получена, блюд найдено {found}")

DATA_FILE.write_text(
    json.dumps(result, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"Файл обновлён: {DATA_FILE}")