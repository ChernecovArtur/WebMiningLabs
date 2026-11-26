import json
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def hits(recommendations, relevant, k=10):
    return sum(
        movie["movieId"] in relevant
        for movie in recommendations[:k]
    )


def main():
    train = pd.read_csv(DATA_DIR / "train.csv")
    test = pd.read_csv(DATA_DIR / "test.csv")
    movies = pd.read_csv(
        DATA_DIR / "ml-latest-small" / "movies.csv"
    ).set_index("movieId")
    recommendations = read_json(RESULTS_DIR / "recs.json")

    relevant_test = (
        test[test["rating"] >= 4]
        .groupby("userId")["movieId"]
        .apply(set)
        .to_dict()
    )
    users = sorted(relevant_test)
    history_counts = train.groupby("userId").size().to_dict()

    # Первый пример: ALS заметно обошёл популярное
    first_user = max(
        users,
        key=lambda user: (
            hits(recommendations["als"][str(user)], relevant_test[user])
            - hits(
                recommendations["popular"][str(user)],
                relevant_test[user],
            ),
            hits(recommendations["als"][str(user)], relevant_test[user]),
        ),
    )

    # Второй пример: ищем относительно удачную выдачу TF-IDF
    remaining_users = [user for user in users if user != first_user]
    second_user = max(
        remaining_users,
        key=lambda user: (
            hits(
                recommendations["content"][str(user)],
                relevant_test[user],
            ),
            hits(
                recommendations["svd"][str(user)],
                relevant_test[user],
            ),
        ),
    )

    review = []

    for user_id in (first_user, second_user):
        user_entry = {
            "user_id": int(user_id),
            "history_count": int(history_counts.get(user_id, 0)),
            "relevant_in_test": [],
            "models": {},
        }

        user_test = test[
            (test["userId"] == user_id)
            & (test["rating"] >= 4)
        ]
        for row in user_test.itertuples():
            user_entry["relevant_in_test"].append({
                "movieId": int(row.movieId),
                "title": movies.loc[row.movieId, "title"],
                "rating": float(row.rating),
            })

        print(
            f"\nПользователь {user_id}, "
            f"история: {user_entry['history_count']}"
        )

        for model_name, model_recommendations in recommendations.items():
            user_recommendations = model_recommendations[str(user_id)][:10]
            annotated = []

            for movie in user_recommendations:
                is_hit = movie["movieId"] in relevant_test[user_id]
                annotated.append({
                    **movie,
                    "hit": is_hit,
                })

            user_entry["models"][model_name] = annotated
            print(
                f"{model_name}: попаданий "
                f"{hits(user_recommendations, relevant_test[user_id])}/10"
            )

        review.append(user_entry)

    (RESULTS_DIR / "manual_review.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    metrics = pd.read_csv(RESULTS_DIR / "metrics.csv")
    groups = metrics[
        (metrics["k"] == 10)
        & (metrics["history_group"] != "all")
    ]
    print("\nNDCG@10 по длине истории:")
    print(groups[[
        "model",
        "history_group",
        "users",
        "NDCG",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()