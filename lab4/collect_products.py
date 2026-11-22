import json
import time
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

OLD_FILE = BASE_DIR.parent / "lab3" / "products.csv"
OUTPUT_FILE = DATA_DIR / "products.json"

HEADERS = {
    "User-Agent": "EducationalLab/1.0"
}

CATEGORIES = {
    "laptops": (
        "https://webscraper.io/test-sites/"
        "e-commerce/ajax/computers/laptops"
    ),
    "tablets": (
        "https://webscraper.io/test-sites/"
        "e-commerce/ajax/computers/tablets"
    ),
    "phones": (
        "https://webscraper.io/test-sites/"
        "e-commerce/ajax/phones"
    ),
}


# Берём уже собранные товары из прошлой ЛР (lab3 фалй)
products = pd.read_csv(OLD_FILE).to_dict("records")
seen_urls = {item["url"] for item in products}

session = requests.Session()
session.headers.update(HEADERS)

for category, url in CATEGORIES.items():
    response = session.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    container = soup.select_one("div.ecomerce-items-ajax")

    if not container:
        print(f"Данные не найдены: {url}")
        continue

    # В атрибуте находится JSON со всеми товарами категории
    items = json.loads(container["data-items"])

    for item in items:
        product_url = urljoin(
            url,
            f"/test-sites/e-commerce/ajax/product/{item['id']}",
        )

        if product_url in seen_urls:
            continue

        products.append({
            "title": item["title"],
            "description": item["description"],
            "price": item["price"],
            "rating": None,
            "reviews": None,
            "url": product_url,
            "category": category,
            "source": "webscraper.io",
        })
        seen_urls.add(product_url)

    time.sleep(0.5)

result = pd.DataFrame(products)
result = result.drop_duplicates(subset=["url"], keep="first")

result.to_json(
    OUTPUT_FILE,
    orient="records",
    force_ascii=False,
    indent=2,
)

print(f"Сохранено товаров: {len(result)}")
print(f"Файл: {OUTPUT_FILE}")