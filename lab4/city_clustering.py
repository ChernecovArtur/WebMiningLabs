import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import (
    AgglomerativeClustering,
    KMeans,
    SpectralClustering,
)
from sklearn.decomposition import PCA
from sklearn.metrics import (
    adjusted_rand_score,
    silhouette_score,
)
from sklearn.preprocessing import normalize


BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "city_dishes.json"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

COMMON_DISHES = {
    "борщ",
    "блины",
    "пельмени",
    "салат",
}


data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
cities = list(data)

all_dishes = list(next(iter(data.values()))["dishes"])
dishes = [
    dish
    for dish in all_dishes
    if dish not in COMMON_DISHES
]

# Строка — город, столбец — нормализованная частотность блюда
X = np.array([
    [data[city]["dishes"][dish] for dish in dishes]
    for city in cities
])

X_normalized = normalize(X)

parser = argparse.ArgumentParser()
parser.add_argument("--clusters", type=int, default=4)
parser.add_argument("--output", default="cities")
args = parser.parse_args()

k = args.clusters

labels = {
    "kmeans": KMeans(
        n_clusters=k,
        random_state=42,
        n_init=10,
    ).fit_predict(X_normalized),
    "hierarchical": AgglomerativeClustering(
        n_clusters=k,
        linkage="ward",
    ).fit_predict(X_normalized),
    "spectral": SpectralClustering(
        n_clusters=k,
        affinity="cosine",
        random_state=42,
    ).fit_predict(X_normalized),
}

silhouette = {
    method: silhouette_score(X_normalized, values)
    for method, values in labels.items()
}

rand_scores = {
    "kmeans_hierarchical": adjusted_rand_score(
        labels["kmeans"],
        labels["hierarchical"],
    ),
    "kmeans_spectral": adjusted_rand_score(
        labels["kmeans"],
        labels["spectral"],
    ),
    "hierarchical_spectral": adjusted_rand_score(
        labels["hierarchical"],
        labels["spectral"],
    ),
}

# Проверяем ожидаемые содержательные пары
expected_pairs = {
    "Пермь — Кунгур": (
        "Пермь",
        "Кунгур",
    ),
    "Казань — Уфа": (
        "Казань",
        "Уфа",
    ),
}

pair_checks = {}

for pair_name, (first, second) in expected_pairs.items():
    first_index = cities.index(first)
    second_index = cities.index(second)

    pair_checks[pair_name] = {
        method: bool(
            values[first_index] == values[second_index]
        )
        for method, values in labels.items()
    }

# Топ-блюда каждого кластера по исходным частотностям
top_dishes = {}

for cluster in range(k):
    indices = np.where(labels["kmeans"] == cluster)[0]

    if not len(indices):
        continue

    mean_values = X[indices].mean(axis=0)
    top_indices = mean_values.argsort()[-5:][::-1]

    top_dishes[str(cluster)] = [
        {
            "dish": dishes[index],
            "frequency": float(mean_values[index]),
        }
        for index in top_indices
        if mean_values[index] > 0
    ]

result = {
    "clusters": k,
    "cities": [
        {
            "city": city,
            "page_count": data[city]["page_count"],
            "kmeans": int(labels["kmeans"][index]),
            "hierarchical": int(
                labels["hierarchical"][index]
            ),
            "spectral": int(labels["spectral"][index]),
        }
        for index, city in enumerate(cities)
    ],
    "silhouette": silhouette,
    "adjusted_rand": rand_scores,
    "expected_pairs": pair_checks,
    "top_dishes": top_dishes,
}

json_path = OUTPUT_DIR / f"{args.output}_clusters.json"
json_path.write_text(
    json.dumps(result, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

# Проекция городов на плоскость
coordinates = PCA(
    n_components=2,
    random_state=42,
).fit_transform(X_normalized)

fig, ax = plt.subplots(figsize=(10, 7))

scatter = ax.scatter(
    coordinates[:, 0],
    coordinates[:, 1],
    c=labels["kmeans"],
    cmap="Set2",
    s=120,
)

for index, city in enumerate(cities):
    ax.annotate(
        city,
        (coordinates[index, 0], coordinates[index, 1]),
        xytext=(5, 5),
        textcoords="offset points",
    )

ax.set_title("Кластеризация городов по частотности блюд")
ax.set_xlabel("PCA 1")
ax.set_ylabel("PCA 2")
fig.tight_layout()
fig.savefig(
    OUTPUT_DIR / f"{args.output}_clusters.png",
    dpi=150,
)
plt.close(fig)

# Метод локтя и silhouette для выбора K
cluster_range = range(2, 7)
inertia = []
silhouette_scores = []

for cluster_count in cluster_range:
    model = KMeans(
        n_clusters=cluster_count,
        random_state=42,
        n_init=10,
    )
    current_labels = model.fit_predict(X_normalized)

    inertia.append(model.inertia_)
    silhouette_scores.append(
        silhouette_score(X_normalized, current_labels)
    )

fig, (left, right) = plt.subplots(1, 2, figsize=(12, 5))

left.plot(cluster_range, inertia, marker="o")
left.set_title("Метод локтя")
left.set_xlabel("Количество кластеров")
left.set_ylabel("Inertia")

right.plot(
    cluster_range,
    silhouette_scores,
    marker="o",
    color="green",
)
right.set_title("Silhouette score")
right.set_xlabel("Количество кластеров")
right.set_ylabel("Score")

fig.tight_layout()
fig.savefig(
    OUTPUT_DIR / f"{args.output}_evaluation.png",
    dpi=150,
)
plt.close(fig)

print(pd.DataFrame({
    "city": cities,
    **labels,
}).to_string(index=False))

print()
print("Silhouette:", silhouette)
print("Согласие методов:", rand_scores)
print("Проверка пар:", pair_checks)
print(f"Файл сохранён: {json_path}")