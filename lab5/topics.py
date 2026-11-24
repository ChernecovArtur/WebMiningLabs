import argparse
import csv
import json
import re
from functools import lru_cache
from pathlib import Path

import pymorphy3
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import (
    ENGLISH_STOP_WORDS,
    TfidfVectorizer,
)
from sklearn.metrics import silhouette_score


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

RUSSIAN_STOP_WORDS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со",
    "как", "а", "то", "все", "весь", "она", "так", "его", "но",
    "да", "ты", "к", "у", "же", "вы", "за", "бы", "по", "только",
    "ее", "мне", "было", "вот", "от", "меня", "еще", "нет", "о",
    "из", "ему", "теперь", "когда", "даже", "ну", "ли", "если",
    "уже", "или", "ни", "быть", "был", "него", "до", "вас",
    "нибудь", "опять", "уж", "вам", "ведь", "там", "потом",
    "себя", "ничего", "ей", "может", "они", "тут", "где", "есть",
    "надо", "ней", "для", "мы", "тебя", "их", "чем", "была",
    "сам", "чтоб", "без", "будто", "чего", "раз", "тоже", "себе",
    "под", "будет", "ж", "тогда", "кто", "этот", "того", "потому",
    "этого", "какой", "совсем", "ним", "здесь", "про", "над",
    "один", "почти", "мой", "тем", "чтобы", "нее", "сейчас",
    "были", "куда", "зачем", "всех", "можно", "при", "другой",
    "это", "который", "очень", "просто", "более", "менее",
}
STOP_WORDS = RUSSIAN_STOP_WORDS | set(ENGLISH_STOP_WORDS)

morph = pymorphy3.MorphAnalyzer()


@lru_cache(maxsize=100000)
def lemmatize(word):
    return morph.parse(word)[0].normal_form


def preprocess(text):
    text = text.lower().replace("ё", "е")
    words = re.findall(r"[a-zа-я]+", text)
    return [
        lemmatize(word)
        for word in words
        if len(word) > 2 and word not in STOP_WORDS
    ]


def load_document(video):
    video_dir = DATA_DIR / video["id"]
    speech_path = video_dir / "speech.json"
    objects_path = video_dir / "objects.json"

    speech = json.loads(speech_path.read_text(encoding="utf-8"))
    objects = json.loads(objects_path.read_text(encoding="utf-8"))

    # Ограничиваем описание, чтобы длинный служебный текст не доминировал.
    text = " ".join([
        video["title"],
        video.get("description", "")[:1000],
        speech["transcript"],
        " ".join(objects["class_counts"].keys()),
    ])
    return " ".join(preprocess(text))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clusters", type=int, default=2)
    args = parser.parse_args()

    collection_path = DATA_DIR / "collection.json"
    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    videos = collection["videos"]

    if len(videos) < args.clusters:
        print("Число кластеров больше числа роликов")
        return

    documents = [load_document(video) for video in videos]

    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(documents)

    model = KMeans(
        n_clusters=args.clusters,
        random_state=42,
        n_init=10,
    )
    labels = model.fit_predict(matrix)
    silhouette = silhouette_score(matrix, labels)

    feature_names = vectorizer.get_feature_names_out()
    clusters = []

    for cluster_id in range(args.clusters):
        centroid = model.cluster_centers_[cluster_id]
        top_indices = centroid.argsort()[::-1][:12]
        top_terms = [feature_names[index] for index in top_indices]

        video_ids = [
            video["id"]
            for video, label in zip(videos, labels)
            if label == cluster_id
        ]
        clusters.append({
            "cluster": cluster_id,
            "video_ids": video_ids,
            "top_terms": top_terms,
        })

    video_results = []
    for video, label, document in zip(videos, labels, documents):
        video_results.append({
            "id": video["id"],
            "title": video["title"],
            "cluster": int(label),
            "token_count": len(document.split()),
        })
        print(f"Кластер {label}: {video['title']}")

    result = {
        "method": "TF-IDF + KMeans",
        "cluster_count": args.clusters,
        "silhouette": round(float(silhouette), 6),
        "videos": video_results,
        "clusters": clusters,
    }
    (DATA_DIR / "topics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (DATA_DIR / "topics.csv").open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["id", "title", "cluster", "token_count"],
        )
        writer.writeheader()
        writer.writerows(video_results)

    print(f"\nSilhouette: {silhouette:.4f}")
    for cluster in clusters:
        terms = ", ".join(cluster["top_terms"])
        print(f'Кластер {cluster["cluster"]}: {terms}')


if __name__ == "__main__":
    main()