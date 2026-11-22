# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import re

import ftfy
from bs4 import BeautifulSoup
from itemadapter import ItemAdapter
from rapidfuzz import fuzz
from scrapy.exceptions import DropItem


class CleaningPipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Очистка текста
        for field, value in list(adapter.items()):
            if not isinstance(value, str):
                continue

            value = BeautifulSoup(value, "lxml").get_text(
                " ",
                strip=True,
            )
            value = ftfy.fix_text(value)
            value = re.sub(r"\s+", " ", value).strip()
            adapter[field] = value

        # Отдельное поле для сравнения
        title = adapter.get("title", "")
        adapter["normalized_title"] = title.lower()

        for field in ("price", "rating"):
            value = adapter.get(field)

            if value in (None, ""):
                adapter[field] = None
                continue

            number = re.sub(r"[^\d,.]", "", str(value))
            number = number.replace(",", ".")

            try:
                adapter[field] = float(number)
            except ValueError:
                adapter[field] = None

        reviews = adapter.get("reviews")

        if reviews not in (None, ""):
            number = re.sub(r"[^\d]", "", str(reviews))
            adapter["reviews"] = int(number) if number else None

        return item


class ValidationPipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Для однозначного использования
        for field in ("title", "url"):
            if not adapter.get(field):
                spider.crawler.stats.inc_value(
                    f"validation/missing_{field}"
                )
                raise DropItem(f"Нет обязательного поля {field}")

        for field in ("summary", "description", "category"):
            if field in adapter and adapter[field] is None:
                adapter[field] = ""

        return item


class DuplicationPipeline:
    def __init__(self):
        self.seen_urls = set()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        url = adapter["url"]

        if url in self.seen_urls:
            spider.crawler.stats.inc_value("duplicates/url")
            raise DropItem(f"Повторный URL: {url}")

        self.seen_urls.add(url)
        return item


class FuzzyDuplicationPipeline:
    def __init__(self):
        self.seen_titles = []
        self.threshold = 98

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        title = adapter["normalized_title"]

        if not title:
            return item

        for seen_title in self.seen_titles:
            similarity = fuzz.ratio(title, seen_title)

            if similarity >= self.threshold:
                spider.crawler.stats.inc_value(
                    "duplicates/fuzzy_title"
                )
                raise DropItem(
                    f"Похожий заголовок ({similarity:.0f}%): {title}"
                )

        self.seen_titles.append(title)
        return item