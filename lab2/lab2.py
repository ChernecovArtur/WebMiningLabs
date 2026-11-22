import json
from pathlib import Path

import requests
import time

API_URL = "https://ru.wikipedia.org/w/api.php"
HEADERS = {
    "User-Agent": "EducationalLab/1.0"
}


def search_articles(query, limit=35):
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
    }

    response = requests.get(
        API_URL,
        params=params,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()

    return response.json()["query"]["search"]


def get_articles(search_results):
    titles = [article["title"] for article in search_results]
    articles = []

    for start in range(0, len(titles), 10):
        batch = titles[start:start + 10]

        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "revisions|links|images|pageimages|pageprops|info",
            "rvprop": "content",
            "rvslots": "main",
            "pllimit": "max",
            "imlimit": "max",
            "pithumbsize": "500",
            "inprop": "url",
            "redirects": "1",
            "titles": "|".join(batch),
        }

        response = requests.get(
            API_URL,
            params=params,
            headers=HEADERS,
            timeout=60
        )
        response.raise_for_status()

        for page in response.json()["query"]["pages"]:
            text = ""
            revisions = page.get("revisions", [])

            if revisions:
                text = revisions[0].get(
                    "slots", {}
                ).get("main", {}).get("content", "")

            articles.append({
                "title": page["title"],
                "url": page.get("fullurl", ""),
                "text": text,
                "links": [
                    link["title"]
                    for link in page.get("links", [])
                ],
                "images": [
                    image["title"]
                    for image in page.get("images", [])
                ],
                "thumbnail": page.get("thumbnail", {}).get("source"),
                "wikidata_id": page.get("pageprops", {}).get("wikibase_item"),
            })

        time.sleep(1)

    return articles

def get_wikidata(articles):
    ids = [
        article["wikidata_id"]
        for article in articles
        if article["wikidata_id"]
    ]

    params = {
        "action": "wbgetentities",
        "format": "json",
        "ids": "|".join(ids),
        "props": "labels|descriptions|claims",
        "languages": "ru|en",
    }

    response = requests.get(
        "https://www.wikidata.org/w/api.php",
        params=params,
        headers=HEADERS,
        timeout=60
    )
    response.raise_for_status()

    entities = []

    for qid, entity in response.json()["entities"].items():
        labels = entity.get("labels", {})
        descriptions = entity.get("descriptions", {})

        entities.append({
            "id": qid,
            "label": labels.get(
                "ru",
                labels.get("en", {})
            ).get("value", ""),
            "description": descriptions.get(
                "ru",
                descriptions.get("en", {})
            ).get("value", ""),
            "properties": list(entity.get("claims", {}).keys()),
        })

    return entities

def get_wiktionary(query):
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": "5",
        "prop": "extracts|info",
        "explaintext": "1",
        "inprop": "url",
    }

    response = requests.get(
        "https://ru.wiktionary.org/w/api.php",
        params=params,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()

    pages = response.json().get("query", {}).get("pages", [])

    return [
        {
            "title": page["title"],
            "url": page.get("fullurl", ""),
            "text": page.get("extract", ""),
        }
        for page in pages
    ]

def get_commons(query):
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": "10",
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": "500",
    }

    response = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params=params,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()

    pages = response.json().get("query", {}).get("pages", [])
    images = []

    for page in pages:
        info = page.get("imageinfo", [{}])[0]

        images.append({
            "title": page["title"],
            "url": info.get("descriptionurl", ""),
            "image_url": info.get("thumburl", info.get("url", "")),
        })

    return images

def main():
    query = input("Введите запрос: ")

    search_results = search_articles(query)
    articles = get_articles(search_results)

    wikidata = get_wikidata(articles)
    wiktionary = get_wiktionary(query)
    commons = get_commons(query)

    result = {
        "query": query,
        "articles": articles,
        "wikidata": wikidata,
        "wiktionary": wiktionary,
        "commons": commons,
    }

    output_file = Path(__file__).with_name("wikimedia.json")
    output_file.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Сохранено статей: {len(articles)}")
    print(f"Сущностей Wikidata: {len(wikidata)}")
    print(f"Файл: {output_file.name}")
    print(f"Статей Викисловаря: {len(wiktionary)}")
    print(f"Изображений Commons: {len(commons)}")


if __name__ == "__main__":
    main()