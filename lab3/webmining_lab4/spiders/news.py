import scrapy


class NewsSpider(scrapy.Spider):
    name = "news"

    # Останавливаемся после 100 записей, прошедших все pipelines
    custom_settings = {
        "CLOSESPIDER_ITEMCOUNT": 100,
    }

    def __init__(self, keywords=None, max_pages=20, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.keywords = [
            word.strip().lower()
            for word in (keywords or "").split(",")
            if word.strip()
        ]
        self.max_pages = int(max_pages)

    async def start(self):
        for page in range(1, self.max_pages + 1):
            url = f"https://pstu.ru/media/news/?PAGEN_1={page}"

            yield scrapy.Request(
                url,
                callback=self.parse,
            )

    def parse(self, response):
        cards = response.css("div.card-media")

        if not cards:
            self.logger.warning(f"Новости не найдены: {response.url}")
            return

        for card in cards:
            title = card.css(".card-media__title::text").get()
            href = card.css("a.card-media__wrap::attr(href)").get()

            if not title or not href:
                self.logger.warning(
                    f"Пропущена карточка без заголовка или URL: {response.url}"
                )
                continue

            published = card.css(".card-media__date::text").get()
            tags = card.css(".card-media__tags .tag::text").getall()

            yield response.follow(
                href,
                callback=self.parse_article,
                cb_kwargs={
                    "title": title,
                    "published": published or "",
                    "tags": "; ".join(tags),
                },
            )

    def parse_article(self, response, title, published, tags):
        # Берём первый абзац как краткое описание
        summary = response.css("div.col-md-8 p").get()

        if not summary:
            self.logger.warning(f"Нет описания: {response.url}")
            summary = ""

        if self.keywords:
            text = f"{title} {summary}".lower()

            if not any(word in text for word in self.keywords):
                return

        yield {
            "title": title,
            "published": published,
            "url": response.url,
            "summary": summary,
            "tags": tags,
            "source": "pstu.ru",
        }