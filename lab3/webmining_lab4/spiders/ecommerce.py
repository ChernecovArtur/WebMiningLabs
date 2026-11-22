import scrapy
from scrapy import Selector
from scrapy_playwright.page import PageMethod


class EcommerceSpider(scrapy.Spider):
    name = "ecommerce"

    custom_settings = {
        "CLOSESPIDER_ITEMCOUNT": 100,
    }

    def __init__(self, category="laptops", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category = category

    def start_requests(self):
        url = (
            "https://webscraper.io/test-sites/"
            f"e-commerce/ajax/computers/{self.category}"
        )

        yield scrapy.Request(
            url,
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod(
                        "wait_for_selector",
                        ".thumbnail",
                    ),
                    PageMethod(
                        "evaluate",
                        "window.scrollTo(0, document.body.scrollHeight)",
                    ),
                    PageMethod("wait_for_timeout", 1000),
                ],
            },
        )

    async def parse(self, response):
        page = response.meta["playwright_page"]

        try:
    
            for page_number in range(1, 21):
                html = await page.content()
                selector = Selector(text=html)
                cards = selector.css("div.thumbnail")

                if not cards:
                    self.logger.warning(
                        f"Товары не найдены на странице {page_number}"
                    )
                    continue

                for card in cards:
                    title = card.css("a.title::attr(title)").get()
                    title = title or card.css("a.title::text").get()
                    href = card.css("a.title::attr(href)").get()

                    if not title or not href:
                        self.logger.warning(
                            "Пропущен товар без названия или ссылки"
                        )
                        continue

                    yield {
                        "title": title,
                        "description": card.css(
                            ".description::text"
                        ).get(),
                        "price": card.css(".price::text").get(),
                        "rating": card.css(
                            ".ratings p[data-rating]::attr(data-rating)"
                        ).get(),
                        "reviews": card.css(
                            ".ratings .pull-right::text"
                        ).get(),
                        "url": response.urljoin(href),
                        "category": self.category,
                        "source": "webscraper.io",
                    }

                if page_number == 20:
                    break

                next_page = page_number + 1

                # Переключаем AJAX-страницу без нового HTTP-запроса Scrapy
                await page.click(
                    f'button.page[data-id="{next_page}"]'
                )
                await page.wait_for_selector(
                    f'button.page[data-id="{next_page}"].active'
                )
                await page.wait_for_timeout(300)

        finally:
            await page.close()