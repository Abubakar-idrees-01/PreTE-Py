import time

import networkx as nx
import pulp


def wave_rerouting(optical_topo, failed_ip_edges, failed_fibers_index, rerouting_k):
    graph = nx.DiGraph()
    for idx, edge in enumerate(optical_topo["links"], start=1):
        if idx in failed_fibers_index:
            continue
        graph.add_edge(edge[0], edge[1], weight=optical_topo["fiber_length"][idx - 1])

    rehoused_edges = []
    rehoused_paths = []
    branch_index_all = []
    branch_groups = []
    current_branch = 0

    for failed_edge in failed_ip_edges:
        src, dst, _ = failed_edge
        try:
            paths = list(nx.shortest_simple_paths(graph, src, dst, weight="weight"))[:rerouting_k]
        except nx.NetworkXNoPath:
            paths = []
        edge_sets = []
        group_indices = []
        for path in paths:
            route = []
            for u, v in zip(path[:-1], path[1:]):
                index = next((i for i, link in enumerate(optical_topo["links"], start=1) if link == (u, v)), None)
                if index is None:
                    route = []
                    break
                route.append(index)
            if route:
                edge_sets.append(route)
                branch_indices = list(range(current_branch, current_branch + 1))
                group_indices.append(branch_indices)
                current_branch += 1
        rehoused_edges.extend(edge_sets)
        rehoused_paths.extend(paths)
        branch_index_all.extend([idx for idx in range(current_branch - len(paths), current_branch)])
        branch_groups.append(branch_index_all[-len(paths) :])

    return rehoused_edges, rehoused_paths, branch_index_all, branch_groups


def restore_ilp(optical_topo, failed_ip_edges, failed_ip_branch_routing_fiber, failed_ip_branch_index_groups,
                failed_ip_initial_bw, rerouting_k):
    n_wavelength = len(optical_topo["capacity_code"][0])
    n_branches = len(failed_ip_branch_routing_fiber)
    capacity_code = optical_topo["capacity_code"]
    model = pulp.LpProblem("restore_ilp", pulp.LpMaximize)

    x = pulp.LpVariable.dicts("x", (range(n_branches), range(n_wavelength)), lowBound=0, upBound=1, cat="Binary")
    restored_bw = pulp.LpVariable.dicts("restored_bw", range(len(failed_ip_edges)), lowBound=0, cat="Integer")

    for branch, route in enumerate(failed_ip_branch_routing_fiber):
        for wave in range(n_wavelength):
            for fiber in route:
                if capacity_code[fiber - 1][wave] == 0:
                    model += x[branch][wave] == 0

    for fiber_idx in range(len(optical_topo["links"])):
        for wave in range(n_wavelength):
            model += pulp.lpSum(
                x[branch][wave]
                for branch, route in enumerate(failed_ip_branch_routing_fiber)
                if fiber_idx + 1 in route
            ) <= capacity_code[fiber_idx][wave]

    link_to_branches = {}
    for link_idx, group in enumerate(failed_ip_branch_index_groups):
        link_to_branches[link_idx] = list(group)

    for link_idx, branch_indices in link_to_branches.items():
        model += restored_bw[link_idx] == 100 * pulp.lpSum(x[b][wave] for b in branch_indices for wave in range(n_wavelength))
        model += restored_bw[link_idx] <= failed_ip_initial_bw[link_idx]

    model += pulp.lpSum(restored_bw[l] for l in range(len(failed_ip_edges)))
    model.solve(pulp.PULP_CBC_CMD(msg=False))

    restored = [int(round(pulp.value(restored_bw[l]))) for l in range(len(failed_ip_edges))]
    return restored, model.objective.value(), None


def restore_lp(optical_topo, failed_ip_edges, failed_ip_branch_routing_fiber, failed_ip_branch_index_groups,
               failed_ip_initial_bw, rerouting_k):
    n_wavelength = len(optical_topo["capacity_code"][0])
    model = pulp.LpProblem("restore_lp", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("x", (range(len(failed_ip_branch_routing_fiber)), range(n_wavelength)), lowBound=0, upBound=1)
    restored_bw = pulp.LpVariable.dicts("restored_bw", range(len(failed_ip_edges)), lowBound=0)

    for fiber_idx in range(len(optical_topo["links"])):
        for wave in range(n_wavelength):
            model += pulp.lpSum(
                x[branch][wave]
                for branch, route in enumerate(failed_ip_branch_routing_fiber)
                if fiber_idx + 1 in route
            ) <= optical_topo["capacity_code"][fiber_idx][wave]

    link_to_branches = {link_idx: list(group) for link_idx, group in enumerate(failed_ip_branch_index_groups)}
    for link_idx, branch_indices in link_to_branches.items():
        model += restored_bw[link_idx] == 100 * pulp.lpSum(x[b][wave] for b in branch_indices for wave in range(n_wavelength))
        model += restored_bw[link_idx] <= failed_ip_initial_bw[link_idx]

    model += pulp.lpSum(restored_bw[l] for l in range(len(failed_ip_edges)))
    model.solve(pulp.PULP_CBC_CMD(msg=False))

    restored = [float(pulp.value(restored_bw[l])) for l in range(len(failed_ip_edges))]
    return restored, model.objective.value(), None


def random_rounding(lp_solution, option_num, option_gap, verbose=False):
    tickets = []
    if not lp_solution:
        return tickets
    base = max(1, int(round(sum(lp_solution) * (1 - option_gap) / option_num)))
    for ticket_id in range(option_num):
        ticket = [min(100, max(0, int(round(value / 100))) * 100) for value in lp_solution]
        if ticket_id % 2 == 1:
            ticket = [max(0, val - base) for val in ticket]
        tickets.append(ticket)
    if verbose:
        print(f"Generated {len(tickets)} random-rounding tickets")
    return tickets
