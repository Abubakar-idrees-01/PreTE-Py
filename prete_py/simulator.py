import os
import sys
import time

# Add the parent directory to sys.path to allow absolute imports when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import networkx as nx
import pulp

from prete_py.environment import get_failure_scenarios
from prete_py.evaluations import compute_links_utilization, flow_availability, scenario_availability, traffic_reassignment
from prete_py.restoration import random_rounding, restore_ilp, restore_lp, wave_rerouting
from prete_py.plotting import draw_tunnel
from prete_py.interface import read_demand


def _build_ip_graph(IPTopo):
    graph = nx.DiGraph()
    edge_map = {}
    for idx, link in enumerate(IPTopo["links"]):
        src, dst, _ = link
        graph.add_edge(src, dst, weight=IPTopo["link_length"][idx], index=idx)
        edge_map[(src, dst)] = idx
    return graph, edge_map


def get_tunnels(IPTopo, OpticalTopo, flows, tunnelK, new_tunnel_or_not, verbose, scenarios, new_tunnel_num, max_new_tunnel_num, edge_disjoint=0):
    graph, edge_map = _build_ip_graph(IPTopo)
    T1 = []
    Tf1 = []
    if verbose:
        print(f"[simulator] get_tunnels start: {len(flows)} flows, tunnelK={tunnelK}")
    for flow_idx, flow in enumerate(flows, start=1):
        src, dst = flow
        try:
            paths = list(nx.shortest_simple_paths(graph, src, dst, weight="weight"))[:tunnelK]
        except (nx.NetworkXNoPath, StopIteration):
            paths = []
        tunnel_indices = []
        for path in paths:
            edges = []
            for u, v in zip(path[:-1], path[1:]):
                if (u, v) in edge_map:
                    edges.append(edge_map[(u, v)])
            if edges:
                T1.append(edges)
                tunnel_indices.append(len(T1) - 1)
        Tf1.append(tunnel_indices)
        if verbose and flow_idx % 20 == 0:
            print(f"[simulator] get_tunnels progress: processed {flow_idx}/{len(flows)} flows, {len(T1)} tunnels so far")
    if verbose:
        print(f"[simulator] get_tunnels complete: generated {len(T1)} tunnels for {len(flows)} flows")
    return T1, Tf1


def TrafficEngineering(IPTopo, OpticalTopo, algorithm, links, capacities, demand, flows, T1, Tf1, IPScenarios, OpticalScenarios,
                       prob, scenario_restored_bw, optical_rerouting_K, tunnelK_s, beta, absolute_gap, verbose, solve_or_not):
    num_tunnels = len(T1)
    model = pulp.LpProblem("TE", pulp.LpMaximize)
    b = pulp.LpVariable.dicts("b", range(num_tunnels), lowBound=0)

    flow_demands = [sum(demand[i] for i in range(len(demand))) / max(1, len(flows))] * len(flows)
    for flow_idx, tunnel_indices in enumerate(Tf1):
        if tunnel_indices:
            for t in tunnel_indices:
                model += b[t] <= demand[flow_idx]

    for link_idx, cap in enumerate(capacities):
        model += pulp.lpSum(b[t] for t, path in enumerate(T1) if link_idx in path) <= cap

    model += pulp.lpSum(b[t] for t in range(num_tunnels))
    model.solve(pulp.PULP_CBC_CMD(msg=False))

    TunnelBw = [float(pulp.value(b[t])) if pulp.value(b[t]) is not None else 0.0 for t in range(num_tunnels)]
    FlowBw = [sum(TunnelBw[t] for t in Tf1[f] if t < len(TunnelBw)) for f in range(len(flows))]
    initial_throughput = sum(FlowBw)
    TEruntime = 0.0
    best_options = None
    best_scenario_restored_bw = scenario_restored_bw
    if verbose:
        print(f"TE assigned {initial_throughput} bandwidth across {num_tunnels} tunnels")
    return TunnelBw, FlowBw, 0.0, initial_throughput, TEruntime, best_options, best_scenario_restored_bw


