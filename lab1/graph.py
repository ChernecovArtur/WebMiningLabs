import csv
from itertools import combinations
from pathlib import Path
from urllib.parse import urlsplit

from graphviz import Digraph


BASE_DIR = Path(__file__).parent
N = 2


def get_domain(url):
    return urlsplit(url).netloc.lower().removeprefix("www.")


def build_edges(resources, only_between_sites=False):
    edges = []

    for first, second in combinations(resources, 2):
        if only_between_sites:
            first_domain = get_domain(first["url"])
            second_domain = get_domain(second["url"])

            if first_domain == second_domain:
                continue

        common = first["terms_set"] & second["terms_set"]

        if len(common) >= N:
            edges.append({
                "source": first["id"],
                "target": second["id"],
                "weight": len(common),
                "common_terms": "; ".join(sorted(common)),
            })

    return edges


def save_edges(filename, edges):
    with open(
        BASE_DIR / filename,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "source",
                "target",
                "weight",
                "common_terms",
            ],
        )
        writer.writeheader()
        writer.writerows(edges)


def save_graph(filename, resources, edges):
    dot = Digraph("MetallurgyResources")
    dot.attr(rankdir="LR", overlap="false", splines="true")
    dot.attr(
        "node",
        shape="box",
        style="rounded,filled",
        fillcolor="#E8F4FA",
    )

    for resource in resources:
       # tooltip = f'{resource["title"]} | Термины: {resource["terms"]}'
        terms = resource["terms"].split("; ")
        short_terms = "; ".join(terms[:40])

        if len(terms) > 40:
            short_terms += "; ..."

        tooltip = f'{resource["title"]} | Термины: {short_terms}'
        dot.node(
            resource["id"],
            label=resource["id"],
            tooltip=tooltip,
            URL=resource["url"],
        )

    for edge in edges:
        dot.edge(
            edge["source"],
            edge["target"],
            label=str(edge["weight"]),
            tooltip=edge["common_terms"][:4000],
        )

    (BASE_DIR / f"{filename}.dot").write_text(
        dot.source,
        encoding="utf-8",
    )

    dot.render(
        str(BASE_DIR / filename),
        format="pdf",
        cleanup=True,
    )
    dot.render(
        str(BASE_DIR / filename),
        format="svg",
        cleanup=True,
    )


with open(
    BASE_DIR / "terms.csv",
    encoding="utf-8-sig",
) as file:
    resources = list(csv.DictReader(file))

for resource in resources:
    resource["terms_set"] = set(resource["terms"].split("; "))

edges = build_edges(resources)
between_sites_edges = build_edges(
    resources,
    only_between_sites=True,
)

save_edges("edges.csv", edges)
save_edges("edges_between_sites.csv", between_sites_edges)

save_graph("graph", resources, edges)
save_graph(
    "graph_between_sites",
    resources,
    between_sites_edges,
)

print(f"Узлов: {len(resources)}")
print(f"Рёбер в общем графе: {len(edges)}")
print(f"Рёбер в межсайтовом графе: {len(between_sites_edges)}")