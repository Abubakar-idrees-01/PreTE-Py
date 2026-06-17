import os

import matplotlib.pyplot as plt


def save_cdf(values, path, xlabel="Value", ylabel="CDF", title=None):
    if not values:
        return
    values = sorted(values)
    cdf = [float(i + 1) / len(values) for i in range(len(values))]
    plt.clf()
    plt.plot(values, cdf, marker="o", linewidth=1)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if title:
        plt.title(title)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    plt.savefig(path)


def draw_tunnel(topology, tunnel_bw, T1, Tf1, links, node_count, output_dir, algorithm):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{topology}_{algorithm}_tunnel_bw.png")
    plt.clf()
    plt.plot(tunnel_bw, marker="o")
    plt.title(f"Tunnel bandwidth for {algorithm}")
    plt.xlabel("Tunnel index")
    plt.ylabel("Bandwidth")
    plt.savefig(path)


def draw_graph(edges, capacities, output_path, title="Graph"):
    try:
        import networkx as nx
    except ImportError:
        return
    graph = nx.DiGraph()
    for idx, edge in enumerate(edges):
        graph.add_edge(edge[0], edge[1], capacity=capacities[idx])
    pos = nx.spring_layout(graph)
    plt.clf()
    nx.draw(graph, pos, with_labels=True, node_size=300, arrowsize=10)
    labels = {edge: str(data["capacity"]) for edge, data in nx.get_edge_attributes(graph, "capacity").items()}
    nx.draw_networkx_edge_labels(graph, pos, edge_labels=labels)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.title(title)
    plt.savefig(output_path)
