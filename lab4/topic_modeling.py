import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from gensim import corpora, models
from gensim.models import CoherenceModel
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

from preprocess import load_documents


BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def prepare_data(documents):
    texts = [doc["tokens"] for doc in documents]
    clean_texts = [doc["clean_text"] for doc in documents]

    dictionary = corpora.Dictionary(texts)
    dictionary.filter_extremes(
        no_below=2,
        no_above=0.5,
    )

    corpus = [dictionary.doc2bow(text) for text in texts]

    vectorizer = TfidfVectorizer(
        max_features=1000,
        min_df=2,
        max_df=0.5,
    )
    tfidf = vectorizer.fit_transform(clean_texts)

    return {
        "texts": texts,
        "dictionary": dictionary,
        "corpus": corpus,
        "tfidf": tfidf,
        "feature_names": vectorizer.get_feature_names_out(),
    }


def get_coherence(topics, data):
    topic_words = [
        [word for word, _ in topic]
        for topic in topics
    ]

    model = CoherenceModel(
        topics=topic_words,
        texts=data["texts"],
        dictionary=data["dictionary"],
        coherence="c_v",
        processes=1,
    )
    return model.get_coherence()


def fit_lda(data, topic_count, top_words):
    model = models.LdaModel(
        corpus=data["corpus"],
        num_topics=topic_count,
        id2word=data["dictionary"],
        passes=15,
        random_state=42,
    )

    topics = [
        model.show_topic(topic_id, topn=top_words)
        for topic_id in range(topic_count)
    ]

    document_matrix = np.array([
        [
            probability
            for _, probability in model.get_document_topics(
                bow,
                minimum_probability=0,
            )
        ]
        for bow in data["corpus"]
    ])

    return {
        "topics": topics,
        "document_matrix": document_matrix,
        "coherence": get_coherence(topics, data),
    }


def fit_nmf(data, topic_count, top_words):
    model = NMF(
        n_components=topic_count,
        random_state=42,
        init="nndsvda",
        max_iter=500,
    )
    document_matrix = model.fit_transform(data["tfidf"])

    # Приводим доли тем в каждом документе к сумме 1
    row_sums = document_matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    document_matrix = document_matrix / row_sums

    topics = []

    for topic in model.components_:
        indices = topic.argsort()[-top_words:][::-1]
        topics.append([
            (
                data["feature_names"][index],
                float(topic[index]),
            )
            for index in indices
        ])

    return {
        "topics": topics,
        "document_matrix": document_matrix,
        "coherence": get_coherence(topics, data),
    }


def fit_model(method, data, topic_count, top_words):
    if method == "lda":
        return fit_lda(data, topic_count, top_words)
    return fit_nmf(data, topic_count, top_words)


def select_topics(method, data, topics_argument, top_words):
    if topics_argument != "auto":
        topic_count = int(topics_argument)
        result = fit_model(
            method,
            data,
            topic_count,
            top_words,
        )
        result["coherence_scores"] = {}
        return result

    scores = {}

    for topic_count in range(3, 21):
        result = fit_model(
            method,
            data,
            topic_count,
            top_words,
        )
        scores[topic_count] = result["coherence"]
        print(
            f"{method}, тем {topic_count}: "
            f"coherence {result['coherence']:.4f}"
        )

    best_count = max(scores, key=scores.get)
    result = fit_model(
        method,
        data,
        best_count,
        top_words,
    )
    result["coherence_scores"] = scores
    return result


