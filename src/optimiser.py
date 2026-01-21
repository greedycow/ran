from generate_data import OperatorParams
from allocate import allocate_uniform_until_saturation
from itertools import combinations


def coalition_utility(
    coalition: list[int],
    guardians: list[int],
    operators: list[OperatorParams],
    traffic_at_t: dict[int, float]
) -> float:
    """
    Computes the utility of a coalition with a given guardian set.

    v(s, l_s) = Σ(c_i * T_i for i in coalition)
                - Σ(β_i * ρ_i for i in guardians)
                + Σ(K_i for i in guardians)

    The allocation of traffic among guardians uses uniform-until-saturation.

    Args:
        coalition: List of operator indices in the coalition
        guardians: List of operator indices serving as guardians
        operators: List of all operator parameters
        traffic_at_t: Dictionary mapping operator index to traffic at current time

    Returns:
        The coalition's utility value.
    """
    # Total revenue from all coalition members
    total_revenue = sum(
        operators[i].c * traffic_at_t[i]
        for i in coalition
    )

    # Total traffic to allocate
    total_traffic = sum(traffic_at_t[i] for i in coalition)

    # Get capacities for allocation
    capacities = {i: operators[i].capacity_epsilon for i in guardians}

    # Allocate traffic using uniform-until-saturation
    allocation = allocate_uniform_until_saturation(guardians, capacities, total_traffic)

    # Compute costs for guardians
    total_variable_cost = 0.0
    total_fixed_cost = 0.0

    for g in guardians:
        allocated_traffic = allocation.get(g, 0.0)
        rho_g = min(1.0, allocated_traffic / operators[g].capacity_epsilon)
        total_variable_cost += operators[g].beta * rho_g
        total_fixed_cost += operators[g].K  # K is negative

    return total_revenue - total_variable_cost + total_fixed_cost


def coalition_value_star(
    coalition: list[int],
    operators: list[OperatorParams],
    traffic_at_t: dict[int, float]
) -> tuple[float, list[int], dict[int, float]]:
    """
    Computes the optimal coalition value v*(s) by finding the best guardian set.

    Enumerates all non-empty subsets of the coalition as candidate guardian sets,
    checks capacity feasibility, and returns the configuration with maximum utility.

    Args:
        coalition: List of operator indices in the coalition
        operators: List of all operator parameters
        traffic_at_t: Dictionary mapping operator index to traffic at current time

    Returns:
        Tuple of:
        - v_star: The maximum coalition value
        - optimal_guardians: The best guardian set
        - optimal_allocation: The traffic allocation for optimal guardians
    """
    if not coalition:
        return 0.0, [], {}

    total_traffic = sum(traffic_at_t[i] for i in coalition)

    best_value = float('-inf')
    best_guardians: list[int] = []
    best_allocation: dict[int, float] = {}

    # Enumerate all non-empty subsets of coalition as candidate guardian sets
    for r in range(1, len(coalition) + 1):
        for guardian_combo in combinations(coalition, r):
            guardians = list(guardian_combo)

            # Check capacity feasibility
            total_capacity = sum(operators[g].capacity_epsilon for g in guardians)
            if total_capacity < total_traffic - 1e-9:
                continue  # Infeasible

            # Compute allocation and utility
            capacities = {g: operators[g].capacity_epsilon for g in guardians}
            try:
                allocation = allocate_uniform_until_saturation(
                    guardians, capacities, total_traffic
                )
            except ValueError:
                continue

            value = coalition_utility(coalition, guardians, operators, traffic_at_t)

            if value > best_value:
                best_value = value
                best_guardians = guardians
                best_allocation = allocation

    return best_value, best_guardians, best_allocation
