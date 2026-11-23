import json
import time
from pathlib import Path

import requests


BASE_DIR = Path(__file__).parent
OUTPUT_FILE = BASE_DIR / "data" / "city_dishes.json"

API_URL = "https://ru.wikipedia.org/w/api.php"
HEADERS = {
    "User-Agent": "EducationalLab/1.0"
}

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


def get_json(params):
    response = requests.get(
        API_URL,
        params=params,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_city_pages(city):
    search = get_json({
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "list": "search",
        "srsearch": f"{city} традиционная кухня блюда",
        "srlimit": 5,
    })

    titles = [
        item["title"]
        for item in search.get("query", {}).get("search", [])
    ]

    if not titles:
        return []

    data = get_json({
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "titles": "|".join(titles),
    })

    pages = []

    for page in data.get("query", {}).get("pages", []):
        revisions = page.get("revisions", [])

        if not revisions:
            continue

        text = revisions[0].get(
            "slots", {}
        ).get("main", {}).get("content", "")

        pages.append({
            "title": page["title"],
            "text": f'{page["title"]} {text}'.lower(),
        })

    return pages


result = {}

for city in CITIES:
    try:
        pages = get_city_pages(city)
    except requests.RequestException as error:
        print(f"Ошибка для {city}: {error}")
        continue

    frequencies = {}

    for dish, variants in DISHES.items():
        mentions = sum(
            any(variant in page["text"] for variant in variants)
            for page in pages
        )
        frequencies[dish] = mentions / len(pages) if pages else 0

    result[city] = {
        "page_count": len(pages),
        "pages": [page["title"] for page in pages],
        "dishes": frequencies,
    }

    print(f"{city}: страниц {len(pages)}")
    time.sleep(1)

OUTPUT_FILE.write_text(
    json.dumps(result, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"Файл сохранён: {OUTPUT_FILE}")