def save_top_words(path, result):
    topics = result["topics"]
    columns = 5
    rows = int(np.ceil(len(topics) / columns))

    fig, axes = plt.subplots(
        rows,
        columns,
        figsize=(20, 4 * rows),
    )
    axes = np.array(axes).flatten()

    for index, topic in enumerate(topics):
        words = [word for word, _ in topic]
        weights = [weight for _, weight in topic]

        axes[index].barh(words, weights)
        axes[index].invert_yaxis()
        axes[index].set_title(f"Тема {index + 1}")

    for index in range(len(topics), len(axes)):
        axes[index].axis("off")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def save_document_plot(path, result):
    matrix = result["document_matrix"]

    fig, (left, right) = plt.subplots(
        1,
        2,
        figsize=(16, 8),
        gridspec_kw={"width_ratios": [2, 1]},
    )

    sns.heatmap(
        matrix[:50],
        cmap="YlGnBu",
        ax=left,
        yticklabels=False,
    )
    left.set_title("Первые 50 документов")
    left.set_xlabel("Тема")
    left.set_ylabel("Документ")

    right.bar(
        range(1, matrix.shape[1] + 1),
        matrix.mean(axis=0),
    )
    right.set_title("Средний вес темы")
    right.set_xlabel("Тема")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def save_result(dataset, method, output, result):
    prefix = OUTPUT_DIR / f"{output}_{method}"
    topic_count = len(result["topics"])

    payload = {
        "dataset": dataset,
        "method": method,
        "topic_count": topic_count,
        "coherence": result["coherence"],
        "coherence_scores": result["coherence_scores"],
        "topics": [
            {
                "id": index + 1,
                "words": [
                    {"word": word, "weight": float(weight)}
                    for word, weight in topic
                ],
            }
            for index, topic in enumerate(result["topics"])
        ],
    }

    with open(
        f"{prefix}_topics.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    matrix = result["document_matrix"]
    frame = pd.DataFrame({
        "title": [doc["title"] for doc in documents],
        "url": [doc["url"] for doc in documents],
        "dominant_topic": matrix.argmax(axis=1) + 1,
    })

    for index in range(topic_count):
        frame[f"topic_{index + 1}"] = matrix[:, index]

    frame.to_csv(
        f"{prefix}_documents.csv",
        index=False,
        encoding="utf-8-sig",
    )

    save_top_words(
        f"{prefix}_topwords.png",
        result,
    )
    save_document_plot(
        f"{prefix}_documents.png",
        result,
    )

    scores = result["coherence_scores"]

    if scores:
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(scores.keys(), scores.values(), marker="o")
        ax.axvline(topic_count, color="red", linestyle="--")
        ax.set_xlabel("Количество тем")
        ax.set_ylabel("Coherence c_v")
        ax.set_title(f"Подбор числа тем: {method.upper()}")
        fig.tight_layout()
        fig.savefig(f"{prefix}_coherence.png", dpi=150)
        plt.close(fig)

    print(
        f"{method.upper()}: тем {topic_count}, "
        f"coherence {result['coherence']:.4f}"
    )


parser = argparse.ArgumentParser()
parser.add_argument(
    "--dataset",
    required=True,
    choices=["news", "products", "mixed"],
)
parser.add_argument(
    "--method",
    required=True,
    choices=["lda", "nmf", "both"],
)
parser.add_argument("--topics", default="auto")
parser.add_argument("--compare", action="store_true")
parser.add_argument("--output", required=True)
parser.add_argument("--top-words", type=int, default=10)
args = parser.parse_args()

if args.dataset == "mixed":
    documents = (
        load_documents("news")
        + load_documents("products")
    )
else:
    documents = load_documents(args.dataset)

data = prepare_data(documents)
methods = ["lda", "nmf"] if args.method == "both" else [args.method]
comparison = {}

for method in methods:
    result = select_topics(
        method,
        data,
        args.topics,
        args.top_words,
    )
    comparison[method] = result["coherence"]
    save_result(
        args.dataset,
        method,
        args.output,
        result,
    )

if args.compare and len(comparison) == 2:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(comparison.keys(), comparison.values())
    ax.set_ylabel("Coherence c_v")
    ax.set_title("Сравнение LDA и NMF")
    fig.tight_layout()
    fig.savefig(
        OUTPUT_DIR / f"{args.output}_compare.png",
        dpi=150,
    )
    plt.close(fig)