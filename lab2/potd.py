from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup


API_URL = "https://commons.wikimedia.org/w/api.php"
HEADERS = {
    "User-Agent": "EducationalLab/1.0"
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


def get_caption(date_iso):
    for language in ("ru", "en"):
        caption_title = f"Template:Potd/{date_iso} ({language})"

        data = get_json({
            "action": "parse",
            "format": "json",
            "formatversion": "2",
            "prop": "text",
            "page": caption_title,
        })

        parse_result = data.get("parse")

        if not parse_result:
            continue

        caption_html = parse_result.get("text", "")
        soup = BeautifulSoup(caption_html, "html.parser")
        description_tag = soup.find("div", class_="description")

        if description_tag:
            description = description_tag.get_text(" ", strip=True)
        else:
            description = soup.get_text(" ", strip=True)

        if description:
            return description

    return ""


def get_image_title(date_iso):
    image_title = f"Template:Potd/{date_iso}"

    data = get_json({
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "images",
        "titles": image_title,
    })

    pages = data.get("query", {}).get("pages", [])

    if not pages:
        return None

    images = pages[0].get("images", [])

    if not images:
        return None

    return images[0].get("title")


date_iso = date.today().isoformat()
filename = get_image_title(date_iso)

if not filename:
    raise SystemExit(f"Картинка дня за {date_iso} не найдена")

image_info = get_json({
    "action": "query",
    "format": "json",
    "formatversion": "2",
    "prop": "imageinfo",
    "iiprop": "url|extmetadata",
    "titles": filename,
})

pages = image_info.get("query", {}).get("pages", [])
imageinfo = pages[0].get("imageinfo", []) if pages else []

if not imageinfo:
    raise SystemExit("Не удалось получить информацию об изображении")

info = imageinfo[0]
description = get_caption(date_iso)

if not description:
    description = info.get("extmetadata", {}).get(
        "ImageDescription", {}
    ).get("value", "")

    description = BeautifulSoup(
        description,
        "html.parser",
    ).get_text(" ", strip=True)

if not description:
    description = "Описание отсутствует"

image_response = requests.get(
    info["url"],
    headers=HEADERS,
    timeout=60,
)
image_response.raise_for_status()

folder = Path(__file__).parent
local_name = filename.removeprefix("File:").replace(" ", "_")
image_path = folder / local_name
description_path = image_path.with_suffix(".txt")

image_path.write_bytes(image_response.content)
description_path.write_text(description, encoding="utf-8")

print(f"Дата: {date_iso}")
print(f"Изображение: {image_path.name}")
print(f"Описание: {description_path.name}")