import csv
import os
import random
import sys
from math import ceil

# Add the parent directory to sys.path to allow absolute imports when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from prete_py.utils import parse_literal_list


def next_run(dir_path, singleplot):
    os.makedirs(dir_path, exist_ok=True)
    counter_file = os.path.join(dir_path, "counter.txt")
    if not os.path.exists(counter_file):
        with open(counter_file, "w", newline="") as fp:
            fp.write("1")
    with open(counter_file, "r+") as fp:
        value = int(fp.read().strip() or "1")
        if singleplot:
            target = value
            value += 1
            fp.seek(0)
            fp.write(str(value))
            fp.truncate()
        else:
            target = max(1, value - 1)
    result = os.path.join(dir_path, str(target))
    os.makedirs(result, exist_ok=True)
    return result


def weibull_probs(num, shape=0.8, scale=0.0001):
    from random import random
    from math import log

    probs = []
    for _ in range(num):
        u = random()
        probs.append(scale * (-log(1 - u)) ** (1 / shape))
    return probs


def read_cross_layer_topo(data_root, topology, topology_index, verbose=False, expanded_spectrum=0, state_id=1,
                          weibull_failure=False, IPfromFile=False, tofile=False, ground_true=False):
    topo_dir = os.path.join(data_root, topology)
    optical_topo_path = os.path.join(topo_dir, "optical_topo.txt")
    ip_nodes_path = os.path.join(topo_dir, "IP_nodes.txt")
    optical_nodes_path = os.path.join(topo_dir, "optical_nodes.txt")

    optical_links = []
    fiber_lengths = []
    failure_probs = []
    with open(optical_topo_path, newline="") as fp:
        reader = csv.reader(fp, delimiter="\t")
        header = next(reader, None)
        for row in reader:
            if len(row) < 4:
                continue
            to_node = int(float(row[0]))
            from_node = int(float(row[1]))
            length = float(row[2])
            failure_prob = float(row[3])
            optical_links.append((to_node, from_node))
            fiber_lengths.append(length)
            failure_probs.append(failure_prob)

    optical_nodes = []
    with open(optical_nodes_path, newline="") as fp:
        for row in csv.reader(fp, delimiter="\t"):
            if row:
                optical_nodes.append(row[0].strip())

    ip_nodes = []
    with open(ip_nodes_path, newline="") as fp:
        for row in csv.reader(fp, delimiter="\t"):
            if row:
                ip_nodes.append(row[0].strip())

    if IPfromFile:
        topo_path = os.path.join(topo_dir, f"IP_topo_{topology_index}", f"IP_topo_{topology_index}.txt")
        ip_links, capacities, fiber_routes, wavelengths, failures = _read_ip_topology_from_file(topo_path)
    else:
        ip_links, capacities, fiber_routes, wavelengths, failures = provision_ip_topology(
            data_root, topology, topology_index, scaling=1, density=0.98, linknum=None, ilp_planning=False, tofile=tofile
        )

    optical_topo = {
        "nodes": optical_nodes,
        "links": optical_links,
        "fiber_length": fiber_lengths,
        "fiber_probs": failure_probs,
        "bidirect_links": _build_bidirectional_links(optical_links),
        "bidirect_fiber_probs": _build_bidirectional_probs(optical_links, failure_probs),
        "fiber_spectrum": [[] for _ in optical_links],
        "capacity": [96 + expanded_spectrum] * len(optical_links),
    }
    optical_topo["capacity_code"] = [[1] * (96 + expanded_spectrum) for _ in optical_links]

    ip_topo = {
        "nodes": ip_nodes,
        "links": ip_links,
        "capacity": capacities,
        "fiberpath": fiber_routes,
        "link_probs": failures,
        "link_fiberroute": fiber_routes,
        "link_length": [sum(optical_topo["fiber_length"][i - 1] for i in route) for route in fiber_routes],
        "link_wavelength": wavelengths,
    }

    if verbose:
        print(f"Loaded optical topo {len(optical_links)} links and IP topo {len(ip_links)} links for {topology}")

    return ip_topo, optical_topo


def read_demand(data_root, filename, num_nodes, demand_index, scale, downscale, rescale, matrix=True, sigfigs=1, zeroindex=False):
    path = os.path.join(data_root, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Demand file not found: {path}")
    demand_values = []
    with open(path, newline="") as fp:
        reader = csv.reader(fp, delimiter=" ")
        for idx, row in enumerate(reader, 1):
            if idx == demand_index:
                demand_values = [float(x) for x in row if x.strip()]
                break
    if not demand_values:
        raise ValueError(f"Demand {demand_index} not found in {path}")

    if matrix and len(demand_values) == num_nodes * num_nodes:
        demand_values = [val * scale / downscale for val in demand_values]
        flows = []
        for src in range(1, num_nodes + 1):
            for dst in range(1, num_nodes + 1):
                if src != dst:
                    flows.append((src, dst))
        demand_values = [demand_values[(src - 1) * num_nodes + (dst - 1)] for src, dst in flows]
    else:
        demand_values = [val * scale / downscale for val in demand_values]
        flows = [(i + 1, i + 2) for i in range(len(demand_values))]

    return demand_values, flows


def _read_ip_topology_from_file(filepath):
    links = []
    capacities = []
    fiber_routes = []
    wavelengths = []
    failures = []
    with open(filepath, newline="") as fp:
        reader = csv.reader(fp, delimiter="\t")
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 7:
                continue
            src = int(float(row[0]))
            dst = int(float(row[1]))
            index = int(float(row[2]))
            capacity = int(float(row[3])) * 100
            fiber_route = parse_literal_list(row[4])
            wavelength = parse_literal_list(row[5])
            failure = float(row[6])
            links.append((src, dst, index))
            capacities.append(capacity)
            fiber_routes.append(fiber_route)
            wavelengths.append(wavelength)
            failures.append(failure)
    return links, capacities, fiber_routes, wavelengths, failures


def _build_bidirectional_links(links):
    seen = []
    for a, b in links:
        if (a, b) not in seen and (b, a) not in seen:
            seen.append((a, b))
    return seen


def _build_bidirectional_probs(links, failure_probs):
    seen = []
    bidirect = []
    for (a, b), p in zip(links, failure_probs):
        if (a, b) not in seen and (b, a) not in seen:
            seen.append((a, b))
            bidirect.append(p)
    return bidirect


def provision_ip_topology(data_root, topology, topology_index, scaling=5, density=0.98, linknum=None, ilp_planning=False, tofile=True):
    from prete_py.topoprovision import provision_ip_topology as provision_fn
    topology_dir = os.path.join(data_root, topology)
    return provision_fn(topology_dir, topology_index, scaling=scaling, density=density, linknum=linknum, ilp_planning=ilp_planning, tofile=tofile)
