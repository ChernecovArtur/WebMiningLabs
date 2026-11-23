import json
from pathlib import Path

import requests


BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "city_dishes.json"

CITY_PAGES = {
    "Пермь": [
        "Посикунчики",
        "Пельмени",
        "Шаньги",
    ],
    "Кунгур": [
        "Посикунчики",
        "Пельмени",
        "Шаньги",
    ],
    "Москва": [
        "Русская кухня",
        "Кулебяка",
        "Расстегай",
    ],
    "Санкт-Петербург": [
        "Русская кухня",
        "Корюшка",
        "Расстегай",
    ],
    "Казань": [
        "Татарская кухня",
        "Чак-чак",
        "Эчпочмак",
        "Кыстыбый",
    ],
    "Уфа": [
        "Башкирская кухня",
        "Чак-чак",
        "Эчпочмак",
    ],
    "Новосибирск": [
        "Сибирская кухня",
        "Пельмени",
    ],
    "Хабаровск": [
        "Дальневосточная кухня",
        "Уха",
    ],
    "Петрозаводск": [
        "Карельская кухня",
        "Калитки",
        "Лохикейтто",
    ],
}

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

titles = sorted({
    title
    for pages in CITY_PAGES.values()
    for title in pages
})

response = requests.get(
    "https://ru.wikipedia.org/w/api.php",
    params={
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "redirects": "1",
        "titles": "|".join(titles),
    },
    headers={"User-Agent": "EducationalLab/1.0"},
    timeout=60,
)
response.raise_for_status()

pages = response.json().get("query", {}).get("pages", [])
texts = {}

for page in pages:
    revisions = page.get("revisions", [])

    if not revisions:
        continue

    text = revisions[0].get(
        "slots", {}
    ).get("main", {}).get("content", "").lower()

    texts[page["title"]] = text

# Учитываем переадресации, чтобы найти текст по исходному названию
for redirect in response.json().get("query", {}).get("redirects", []):
    source = redirect["from"]
    target = redirect["to"]

    if target in texts:
        texts[source] = texts[target]

for city, city_pages in CITY_PAGES.items():
    old = result[city]
    old_count = old["page_count"]
    added_count = 0
    mentions = {
        dish: old["dishes"].get(dish, 0) * old_count
        for dish in DISHES
    }

    for title in city_pages:
        text = texts.get(title)

        if text is None:
            print(f"{city}: страница не найдена — {title}")
            continue

        for dish, variants in DISHES.items():
            if any(variant in text for variant in variants):
                mentions[dish] += 1

        old["pages"].append(f"{title} — Wikipedia")
        added_count += 1

    total_count = old_count + added_count

    result[city] = {
        "page_count": total_count,
        "pages": old["pages"],
        "dishes": {
            dish: count / total_count
            for dish, count in mentions.items()
        },
    }

    print(f"{city}: добавлено страниц {added_count}")

DATA_FILE.write_text(
    json.dumps(result, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"Файл обновлён: {DATA_FILE}")