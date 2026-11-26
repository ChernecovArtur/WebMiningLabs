import numpy as np


def precision_at_k(recommendations, relevant, k):
    recommended_ids = [
        item["movieId"] for item in recommendations[:k]
    ]
    hits = sum(
        movie_id in relevant for movie_id in recommended_ids
    )
    return hits / k


def recall_at_k(recommendations, relevant, k):
    recommended_ids = [
        item["movieId"] for item in recommendations[:k]
    ]
    hits = sum(
        movie_id in relevant for movie_id in recommended_ids
    )
    return hits / len(relevant) if relevant else 0.0


def average_precision_at_k(recommendations, relevant, k):
    score = 0.0
    hits = 0

    for rank, item in enumerate(recommendations[:k], start=1):
        if item["movieId"] in relevant:
            hits += 1
            score += hits / rank

    normalizer = min(len(relevant), k)
    return score / normalizer if normalizer else 0.0


def ndcg_at_k(recommendations, relevant, k):
    dcg = 0.0

    for rank, item in enumerate(recommendations[:k], start=1):
        if item["movieId"] in relevant:
            dcg += 1 / np.log2(rank + 1)

    ideal_hits = min(len(relevant), k)
    ideal_dcg = sum(
        1 / np.log2(rank + 1)
        for rank in range(1, ideal_hits + 1)
    )
    return dcg / ideal_dcg if ideal_dcg else 0.0