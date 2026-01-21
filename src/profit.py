from typing import Callable, Optional
from math import factorial
from itertools import permutations, combinations
from generate_data import OperatorParams
from optimiser import coalition_value_star, coalition_utility
from utility import single_operator_utility


def shapley_values(
    players: list[int],
    value_function: Callable[[list[int]], float]
) -> dict[int, float]:
    """
    Computes Shapley values by enumerating all permutations of players.

    The Shapley value for player i is the average marginal contribution
    when i joins a coalition, averaged over all possible orderings.

    φ_i = (1/N!) * Σ [v(S ∪ {i}) - v(S)]

    where S is the set of players appearing before i in each permutation.

    Args:
        players: List of player indices
        value_function: Function that takes a list of players and returns coalition value

    Returns:
        Dictionary mapping player index to their Shapley value.
    """
    n = len(players)
    if n == 0:
        return {}

    shapley: dict[int, float] = {p: 0.0 for p in players}

    # Enumerate all permutations
    for perm in permutations(players):
        current_coalition: list[int] = []
        current_value = 0.0

        for player in perm:
            # Value of coalition including this player
            new_coalition = current_coalition + [player]
            new_value = value_function(new_coalition)

            # Marginal contribution
            marginal = new_value - current_value
            shapley[player] += marginal

            current_coalition = new_coalition
            current_value = new_value

    # Average over all permutations
    num_perms = factorial(n)
    for p in players:
        shapley[p] /= num_perms

    return shapley


def payoff_rule1(
    coalition: list[int],
    v_star: Callable[[list[int]], float],
    operators: list[OperatorParams],
    traffic_at_t: dict[int, float],
    actual_v_star: Optional[float] = None,
    actual_guardians: Optional[list[int]] = None,
    actual_allocation: Optional[dict[int, float]] = None
) -> dict[int, float]:
    """
    Gain-sharing rule 1: Equalized costs plus Shapley-based revenues.

    Steps:
    1. Compute guardian costs and average cost share D_s
    2. Use Shapley values to allocate revenue proportionally
    3. Final payoff: g1_i = revenue_share_i - D_s

    This ensures all coalition members share costs equally while revenues
    are distributed based on marginal contributions.

    Args:
        coalition: List of operator indices in the coalition
        v_star: Function computing v*(s) for any coalition s
        operators: List of all operator parameters
        traffic_at_t: Dictionary mapping operator index to traffic at current time
        actual_v_star: Actual coalition value (if None, compute from v_star function)
        actual_guardians: Actual guardians used (if None, compute optimal)
        actual_allocation: Actual traffic allocation (if None, compute optimal)

    Returns:
        Dictionary mapping operator index to their payoff under rule 1.
    """
    if not coalition:
        return {}

    # Get configuration - use actual if provided, otherwise compute optimal
    if actual_v_star is not None and actual_guardians is not None and actual_allocation is not None:
        v_star_coalition = actual_v_star
        guardians = actual_guardians
        allocation = actual_allocation
    else:
        v_star_coalition, guardians, allocation = coalition_value_star(
            coalition, operators, traffic_at_t
        )

    if abs(v_star_coalition) < 1e-9:
        # Avoid division by zero
        return {i: 0.0 for i in coalition}

    # Compute individual guardian costs D_i
    guardian_costs: dict[int, float] = {}
    for g in guardians:
        allocated_traffic = allocation.get(g, 0.0)
        rho_g = min(1.0, allocated_traffic / operators[g].capacity_epsilon)
        # D_i = beta_i * rho_i - K_i (note: K is negative, so -K is positive)
        guardian_costs[g] = operators[g].beta * rho_g - operators[g].K

    # Average cost share
    total_cost = sum(guardian_costs.values())
    D_s = total_cost / len(coalition)

    # Compute Shapley values (still use the v_star function for marginal contributions)
    phi = shapley_values(coalition, v_star)

    # Total coalition revenue
    R_s = sum(operators[i].c * traffic_at_t[i] for i in coalition)

    # Sum of Shapley values for normalization
    phi_sum = sum(phi.values())
    if abs(phi_sum) < 1e-9:
        phi_sum = 1.0  # Avoid division by zero

    # Allocate revenue proportionally to Shapley values, scaled to actual v_star
    payoffs: dict[int, float] = {}
    for i in coalition:
        # Revenue share based on Shapley proportion, but total scaled to actual v_star + costs
        revenue_share_i = (phi[i] / phi_sum) * (v_star_coalition + len(coalition) * D_s)
        payoffs[i] = revenue_share_i - D_s

    return payoffs


