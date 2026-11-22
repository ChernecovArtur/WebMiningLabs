import re
import time
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

OLD_FILE = BASE_DIR.parent / "lab3" / "news.json"
OUTPUT_FILE = DATA_DIR / "news.json"

TARGET_COUNT = 230
MAX_PAGES = 50

HEADERS = {
    "User-Agent": "EducationalLab/1.0"
}


def text_key(title, summary):
    text = f"{title} {summary}"
    return re.sub(r"\s+", " ", text).strip().lower()


news = pd.read_json(OLD_FILE).to_dict("records")
seen_urls = {item["url"] for item in news}
seen_texts = {
    text_key(item["title"], item.get("summary", ""))
    for item in news
}

session = requests.Session()
session.headers.update(HEADERS)

for page in range(1, MAX_PAGES + 1):
    if len(news) >= TARGET_COUNT:
        break

    url = f"https://pstu.ru/media/news/?PAGEN_1={page}"

    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Ошибка страницы {page}: {error}")
        continue

    soup = BeautifulSoup(response.text, "lxml")
    cards = soup.select("div.card-media")

    for card in cards:
        if len(news) >= TARGET_COUNT:
            break

        title_tag = card.select_one(".card-media__title")
        link_tag = card.select_one("a.card-media__wrap")

        if not title_tag or not link_tag:
            continue

        title = title_tag.get_text(" ", strip=True)
        article_url = urljoin(url, link_tag.get("href"))

        if article_url in seen_urls:
            continue

        try:
            article_response = session.get(
                article_url,
                timeout=30,
            )
            article_response.raise_for_status()
        except requests.RequestException as error:
            print(f"Ошибка новости: {article_url}: {error}")
            continue

        article = BeautifulSoup(
            article_response.text,
            "lxml",
        )
        summary_tag = article.select_one("div.col-md-8 p")
        summary = (
            summary_tag.get_text(" ", strip=True)
            if summary_tag
            else ""
        )

        key = text_key(title, summary)

        if key in seen_texts:
            continue

        date_tag = card.select_one(".card-media__date")
        tags = [
            tag.get_text(" ", strip=True)
            for tag in card.select(".card-media__tags .tag")
        ]

        news.append({
            "title": title,
            "published": (
                date_tag.get_text(" ", strip=True)
                if date_tag
                else ""
            ),
            "url": article_url,
            "summary": summary,
            "tags": "; ".join(tags),
            "source": "pstu.ru",
        })

        seen_urls.add(article_url)
        seen_texts.add(key)
        time.sleep(0.2)

    time.sleep(0.2)

result = pd.DataFrame(news)
result = result.drop_duplicates(subset=["url"], keep="first")

result.to_json(
    OUTPUT_FILE,
    orient="records",
    force_ascii=False,
    indent=2,
)

print(f"Сохранено новостей: {len(result)}")
print(f"Файл: {OUTPUT_FILE}")