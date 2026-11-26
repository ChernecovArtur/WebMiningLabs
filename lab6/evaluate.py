import os

os.environ["OPENBLAS_NUM_THREADS"] = "1"

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from metrics import (
    average_precision_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from models import (
    ALSRecommender,
    ContentRecommender,
    SVDRecommender,
    load_movies,
    popular_recommendations,
)


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"


def history_group(history_count):
    if history_count == 0:
        return "cold"
    if history_count < 20:
        return "1-19"
    return "20+"


def genre_diversity(recommendations, k):
    genres = set()
    for movie in recommendations[:k]:
        genres.update(movie["genres"].split("|"))
    return len(genres)


def main(k_values=None):
    if k_values is None:
        k_values = [5, 10, 20]
    train = pd.read_csv(DATA_DIR / "train.csv")
    test = pd.read_csv(DATA_DIR / "test.csv")
    movies = pd.read_csv(
        DATA_DIR / "ml-latest-small" / "movies.csv"
    )
    movies_by_id = load_movies(movies)

    relevant_by_user = (
        test[test["rating"] >= 4]
        .groupby("userId")["movieId"]
        .apply(set)
        .to_dict()
    )
    users = sorted(relevant_by_user)

    history_counts = train.groupby("userId").size().to_dict()
    user_groups = {
        user_id: history_group(history_counts.get(user_id, 0))
        for user_id in users
    }

    content = ContentRecommender(movies)
    content.fit(train)

    svd = SVDRecommender(movies)
    svd.fit(train)

    als = ALSRecommender(movies)
    als.fit(train)

    models = {
        "popular": None,
        "content": content,
        "svd": svd,
        "als": als,
    }

    all_recommendations = {}
    metric_rows = []

    for model_name, model in models.items():
        print(f"Оцениваю {model_name}")
        model_recommendations = {}

        for user_id in users:
            if model_name == "popular":
                recommendations = popular_recommendations(
                    train,
                    movies_by_id,
                    user_id,
                    k=max(k_values),
                )
            else:
                recommendations = model.recommend(
                    user_id,
                    k=max(k_values),
                )

            model_recommendations[user_id] = recommendations

        all_recommendations[model_name] = model_recommendations

        for k in k_values:
            for group in ("all", "cold", "1-19", "20+"):
                group_users = [
                    user_id for user_id in users
                    if group == "all" or user_groups[user_id] == group
                ]
                if not group_users:
                    continue

                precision_values = []
                recall_values = []
                map_values = []
                ndcg_values = []
                diversity_values = []
                recommended_movies = set()

                for user_id in group_users:
                    recommendations = model_recommendations[user_id]
                    relevant = relevant_by_user[user_id]

                    precision_values.append(precision_at_k(
                        recommendations, relevant, k
                    ))
                    recall_values.append(recall_at_k(
                        recommendations, relevant, k
                    ))
                    map_values.append(average_precision_at_k(
                        recommendations, relevant, k
                    ))
                    ndcg_values.append(ndcg_at_k(
                        recommendations, relevant, k
                    ))
                    diversity_values.append(genre_diversity(
                        recommendations, k
                    ))
                    recommended_movies.update(
                        movie["movieId"]
                        for movie in recommendations[:k]
                    )

                metric_rows.append({
                    "model": model_name,
                    "k": k,
                    "history_group": group,
                    "users": len(group_users),
                    "precision": sum(precision_values) / len(group_users),
                    "recall": sum(recall_values) / len(group_users),
                    "MAP": sum(map_values) / len(group_users),
                    "NDCG": sum(ndcg_values) / len(group_users),
                    "coverage": (
                        len(recommended_movies) / movies["movieId"].nunique()
                    ),
                    "genre_diversity": (
                        sum(diversity_values) / len(group_users)
                    ),
                })

    RESULTS_DIR.mkdir(exist_ok=True)
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(RESULTS_DIR / "metrics.csv", index=False)

    with (RESULTS_DIR / "recs.json").open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            all_recommendations,
            file,
            ensure_ascii=False,
            indent=2,
        )

    summary = {
        "evaluated_users": len(users),
        "relevance_threshold": 4,
        "k_values": k_values,
        "history_groups": {
            group: sum(
                group_name == group
                for group_name in user_groups.values()
            )
            for group in ("cold", "1-19", "20+")
        },
    }
    (RESULTS_DIR / "evaluation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    overall = metrics[
        (metrics["k"] == 10)
        & (metrics["history_group"] == "all")
    ]

    figure, axes = plt.subplots(1, 3, figsize=(14, 4))
    for column, axis in zip(
        ["NDCG", "coverage", "genre_diversity"],
        axes,
    ):
        axis.bar(overall["model"], overall[column])
        axis.set_title(column)
        axis.tick_params(axis="x", rotation=30)

    figure.tight_layout()
    figure.savefig(RESULTS_DIR / "model_comparison.png", dpi=150)
    plt.close(figure)

    print("\nK = 10, все пользователи:")
    print(overall[[
        "model",
        "NDCG",
        "coverage",
        "genre_diversity",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()