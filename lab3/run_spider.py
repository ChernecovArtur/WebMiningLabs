import argparse
import os
from pathlib import Path

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from webmining_lab4.spiders.ecommerce import EcommerceSpider
from webmining_lab4.spiders.news import NewsSpider


BASE_DIR = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(
        description="Сбор новостей и товаров"
    )
    parser.add_argument(
        "--spider",
        required=True,
        choices=["news", "ecommerce"],
        help="Какого паука запустить",
    )
    parser.add_argument(
        "--keywords",
        help="Ключевые слова для новостей",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=20,
        help="Максимум страниц новостей",
    )
    parser.add_argument(
        "--category",
        default="laptops",
        help="Категория товаров",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Имя файла",
    )

    args = parser.parse_args()

    output_path = Path(args.output)

    if not output_path.is_absolute():
        output_path = BASE_DIR / output_path

    file_format = output_path.suffix.lower().lstrip(".")

    if file_format not in ("json", "csv"):
        parser.error("Файл результата должен иметь расширение .json или .csv")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault(
        "SCRAPY_SETTINGS_MODULE",
        "webmining_lab4.settings",
    )
    settings = get_project_settings()

    feed = {
        "format": file_format,
        "mode": "overwrite",
        "encoding": "utf-8",
    }

    if file_format == "json":
        feed["indent"] = 2

    settings.set("FEEDS", {str(output_path): feed})

    process = CrawlerProcess(settings)

    if args.spider == "news":
        process.crawl(
            NewsSpider,
            keywords=args.keywords,
            max_pages=args.max_pages,
        )
    else:
        process.crawl(
            EcommerceSpider,
            category=args.category,
        )

    process.start()
    print(f"Файл сохранён: {output_path}")


if __name__ == "__main__":
    main()