def abstract_optical_layer(topology, topology_index, IPTopo, OpticalTopo, IPScenarios, OpticalScenarios,
                           scenario_generation_only, run_dir, topology_name, ticketsnum, largeticketsnum,
                           tunneltype, beta, verbose):
    rwa_scenario_restored_bw = []
    rr_scenario_restored_bw = []
    absolute_gap = [0.0] * len(IPScenarios["code"])

    for q, scenario_code in enumerate(IPScenarios["code"]):
        if sum(scenario_code) < len(scenario_code):
            failed_fibers = [idx + 1 for idx, v in enumerate(OpticalScenarios["code"][q]) if v == 0]
            failed_ip_edges = [IPTopo["links"][idx] for idx, status in enumerate(scenario_code) if status == 0]
            failed_ip_initialindex = [idx for idx, status in enumerate(scenario_code) if status == 0]
            failed_ip_initialbw = [IPTopo["capacity"][idx] for idx in failed_ip_initialindex]
            rehoused_IProutingEdge, rehoused_IProuting, failedIPbranckindex, failedIPbrachGroup = wave_rerouting(
                OpticalTopo, failed_ip_edges, failed_fibers, optical_rerouting_K
            )
            restored_bw_rwa, _, _ = restore_ilp(OpticalTopo, failed_ip_edges, rehoused_IProuting, failedIPbrachGroup,
                                               failed_ip_initialbw, optical_rerouting_K)
            lp_restored_bw, _, _ = restore_lp(OpticalTopo, failed_ip_edges, rehoused_IProuting, failedIPbrachGroup,
                                              failed_ip_initialbw, optical_rerouting_K)
            rwa_full = list(IPTopo["capacity"])
            rr_full = []
            for i, idx in enumerate(failed_ip_initialindex):
                rwa_full[idx] = int(round(restored_bw_rwa[i]))
            for _ in range(ticketsnum):
                rr_ticket = list(IPTopo["capacity"])
                for i, idx in enumerate(failed_ip_initialindex):
                    rr_ticket[idx] = int(round(lp_restored_bw[i]))
                rr_full.append(rr_ticket)
            rwa_scenario_restored_bw.append(rwa_full)
            rr_scenario_restored_bw.append(rr_full)
        else:
            rwa_scenario_restored_bw.append(list(IPTopo["capacity"]))
            rr_scenario_restored_bw.append([list(IPTopo["capacity"]) for _ in range(ticketsnum)])

    return rwa_scenario_restored_bw, rr_scenario_restored_bw, absolute_gap


def run_simulation(data_root, topology, topology_index, traffic, scale, algorithm, parallel_dir, cutoff,
                   tunnel, scenario_id, ticketsnum, largeticketsnum, beta, tunneltype, failure_simulation,
                   failure_free, expandspectrum, filter_option, train_prob, test_prob, max_flows, verbose):
    # data_root = os.path.abspath("./data/topology")
    output_dir = os.path.abspath("./data/experiment/run")
    os.makedirs(output_dir, exist_ok=True)
    print("[simulator] calling get_failure_scenarios...")
    IPTopo, OpticalTopo, IPScenarios, OpticalScenarios = get_failure_scenarios(
        data_root, topology, topology_index, verbose, cutoff, scenario_id, 1, failure_free, expandspectrum, 1
    )
    print(f"[simulator] get_failure_scenarios complete: {len(IPScenarios['code'])} scenarios")

    print("[simulator] calling read_demand...")
    initial_demand, flows = read_demand(data_root, f"{topology}/demand.txt", len(IPTopo["nodes"]), traffic, scale, 1.0, False)
    
    # Limit flows for faster testing
    if max_flows is not None and len(flows) > max_flows:
        print(f"[simulator] Limiting flows from {len(flows)} to {max_flows} for faster simulation")
        flows = flows[:max_flows]
        initial_demand = initial_demand[:max_flows]
    
    print(f"[simulator] read_demand complete: {len(flows)} flows")

    print("[simulator] calling get_tunnels...")
    T1, Tf1 = get_tunnels(IPTopo, OpticalTopo, flows, tunnel, 0, verbose, IPScenarios["code"], 0, 0, edge_disjoint=tunneltype)
    print(f"[simulator] get_tunnels complete: {len(T1)} tunnels")

    scenario_restored_bw = []
    for scenario in IPScenarios["code"]:
        if sum(scenario) < len(scenario):
            scenario_restored_bw.append(list(IPTopo["capacity"]))
        else:
            scenario_restored_bw.append(list(IPTopo["capacity"]))

    TunnelBw, FlowBw, var, initial_throughput, TEruntime, best_options, best_scenario_restored_bw = TrafficEngineering(
        IPTopo, OpticalTopo, algorithm, IPTopo["links"], IPTopo["capacity"], initial_demand, flows, T1, Tf1,
        IPScenarios, OpticalScenarios, IPScenarios["prob"], scenario_restored_bw, 3, tunnel, beta, [0.0], verbose, False
    )

    if failure_simulation:
        links_util = compute_links_utilization(IPTopo["links"], IPTopo["capacity"], initial_demand, flows, T1, Tf1, TunnelBw)
        losses, affected_flows, router_ports, sloss = traffic_reassignment(
            links_util, IPTopo["links"], IPTopo["capacity"], initial_demand, flows, T1, Tf1, TunnelBw,
            FlowBw, IPScenarios["code"], best_scenario_restored_bw, algorithm, verbose
        )
        aval = scenario_availability(losses, IPScenarios["prob"], conditional=False)
        print(f"Scenario availability: {aval}")

    draw_tunnel(topology, TunnelBw, T1, Tf1, IPTopo["links"], len(IPTopo["nodes"]), output_dir, algorithm)
    print(f"Finished simulation for {topology} algorithm {algorithm}")
