import argparse
import json
from io import BytesIO
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tabulate import tabulate
from warcio.archiveiterator import ArchiveIterator
from collections import Counter
from urllib.parse import urlsplit

INDEX_URL = "https://index.commoncrawl.org/CC-MAIN-2025-30-index"
CACHE_FILE = Path(__file__).with_name("cdx_cache.json")
#TEXT_SCAN_LIMIT = 20


def search_cdx(keywords, domain, limit):
    params = {
        "url": domain or keywords[0],
        "matchType": "domain",
        "output": "json",
        "filter": ["status:200", "mime:text/html"],
        "fl": "url,timestamp,filename,offset,length",
        "collapse": "urlkey",
        "limit": limit * 10,
    }

    try:
        response = requests.get(INDEX_URL, params=params, timeout=15)
        response.raise_for_status()

        records = [
            json.loads(line)
            for line in response.text.splitlines()
            if line.strip()
        ]

        if records:
            CACHE_FILE.write_text(
                json.dumps(records, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

    except (requests.RequestException, json.JSONDecodeError):
        print("CDX недоступен, использую кэш")

        if not CACHE_FILE.exists():
            print("Файл кэша не найден")
            return []
        records = json.loads(CACHE_FILE.read_text(encoding="utf-8"))

    words = [word.casefold() for word in keywords]
    domain_filter = (domain or "").casefold().strip("/")
    results = []

    for record in records:
        url = record["url"].casefold()

        if domain_filter and domain_filter not in url:
            continue

        if all(word in url for word in words):
            results.append(record)

        if len(results) >= limit:
            break

    return results


def load_page(record):
    offset = int(record["offset"])
    end = offset + int(record["length"]) - 1
    warc_url = "https://data.commoncrawl.org/" + record["filename"]

    response = requests.get(
        warc_url,
        headers={"Range": f"bytes={offset}-{end}"},
        timeout=20
    )
    response.raise_for_status()

    for warc_record in ArchiveIterator(BytesIO(response.content)):
        if warc_record.rec_type != "response":
            continue

        html = warc_record.content_stream().read()
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else "—"

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        return title, soup.get_text(" ", strip=True)

    return "—", ""


def find_in_text(records, words, limit):
    results = []
    words = [word.casefold() for word in words]

    for record in records:
        try:
            title, text = load_page(record)
        except Exception:
            continue

        if all(word in text.casefold() for word in words):
            record["_title"] = title
            record["_text"] = text
            results.append(record)

        if len(results) >= limit:
            break

    return results

def print_stats(records):
    domains = Counter(
        urlsplit(record["url"]).hostname
        for record in records
    )

    months = Counter(
        record["timestamp"][:6]
        for record in records
    )

    domain_rows = [
        [domain, count]
        for domain, count in domains.most_common()
    ]

    month_rows = [
        [f"{month[:4]}-{month[4:]}", count]
        for month, count in sorted(months.items())
    ]

    print("\nРаспределение по доменам:")
    print(tabulate(
        domain_rows,
        headers=["Домен", "Страниц"],
        tablefmt="grid"
    ))

    print("\nРаспределение по месяцам архивации:")
    print(tabulate(
        month_rows,
        headers=["Месяц", "Страниц"],
        tablefmt="grid"
    ))

def main():
    parser = argparse.ArgumentParser(description="Поиск в Common Crawl")
    parser.add_argument("keywords", nargs="+", help="Ключевые слова в URL")
    parser.add_argument("--domain", help="Домен")
    parser.add_argument("--limit", type=int, default=10, help="Число результатов")
    parser.add_argument("--scan-limit",type=int, default=20, help="Сколько страниц проверять при поиске по тексту")
    parser.add_argument("--show-text", action="store_true", help="Показать текст")
    parser.add_argument("--text", nargs="+", default=[], help="Слова в тексте")
    parser.add_argument("--stats", action="store_true", help="Показать статистику")

    args = parser.parse_args()
    show_text = args.show_text or bool(args.text)

    if args.text:
        records = search_cdx(args.keywords, args.domain, args.scan_limit)
        results = find_in_text(records, args.text, args.limit)
    else:
        results = search_cdx(args.keywords, args.domain, args.limit)

    if not results:
        print("Ничего не найдено")
        return

    headers = ["URL", "Дата архивации", "Заголовок"]
    widths = [50, 14, 35]

    if show_text:
        headers.append("Фрагмент текста")
        widths.append(50)

    rows = []

    for result in results:
        timestamp = result["timestamp"]
        date = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
        row = [result["url"], date]

        if show_text:
            try:
                if "_text" in result:
                    title = result["_title"]
                    text = result["_text"]
                else:
                    title, text = load_page(result)

                fragment = text[:200]
            except Exception:
                title, fragment = "—", "WARC сейчас недоступен"

            row.extend([title, fragment])
        else:
            row.append("—")

        rows.append(row)

    print(tabulate(
        rows,
        headers=headers,
        tablefmt="grid",
        maxcolwidths=widths
    ))

    if args.stats:
        print_stats(results)


if __name__ == "__main__":
    main()