def payoff_rule2(
    coalition: list[int],
    operators: list[OperatorParams],
    traffic_at_t: dict[int, float],
    actual_v_star: Optional[float] = None,
    actual_guardians: Optional[list[int]] = None
) -> dict[int, float]:
    """
    Gain-sharing rule 2: Guard vs non-guard interpolated Shapley.

    For each player:
    1. Compute ordinary Shapley value φ_i (can be guardian)
    2. Compute modified Shapley value ψ_i (forbidden from being guardian)
    3. Interpolate: h_i = ρ_i * φ_i + (1 - ρ_i) * ψ_i
    4. Normalize for efficiency: g2_i = h_i * v*(coalition) / Σh_j

    Args:
        coalition: List of operator indices in the coalition
        operators: List of all operator parameters
        traffic_at_t: Dictionary mapping operator index to traffic at current time
        actual_v_star: Actual coalition value (if None, compute optimal)
        actual_guardians: Actual guardians used (affects rho calculation)

    Returns:
        Dictionary mapping operator index to their payoff under rule 2.
    """
    if not coalition:
        return {}

    # Standard v_star function for Shapley computation
    def v_star_standard(s: list[int]) -> float:
        if not s:
            return 0.0
        val, _, _ = coalition_value_star(s, operators, traffic_at_t)
        return val

    # Use actual v_star if provided, otherwise compute optimal
    if actual_v_star is not None:
        v_star_coalition = actual_v_star
    else:
        v_star_coalition = v_star_standard(coalition)

    # Compute ordinary Shapley values
    phi = shapley_values(coalition, v_star_standard)

    # For each player, compute modified Shapley value (player forbidden as guardian)
    psi: dict[int, float] = {}

    for player in coalition:
        # Define v_star_without_guard_i: player i cannot be in guardian set
        def v_star_without_guard(s: list[int], excluded: int = player) -> float:
            if not s:
                return 0.0

            total_traffic = sum(traffic_at_t[i] for i in s)

            best_value = float('-inf')
            candidates = [i for i in s if i != excluded]

            if not candidates:
                # No valid guardians, compute individual value if excluded is alone
                if len(s) == 1 and s[0] == excluded:
                    # Single player who can't be guardian - return 0 or individual value
                    return 0.0
                return float('-inf')

            # Enumerate all non-empty subsets of candidates (excluding 'excluded')
            for r in range(1, len(candidates) + 1):
                for guardian_combo in combinations(candidates, r):
                    guardians = list(guardian_combo)
                    total_capacity = sum(operators[g].capacity_epsilon for g in guardians)

                    if total_capacity < total_traffic - 1e-9:
                        continue

                    value = coalition_utility(s, guardians, operators, traffic_at_t)
                    if value > best_value:
                        best_value = value

            return best_value if best_value > float('-inf') else 0.0

        psi[player] = shapley_values(coalition, v_star_without_guard).get(player, 0.0)

    # Compute load for each player - use actual guardians if provided
    rho: dict[int, float] = {}
    for i in coalition:
        if actual_guardians is not None and i in actual_guardians:
            # If this operator is actually serving as guardian, use higher load
            rho[i] = min(1.0, traffic_at_t[i] / operators[i].capacity_epsilon)
        else:
            rho[i] = min(1.0, traffic_at_t[i] / operators[i].capacity_epsilon)

    # Preliminary payoff
    h: dict[int, float] = {}
    for i in coalition:
        h[i] = rho[i] * phi[i] + (1 - rho[i]) * psi[i]

    # Normalize for efficiency - use actual v_star
    h_sum = sum(h.values())
    if abs(h_sum) < 1e-9:
        # Avoid division by zero
        return {i: v_star_coalition / len(coalition) for i in coalition}

    payoffs: dict[int, float] = {}
    for i in coalition:
        payoffs[i] = h[i] * v_star_coalition / h_sum

    return payoffs


def payoff_rule3(
    coalition: list[int],
    operators: list[OperatorParams],
    traffic_at_t: dict[int, float],
    actual_v_star: Optional[float] = None
) -> dict[int, float]:
    """
    Gain-sharing rule 3: Proportional to standalone utility.

    Each player receives a share proportional to their standalone utility:
    g3_i = v(A_i) * v*(coalition) / Σv(A_j)

    This is the simplest rule but doesn't account for strategic contributions.

    Args:
        coalition: List of operator indices in the coalition
        operators: List of all operator parameters
        traffic_at_t: Dictionary mapping operator index to traffic at current time
        actual_v_star: Actual coalition value (if None, compute optimal)

    Returns:
        Dictionary mapping operator index to their payoff under rule 3.
    """
    if not coalition:
        return {}

    # Compute standalone utilities
    standalone: dict[int, float] = {}
    for i in coalition:
        T_i = traffic_at_t[i]
        rho_i = min(1.0, T_i / operators[i].capacity_epsilon)
        standalone[i] = single_operator_utility(
            operators[i].c, T_i, operators[i].beta, rho_i, operators[i].K
        )

    # Total standalone utility
    V_total = sum(standalone.values())

    # Use actual v_star if provided, otherwise compute optimal
    if actual_v_star is not None:
        v_star_coalition = actual_v_star
    else:
        v_star_coalition, _, _ = coalition_value_star(coalition, operators, traffic_at_t)

    if abs(V_total) < 1e-9:
        # Avoid division by zero - equal split
        return {i: v_star_coalition / len(coalition) for i in coalition}

    # Proportional allocation
    payoffs: dict[int, float] = {}
    for i in coalition:
        payoffs[i] = standalone[i] * v_star_coalition / V_total

    return payoffs
