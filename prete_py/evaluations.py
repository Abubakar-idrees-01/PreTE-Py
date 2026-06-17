def scenario_availability(losses, probabilities, conditional=False):
    if not losses or not probabilities:
        return 0.0
    total = 0.0
    for loss, prob in zip(losses, probabilities):
        total += (1.0 - loss) * prob
    if conditional:
        total /= sum(probabilities)
    return total


def flow_availability(losses, affected_flows, flows, probabilities, conditional=False):
    if not flows:
        return 0.0
    flow_probs = sum(probabilities)
    total = 0.0
    for loss, prob in zip(losses, probabilities):
        total += (1.0 - loss) * prob
    if conditional and flow_probs:
        total /= flow_probs
    return total


def bandwidth_availability(losses, probabilities, conditional=False):
    return scenario_availability(losses, probabilities, conditional)


def scenario_loss(losses, probabilities, conditional=False):
    if not losses or not probabilities:
        return 0.0
    total = sum(loss * prob for loss, prob in zip(losses, probabilities))
    if conditional and sum(probabilities):
        total /= sum(probabilities)
    return total


def compute_links_utilization(links, capacities, demand, flows, T1, Tf1, tunnel_bw):
    utilization = [0.0] * len(links)
    for flow_idx, tunnel_indices in enumerate(Tf1):
        for tunnel_idx in tunnel_indices:
            for link_idx in T1[tunnel_idx]:
                if link_idx < len(utilization):
                    utilization[link_idx] += tunnel_bw[tunnel_idx]
    return utilization


def traffic_reassignment(links_utilization, links, capacities, demand, flows, T1, Tf1, tunnel_bw, flow_bw,
                         scenarios, restored_bw, algorithm, verbose=False):
    losses = []
    affected_flows = []
    router_ports = []
    sloss = []
    for scenario_idx, scenario in enumerate(scenarios):
        scenario_loss = 0.0
        flow_loss = 0.0
        current_flows = []
        for flow_idx, flow in enumerate(flows):
            achieved = flow_bw[flow_idx] if flow_idx < len(flow_bw) else 0.0
            demand_value = demand[flow_idx] if flow_idx < len(demand) else 0.0
            loss = max(0.0, 1.0 - achieved / max(1.0, demand_value))
            flow_loss += loss
            scenario_loss += loss
            if loss > 0:
                current_flows.append(flow)
        losses.append(scenario_loss / max(1.0, len(flows)))
        affected_flows.append(len(current_flows))
        router_ports.append(sum(1 for link_idx, status in enumerate(scenario) if status == 0))
        sloss.append(scenario_loss)
    return losses, affected_flows, router_ports, sloss
