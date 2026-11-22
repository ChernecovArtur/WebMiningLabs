from pathlib import Path

import pandas as pd
import requests


BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "products.json"

# Если сбор книг уже запускался, убираем их из набора
frame = pd.read_json(DATA_FILE)
frame = frame[frame["source"] != "books.toscrape.com"]

products = frame.to_dict("records")
seen_urls = {item["url"] for item in products}

response = requests.get(
    "https://dummyjson.com/products?limit=0",
    headers={"User-Agent": "EducationalLab/1.0"},
    timeout=30,
)
response.raise_for_status()

for item in response.json()["products"]:
    product_url = f"https://dummyjson.com/products/{item['id']}"

    if product_url in seen_urls:
        continue

    reviews = item.get("reviews", [])
    review_text = " ".join(
        review.get("comment", "")
        for review in reviews
    )

    products.append({
        "title": item["title"],
        "description": item["description"],
        "review_text": review_text,
        "price": item["price"],
        "rating": item.get("rating"),
        "reviews": len(reviews),
        "url": product_url,
        "category": item.get("category", ""),
        "source": "dummyjson.com",
    })
    seen_urls.add(product_url)

result = pd.DataFrame(products)
result = result.drop_duplicates(subset=["url"], keep="first")

if "review_text" not in result.columns:
    result["review_text"] = ""

result["review_text"] = result["review_text"].fillna("")

result.to_json(
    DATA_FILE,
    orient="records",
    force_ascii=False,
    indent=2,
)

print(f"Всего товаров: {len(result)}")
print(f"Файл: {DATA_FILE}")