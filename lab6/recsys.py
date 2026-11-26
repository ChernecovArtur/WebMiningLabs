import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import argparse
import json
from pathlib import Path

import pandas as pd

from data import main as prepare_data
from evaluate import main as evaluate_models
from models import (
    ALSRecommender,
    ContentRecommender,
    SVDRecommender,
    load_movies,
    popular_recommendations,
)


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"


def ensure_data():
    train_path = DATA_DIR / "train.csv"
    movies_path = DATA_DIR / "ml-latest-small" / "movies.csv"

    if not train_path.exists() or not movies_path.exists():
        prepare_data()


def get_recommendations(model_name, user_id, k, train, movies):
    movies_by_id = load_movies(movies)

    if model_name == "popular":
        return popular_recommendations(
            train,
            movies_by_id,
            user_id,
            k,
        )

    if model_name == "content":
        model = ContentRecommender(movies)
    elif model_name == "svd":
        model = SVDRecommender(movies)
    elif model_name == "als":
        model = ALSRecommender(movies)
    else:
        raise ValueError(f"Неизвестная модель: {model_name}")

    model.fit(train)
    return model.recommend(user_id, k)


def main():
    parser = argparse.ArgumentParser(
        description="Рекомендательная система MovieLens"
    )
    parser.add_argument(
        "--dataset",
        choices=["movielens"],
        default="movielens",
    )
    parser.add_argument(
        "--model",
        choices=["popular", "content", "svd", "als", "all"],
        default="all",
    )
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--k", type=int, nargs="+", default=[10])
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument(
        "--output",
        default=str(BASE_DIR / "results" / "user"),
    )
    args = parser.parse_args()

    ensure_data()

    if args.evaluate:
        evaluate_models(args.k)

    if not args.evaluate or args.user_id is not None:
        train = pd.read_csv(DATA_DIR / "train.csv")
        movies = pd.read_csv(
            DATA_DIR / "ml-latest-small" / "movies.csv"
        )

        if args.user_id is None:
            user_id = int(train["userId"].iloc[0])
        else:
            user_id = args.user_id

        model_names = (
            ["popular", "content", "svd", "als"]
            if args.model == "all"
            else [args.model]
        )
        recommendations = {}

        for model_name in model_names:
            print(f"Строю рекомендации: {model_name}")
            recommendations[model_name] = get_recommendations(
                model_name,
                user_id,
                max(args.k),
                train,
                movies,
            )

        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "user_id": user_id,
            "k": max(args.k),
            "recommendations": recommendations,
        }
        (output_dir / "recs.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"\nПользователь: {user_id}")
        for model_name, movies_list in recommendations.items():
            print(f"\n{model_name}:")
            for movie in movies_list:
                print(f'- {movie["title"]}')

        print(f"\nСохранено в {output_dir / 'recs.json'}")


if __name__ == "__main__":
    main()