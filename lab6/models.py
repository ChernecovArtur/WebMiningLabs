from pathlib import Path

import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from surprise import Dataset, Reader, SVD
import implicit
from scipy.sparse import csr_matrix
from implicit.als import AlternatingLeastSquares


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"


def load_movies(movies):
    return movies.set_index("movieId", drop=False)


def movie_result(movie_id, movies, score):
    movie = movies.loc[movie_id]
    return {
        "movieId": int(movie_id),
        "title": movie["title"],
        "genres": movie["genres"],
        "score": round(float(score), 6),
    }


def popular_recommendations(train, movies, user_id, k=10):
    seen = set(train.loc[train["userId"] == user_id, "movieId"])
    popularity = train.groupby("movieId").size().sort_values(
        ascending=False
    )

    recommendations = []
    for movie_id, count in popularity.items():
        if movie_id not in seen:
            recommendations.append(
                movie_result(movie_id, movies, count)
            )
        if len(recommendations) == k:
            break

    return recommendations


class ContentRecommender:
    def __init__(self, movies):
        self.movies = load_movies(movies)
        self.movie_ids = self.movies["movieId"].tolist()
        self.id_to_index = {
            movie_id: index
            for index, movie_id in enumerate(self.movie_ids)
        }

        documents = (
            self.movies["title"].fillna("")
            + " "
            + self.movies["genres"].fillna("").str.replace("|", " ")
        )
        self.vectorizer = TfidfVectorizer(
            max_features=10000,
            min_df=2,
            stop_words="english",
        )
        self.matrix = self.vectorizer.fit_transform(documents)
        self.popularity = None
        self.train = None

    def fit(self, train):
        self.train = train
        self.popularity = train.groupby("movieId").size().sort_values(
            ascending=False
        )

    def recommend(self, user_id, k=10):
        user_ratings = self.train[
            self.train["userId"] == user_id
        ]
        seen = set(user_ratings["movieId"])
        liked = user_ratings[
            (user_ratings["rating"] >= 4)
            & (user_ratings["movieId"].isin(self.id_to_index))
        ]

        # Если истории нет, показываем популярные фильмы.
        if liked.empty:
            return popular_recommendations(
                self.train,
                self.movies,
                user_id,
                k,
            )

        liked_indices = [
            self.id_to_index[movie_id]
            for movie_id in liked["movieId"]
        ]
        profile = np.asarray(
            self.matrix[liked_indices].mean(axis=0)
        )
        similarities = cosine_similarity(
            profile,
            self.matrix,
        ).ravel()

        order = similarities.argsort()[::-1]
        recommendations = []

        for index in order:
            movie_id = self.movie_ids[index]
            if movie_id in seen:
                continue

            recommendations.append(
                movie_result(
                    movie_id,
                    self.movies,
                    similarities[index],
                )
            )
            if len(recommendations) == k:
                break

        return recommendations

class SVDRecommender:
    def __init__(self, movies):
        self.movies = load_movies(movies)
        self.movie_ids = self.movies["movieId"].tolist()
        self.model = None
        self.train = None
        self.users = set()

    def fit(self, train):
        self.train = train
        self.users = set(train["userId"])

        reader = Reader(rating_scale=(0.5, 5))
        dataset = Dataset.load_from_df(
            train[["userId", "movieId", "rating"]],
            reader,
        )
        trainset = dataset.build_full_trainset()

        self.model = SVD(
            n_factors=50,
            n_epochs=20,
            random_state=42,
        )
        self.model.fit(trainset)

    def recommend(self, user_id, k=10):
        if user_id not in self.users:
            return popular_recommendations(
                self.train,
                self.movies,
                user_id,
                k,
            )

        seen = set(
            self.train.loc[
                self.train["userId"] == user_id,
                "movieId",
            ]
        )
        predictions = []

        for movie_id in self.movie_ids:
            if movie_id in seen:
                continue

            prediction = self.model.predict(user_id, movie_id)
            predictions.append((movie_id, prediction.est))

        predictions.sort(key=lambda item: item[1], reverse=True)

        return [
            movie_result(movie_id, self.movies, score)
            for movie_id, score in predictions[:k]
        ]

class ALSRecommender:
    def __init__(self, movies):
        self.movies = load_movies(movies)
        self.movie_ids = self.movies["movieId"].tolist()
        self.movie_to_index = {
            movie_id: index
            for index, movie_id in enumerate(self.movie_ids)
        }
        self.model = None
        self.train = None
        self.user_ids = []
        self.user_to_index = {}
        self.user_item = None

    def fit(self, train):
        self.train = train
        self.user_ids = sorted(train["userId"].unique())
        self.user_to_index = {
            user_id: index
            for index, user_id in enumerate(self.user_ids)
        }

        rows = train["userId"].map(self.user_to_index)
        columns = train["movieId"].map(self.movie_to_index)

        # Убираем возможные оценки фильмов вне каталога.
        valid = rows.notna() & columns.notna()
        rows = rows[valid].astype(int)
        columns = columns[valid].astype(int)
        ratings = train.loc[valid, "rating"].astype(float)

        self.user_item = csr_matrix(
            (
                ratings,
                (rows, columns),
            ),
            shape=(len(self.user_ids), len(self.movie_ids)),
        )

        self.model = AlternatingLeastSquares(
            factors=64,
            iterations=15,
            random_state=42,
        )
        self.model.fit(self.user_item)

    def recommend(self, user_id, k=10):
        if user_id not in self.user_to_index:
            return popular_recommendations(
                self.train,
                self.movies,
                user_id,
                k,
            )

        user_index = self.user_to_index[user_id]
        indices, scores = self.model.recommend(
            user_index,
            self.user_item[user_index],
            N=k,
            filter_already_liked_items=True,
        )

        return [
            movie_result(
                self.movie_ids[index],
                self.movies,
                score,
            )
            for index, score in zip(indices, scores)
        ]
    
def main():
    train = pd.read_csv(DATA_DIR / "train.csv")
    movies = pd.read_csv(
        DATA_DIR / "ml-latest-small" / "movies.csv"
    )
    movies_by_id = load_movies(movies)
    user_id = int(train["userId"].iloc[0])

    popular = popular_recommendations(
        train,
        movies_by_id,
        user_id,
        k=5,
    )

    content = ContentRecommender(movies)
    content.fit(train)
    content_recommendations = content.recommend(user_id, k=5)

    svd = SVDRecommender(movies)
    svd.fit(train)
    svd_recommendations = svd.recommend(user_id, k=5)

    als = ALSRecommender(movies)
    als.fit(train)
    als_recommendations = als.recommend(user_id, k=5)

    print(f"Пользователь: {user_id}")

    print("\nПопулярное:")
    for movie in popular:
        print(f'- {movie["title"]}')

    print("\nTF-IDF:")
    for movie in content_recommendations:
        print(f'- {movie["title"]} ({movie["score"]:.3f})')

    print("\nSVD:")
    for movie in svd_recommendations:
        print(f'- {movie["title"]} ({movie["score"]:.3f})')

    print("\nALS:")
    for movie in als_recommendations:
        print(f'- {movie["title"]} ({movie["score"]:.3f})')


if __name__ == "__main__":
    main()