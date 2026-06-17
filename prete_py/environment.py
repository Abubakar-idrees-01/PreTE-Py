import os
import sys

# Add the parent directory to sys.path to allow absolute imports when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import networkx as nx

from prete_py.interface import read_cross_layer_topo


def get_failure_scenarios(data_root, topology, topology_index, verbose, cutoff, scenario_id, weibull_or_k,
                          failure_free, expanded_spectrum, state_id, ground_true=False):
    print(f"[environment] get_failure_scenarios start: topology={topology}, topology_index={topology_index}, cutoff={cutoff}, failure_free={failure_free}")
    IPTopo, OpticalTopo = read_cross_layer_topo(
        data_root,
        topology,
        topology_index,
        verbose=verbose,
        expanded_spectrum=expanded_spectrum,
        state_id=state_id,
        weibull_failure=(weibull_or_k == 1),
        IPfromFile=True,
        tofile=False,
        ground_true=ground_true,
    )
    if failure_free:
        OpticalTopo["fiber_probs"] = [0.0 for _ in OpticalTopo["fiber_probs"]]
        OpticalTopo["bidirect_fiber_probs"] = [0.0 for _ in OpticalTopo["bidirect_fiber_probs"]]

    IPScenarios, OpticalScenarios = get_all_scenarios(IPTopo, OpticalTopo, cutoff)
    print(f"[environment] get_failure_scenarios done: {len(IPScenarios['code'])} IP scenarios, {len(OpticalScenarios['code'])} optical scenarios")
    return IPTopo, OpticalTopo, IPScenarios, OpticalScenarios


def get_all_scenarios(IPTopo, OpticalTopo, cutoff, is_ffc_scenario=False, ffc_fiber_cut_num=1):
    print(f"[environment] get_all_scenarios start: is_ffc_scenario={is_ffc_scenario}, cutoff={cutoff}, bidirect_links={len(OpticalTopo['bidirect_links'])}")
    if is_ffc_scenario:
        scenarios = [[1] * len(OpticalTopo["bidirect_links"])]
        probs = [1.0]
        if ffc_fiber_cut_num > 0:
            from itertools import combinations
            for combo in combinations(range(len(OpticalTopo["bidirect_links"])), ffc_fiber_cut_num):
                scenario = [1] * len(OpticalTopo["bidirect_links"])
                prob = 1.0
                for idx in combo:
                    scenario[idx] = 0
                    prob *= OpticalTopo["bidirect_fiber_probs"][idx]
                scenarios.append(scenario)
                probs.append(prob)
        probs[0] = 1.0 - sum(probs[1:])
    else:
        scenarios, probs = sub_scenarios(OpticalTopo, IPTopo, cutoff)
    print(f"[environment] get_all_scenarios generated {len(scenarios)} raw optical scenarios")

    oscenarios = []
    oprobs = probs
    for scenario in scenarios:
        current = [1] * len(OpticalTopo["links"])
        for index, value in enumerate(scenario):
            if value == 0:
                bidir_edge = OpticalTopo["bidirect_links"][index]
                for idx, edge in enumerate(OpticalTopo["links"]):
                    if edge == bidir_edge or edge == (bidir_edge[1], bidir_edge[0]):
                        current[idx] = 0
        oscenarios.append(current)

    IPScenarios = {"code": [], "prob": []}
    for opt_scenario, prob in zip(oscenarios, oprobs):
        ip_scenario = [1] * len(IPTopo["links"])
        for fiber_index, fiber_status in enumerate(opt_scenario, start=1):
            if fiber_status == 0:
                for link_index, route in enumerate(IPTopo["link_fiberroute"]):
                    if fiber_index in route:
                        ip_scenario[link_index] = 0
        IPScenarios["code"].append(ip_scenario)
        IPScenarios["prob"].append(prob)

    OpticalScenarios = {"code": oscenarios, "prob": oprobs}
    return IPScenarios, OpticalScenarios


def sub_scenarios(optical_topo, IPTopo, cutoff, first=True, last=True):
    original = optical_topo["bidirect_fiber_probs"]
    progress = {"count": 0}
    scenarios, probabilities = sub_scenarios_recursion(optical_topo, IPTopo, original, cutoff, progress=progress)
    print(f"[environment] sub_scenarios completed recursion: {progress['count']} feasible scenarios found")
    if not first:
        scenarios = scenarios[1:]
        probabilities = probabilities[1:]
    if last:
        scenarios.append([0] * len(scenarios[0]))
        probabilities.append(1.0 - sum(probabilities))
    if sum(probabilities) < 1e-12:
        normalized = [0.0 for _ in probabilities]
    else:
        normalized = [p / sum(probabilities) for p in probabilities]
    return scenarios, normalized


def sub_scenarios_recursion(optical_topo, IPTopo, original, cutoff, remaining=None, partial=None, scenarios=None, probabilities=None, progress=None):
    if remaining is None:
        remaining = list(range(len(original)))
    if partial is None:
        partial = []
    if scenarios is None:
        scenarios = []
    if probabilities is None:
        probabilities = []
    if progress is None:
        progress = {"count": 0}

    if not partial:
        scenarios.append([1] * len(original))
        probabilities.append(float(sum((1 - p) for p in original)))
        remaining = list(range(len(original)))
    else:
        bitmap = [1] * len(original)
        product = 1.0
        for index in partial:
            bitmap[index] = 0
            product *= original[index]
        if product >= cutoff:
            if optical_graph_connectivity(optical_topo, bitmap):
                ip_bitmap = [1] * len(IPTopo["links"])
                for link_index, route in enumerate(IPTopo["link_fiberroute"]):
                    if any(bitmap[f - 1] == 0 for f in route):
                        ip_bitmap[link_index] = 0
                if ip_graph_connectivity(IPTopo, ip_bitmap):
                    scenarios.append(bitmap.copy())
                    probabilities.append(product)
                    progress["count"] += 1
                    if progress["count"] % 10 == 0:
                        print(f"[environment] sub_scenarios found {progress['count']} feasible scenarios so far")
        else:
            return scenarios, probabilities

    for i, fiber_index in enumerate(remaining):
        next_remaining = remaining[i + 1 :]
        next_partial = partial + [fiber_index]
        sub_scenarios_recursion(optical_topo, IPTopo, original, cutoff, next_remaining, next_partial, scenarios, probabilities, progress=progress)

    return scenarios, probabilities


def optical_graph_connectivity(optical_topo, optical_failure_bitmap):
    graph = nx.DiGraph()
    graph.add_nodes_from(range(1, len(optical_topo["nodes"]) + 1))
    for idx, edge in enumerate(optical_topo["bidirect_links"]):
        if optical_failure_bitmap[idx] > 0:
            graph.add_edge(edge[0], edge[1])
            graph.add_edge(edge[1], edge[0])
    return nx.is_strongly_connected(graph)


def ip_graph_connectivity(IP_topo, IP_failure_bitmap):
    graph = nx.DiGraph()
    graph.add_nodes_from(range(1, len(IP_topo["nodes"]) + 1))
    for idx, edge in enumerate(IP_topo["links"]):
        if IP_failure_bitmap[idx] > 0:
            graph.add_edge(edge[0], edge[1])
    return nx.is_strongly_connected(graph)
