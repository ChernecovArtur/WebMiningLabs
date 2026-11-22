import re
from functools import lru_cache
from pathlib import Path

import ftfy
import pandas as pd
import pymorphy3
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

morph = pymorphy3.MorphAnalyzer()

RUSSIAN_STOPWORDS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со",
    "как", "а", "то", "все", "всё", "она", "так", "его", "но",
    "да", "ты", "к", "у", "же", "вы", "за", "бы", "по", "ее",
    "её", "мне", "было", "вот", "от", "меня", "еще", "ещё",
    "о", "об", "из", "у", "им", "для", "это", "этот", "эта",
    "эти", "который", "которая", "которые", "быть", "мочь",
    "очень", "после", "перед", "более", "менее", "также",
    "уже", "там", "здесь", "тут", "или", "ли", "при",
    "год", "день", "время", "работа", "новость", "сайт",
    "пнипу", "пермь", "политех", "университет", "товар",
    "описание", "цена", "страница", "ссылка",
}

STOPWORDS = RUSSIAN_STOPWORDS | set(ENGLISH_STOP_WORDS)


@lru_cache(maxsize=100000)
def lemmatize(word):
    return morph.parse(word)[0].normal_form


def tokenize(text):
    text = ftfy.fix_text(str(text)).lower()
    text = text.replace("ё", "е")

    words = re.findall(r"[a-zа-я]+", text)
    tokens = []

    for word in words:
        if len(word) < 3 or word in STOPWORDS:
            continue

        lemma = lemmatize(word)

        if len(lemma) >= 3 and lemma not in STOPWORDS:
            tokens.append(lemma)

    return tokens


def load_documents(dataset):
    if dataset == "news":
        frame = pd.read_json(DATA_DIR / "news.json")
        frame["document_text"] = (
            frame["title"].fillna("")
            + " "
            + frame["summary"].fillna("")
        )
    elif dataset == "products":
        frame = pd.read_json(DATA_DIR / "products.json")
        # Чтоб не падало с ошибкой
        if "review_text" not in frame.columns:
            frame["review_text"] = ""
        frame["document_text"] = (
            frame["title"].fillna("")
            + " "
            + frame["description"].fillna("")
            + " "
            + frame["review_text"].fillna("")
        )
    else:
        raise ValueError("Датасет должен быть news или products")

    documents = []

    for _, row in frame.iterrows():
        tokens = tokenize(row["document_text"])

        # Совсем короткие тексты только добавляют шум
        if len(tokens) < 5:
            continue

        documents.append({
            "title": row["title"],
            "url": row["url"],
            "text": row["document_text"],
            "tokens": tokens,
            "clean_text": " ".join(tokens),
        })

    return documents


if __name__ == "__main__":
    for name in ("news", "products"):
        documents = load_documents(name)
        words = sum(len(doc["tokens"]) for doc in documents)

        print(f"{name}: документов {len(documents)}, слов {words}")