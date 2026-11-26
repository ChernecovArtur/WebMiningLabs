import json
import zipfile
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import requests


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
ARCHIVE_PATH = DATA_DIR / "ml-latest-small.zip"
DATASET_URL = (
    "https://files.grouplens.org/datasets/movielens/"
    "ml-latest-small.zip"
)


def download_dataset():
    ratings_path = DATA_DIR / "ml-latest-small" / "ratings.csv"
    if ratings_path.exists():
        return

    DATA_DIR.mkdir(exist_ok=True)

    if not ARCHIVE_PATH.exists():
        print("Скачиваю MovieLens")
        response = requests.get(
            DATASET_URL,
            stream=True,
            timeout=(10, 60),
        )
        response.raise_for_status()

        with ARCHIVE_PATH.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                file.write(chunk)

    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        for name in ("ratings.csv", "movies.csv"):
            source = f"ml-latest-small/{name}"
            target = DATA_DIR / source
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(source))


def load_data():
    dataset_dir = DATA_DIR / "ml-latest-small"
    ratings = pd.read_csv(dataset_dir / "ratings.csv")
    movies = pd.read_csv(dataset_dir / "movies.csv")
    return ratings, movies


def temporal_split(ratings):
    ordered = ratings.sort_values("timestamp").reset_index(drop=True)
    split_index = int(len(ordered) * 0.8)

    train = ordered.iloc[:split_index].copy()
    test = ordered.iloc[split_index:].copy()
    return train, test


def analyze(ratings, movies, train, test):
    user_counts = ratings.groupby("userId").size()
    rating_counts = ratings["rating"].value_counts().sort_index()

    sparsity = 1 - len(ratings) / (
        ratings["userId"].nunique() * movies["movieId"].nunique()
    )

    summary = {
        "ratings": int(len(ratings)),
        "users": int(ratings["userId"].nunique()),
        "movies_in_catalog": int(movies["movieId"].nunique()),
        "rated_movies": int(ratings["movieId"].nunique()),
        "sparsity": round(float(sparsity), 6),
        "mean_ratings_per_user": round(float(user_counts.mean()), 3),
        "median_ratings_per_user": round(float(user_counts.median()), 3),
        "max_ratings_per_user": int(user_counts.max()),
        "train_ratings": int(len(train)),
        "test_ratings": int(len(test)),
        "cutoff_timestamp": int(train["timestamp"].max()),
        "rating_distribution": {
            str(rating): int(count)
            for rating, count in rating_counts.items()
        },
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "eda.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    rating_counts.plot(kind="bar", color="#3264a8")
    plt.title("Распределение оценок")
    plt.xlabel("Оценка")
    plt.ylabel("Количество")
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "rating_distribution.png", dpi=150)
    plt.close()

    plt.hist(user_counts, bins=30, color="#3264a8")
    plt.title("Активность пользователей")
    plt.xlabel("Количество оценок у пользователя")
    plt.ylabel("Количество пользователей")
    plt.yscale("log")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "user_activity.png", dpi=150)
    plt.close()

    return summary


def main():
    download_dataset()
    ratings, movies = load_data()
    train, test = temporal_split(ratings)

    train.to_csv(DATA_DIR / "train.csv", index=False)
    test.to_csv(DATA_DIR / "test.csv", index=False)

    summary = analyze(ratings, movies, train, test)

    print(
        f'Оценок: {summary["ratings"]}, '
        f'пользователей: {summary["users"]}, '
        f'фильмов: {summary["movies_in_catalog"]}'
    )
    print(f'Разреженность: {summary["sparsity"]:.2%}')
    print(
        f'Обучение: {summary["train_ratings"]}, '
        f'тест: {summary["test_ratings"]}'
    )


if __name__ == "__main__":
    main()