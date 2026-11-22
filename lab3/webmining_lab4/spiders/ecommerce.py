import scrapy
from scrapy import Selector
from scrapy_playwright.page import PageMethod


async def collect_products(page):
    products = []

    for page_number in range(1, 21):
        html = await page.content()
        selector = Selector(text=html)
        cards = selector.css("div.thumbnail")

        for card in cards:
            title = card.css("a.title::attr(title)").get()
            title = title or card.css("a.title::text").get()
            href = card.css("a.title::attr(href)").get()

            if not title or not href:
                continue

            products.append({
                "title": title,
                "description": card.css(
                    ".description::text"
                ).get(),
                "price": card.css(".price::text").get(),
                "rating": card.css(
                    ".ratings p[data-rating]::attr(data-rating)"
                ).get(),
                "reviews": card.css(
                    ".review-count span::text"
                ).get(),
                "url": href,
            })

        if page_number == 20:
            break

        next_page = page_number + 1

        await page.click(
            f'button.page[data-id="{next_page}"]'
        )
        await page.wait_for_selector(
            f'button.page[data-id="{next_page}"].active'
        )
        await page.wait_for_timeout(300)

    return products


class EcommerceSpider(scrapy.Spider):
    name = "ecommerce"

    custom_settings = {
        "CLOSESPIDER_ITEMCOUNT": 100,
    }

    def __init__(self, category="laptops", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category = category

    async def start(self):
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
                    PageMethod(collect_products),
                ],
            },
        )

    def parse(self, response):
        methods = response.meta["playwright_page_methods"]
        products = methods[-1].result or []

        for product in products:
            product["url"] = response.urljoin(product["url"])
            product["category"] = self.category
            product["source"] = "webscraper.io"
            yield product