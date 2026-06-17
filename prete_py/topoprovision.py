import csv
import os
import random
import sys

# Add the parent directory to sys.path to allow absolute imports when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import networkx as nx

from prete_py.utils import parse_literal_list


def _read_table(path, delimiter="\t"):
    rows = []
    with open(path, newline="") as fp:
        reader = csv.reader(fp, delimiter=delimiter)
        header = next(reader, None)
        for row in reader:
            if row:
                rows.append([cell.strip() for cell in row])
    return rows


def ip_capacity_distribution(topology_dir, linknum):
    path = os.path.join(topology_dir, "IPCapacityDistribution.txt")
    samples = []
    if os.path.exists(path):
        with open(path, newline="") as fp:
            for row in csv.reader(fp, delimiter="\t"):
                if row and row[0].strip():
                    samples.append(float(row[0]))
    if not samples:
        samples = [random.expovariate(1.0) for _ in range(max(linknum, 1))]
    if len(samples) < linknum:
        samples = samples * (linknum // len(samples) + 1)
    values = [max(1, int(round(val))) for val in samples[:linknum]]
    return values


def provision_ip_topology(topology_dir, topology_index, scaling=5, density=0.98, linknum=None, ilp_planning=False, tofile=True):
    optical_topo_path = os.path.join(topology_dir, "optical_topo.txt")
    optical_nodes_path = os.path.join(topology_dir, "optical_nodes.txt")
    ip_nodes_path = os.path.join(topology_dir, "IP_nodes.txt")

    optical_rows = _read_table(optical_topo_path)
    optical_links = []
    optical_lengths = []
    for row in optical_rows:
        if len(row) < 3:
            continue
        src = int(float(row[0]))
        dst = int(float(row[1]))
        metric = float(row[2])
        optical_links.append((src, dst))
        optical_lengths.append(metric)

    ip_nodes = [row[0] for row in _read_table(ip_nodes_path)]
    max_node = len(ip_nodes)
    if max_node < 2:
        raise ValueError("IP node list must contain at least two nodes")

    graph = nx.DiGraph()
    for (src, dst), length in zip(optical_links, optical_lengths):
        graph.add_edge(src, dst, weight=length)

    if linknum is None:
        linknum = int(round(density * max_node * (max_node - 1) / 2))
    capacities = ip_capacity_distribution(topology_dir, linknum)
    capacities = [max(1, cap + scaling) for cap in capacities]

    available_edges = [(u, v) for u in range(1, max_node + 1) for v in range(u + 1, max_node + 1)]
    random.shuffle(available_edges)
    ip_links = []
    fiber_routes = []
    wavelengths = []
    failures = []

    selected = 0
    for src, dst in available_edges:
        if selected >= linknum:
            break
        try:
            path = nx.shortest_path(graph, src, dst, weight="weight")
        except nx.NetworkXNoPath:
            continue
        if len(path) < 2:
            continue
        route = []
        for a, b in zip(path[:-1], path[1:]):
            matches = [i for i, edge in enumerate(optical_links, start=1) if edge == (a, b)]
            if not matches:
                route = []
                break
            route.append(matches[0])
        if not route:
            continue

        capacity = capacities[selected]
        used_wavelengths = []
        for w in range(1, 97):
            if len(used_wavelengths) >= capacity:
                break
            used_wavelengths.append(w)

        failure_probability = 0.001 * len(route)
        ip_links.append((src, dst, selected + 1))
        fiber_routes.append(route)
        wavelengths.append(used_wavelengths)
        failures.append(failure_probability)
        selected += 1

    if tofile:
        ip_dir = os.path.join(topology_dir, f"IP_topo_{topology_index}")
        os.makedirs(ip_dir, exist_ok=True)
        file_path = os.path.join(ip_dir, f"IP_topo_{topology_index}.txt")
        with open(file_path, "w", newline="") as fp:
            writer = csv.writer(fp, delimiter="\t")
            writer.writerow(["src", "dst", "index", "capacity", "fiberpath_index", "wavelength", "failure"])
            for link, capacity, route, wavelength, failure in zip(ip_links, capacities, fiber_routes, wavelengths, failures):
                writer.writerow([
                    link[0],
                    link[1],
                    link[2],
                    int(capacity / 100) if capacity >= 100 else capacity,
                    str(route),
                    str(wavelength),
                    failure,
                ])

    return ip_links, [cap * 100 for cap in capacities], fiber_routes, wavelengths, failures
