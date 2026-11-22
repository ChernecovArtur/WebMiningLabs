from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats


BASE_DIR = Path(__file__).parent
report = []


def add_line(text=""):
    report.append(str(text))


products = pd.read_csv(BASE_DIR / "products.csv")
news = pd.read_json(BASE_DIR / "news.json")

news = news.drop(
    columns=["price", "rating"],
    errors="ignore",
)

add_line("Первичный анализ")
add_line()
add_line(f"Товаров до обработки: {len(products)}")
add_line(f"Новостей до обработки: {len(news)}")

add_line()
add_line("Пропуски в товарах:")
add_line(products.isna().sum().to_string())

add_line()
add_line("Пропуски в новостях:")
add_line(news.isna().sum().to_string())

# Удаляем точные дубликаты по URL
products = products.drop_duplicates(subset=["url"], keep="first")
news = news.drop_duplicates(subset=["url"], keep="first")

# Удаляем записи без обязательных полей
products = products.dropna(subset=["title", "url"])
news = news.dropna(subset=["title", "url"])

# Заполняем необязательные текстовые поля
for frame in (products, news):
    for field in ("summary", "description", "tags", "published"):
        if field in frame.columns:
            frame[field] = frame[field].fillna("")

# Цену заполняем медианой, категорию — модой
price_median = products["price"].median()
products["price"] = products["price"].fillna(price_median)

category_mode = products["category"].mode()

if not category_mode.empty:
    products["category"] = products["category"].fillna(
        category_mode[0]
    )

# Z-score
z_scores = np.abs(stats.zscore(products["price"]))
zscore_mask = z_scores < 3

# IQR
q1 = products["price"].quantile(0.25)
q3 = products["price"].quantile(0.75)
iqr = q3 - q1
lower_bound = q1 - 1.5 * iqr
upper_bound = q3 + 1.5 * iqr

iqr_mask = products["price"].between(
    lower_bound,
    upper_bound,
)

products_clean = products[iqr_mask].copy()
news_clean = news.copy()

add_line()
add_line("Резальтат обработки")
add_line(f"Медианная цена: {price_median:.2f}")
add_line(f"Q1: {q1:.2f}")
add_line(f"Q3: {q3:.2f}")
add_line(f"IQR: {iqr:.2f}")
add_line(f"Нижняя граница: {lower_bound:.2f}")
add_line(f"Верхняя граница: {upper_bound:.2f}")
add_line(
    f"Выбросов по Z-score: {(~zscore_mask).sum()}"
)
add_line(
    f"Выбросов по IQR: {(~iqr_mask).sum()}"
)
add_line(f"Товаров после фильтрации IQR: {len(products_clean)}")
add_line(f"Новостей после очистки: {len(news_clean)}")

products_clean.to_csv(
    BASE_DIR / "products_clean.csv",
    index=False,
    encoding="utf-8-sig",
)
news_clean.to_csv(
    BASE_DIR / "news_clean.csv",
    index=False,
    encoding="utf-8-sig",
)

# Boxplot до удаления выбросов
plt.figure(figsize=(9, 4))
sns.boxplot(x=products["price"])
plt.xlabel("Price, USD")
plt.title("Product prices")
plt.tight_layout()
plt.savefig(
    BASE_DIR / "price_boxplot.png",
    dpi=150,
)
plt.close()

(BASE_DIR / "analysis.txt").write_text(
    "\n".join(report),
    encoding="utf-8",
)

print("Анализ сохранён в analysis.txt")