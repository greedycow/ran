"""
RAN Sharing Cooperative Game Simulation

This module implements a cooperative game theory model for RAN (Radio Access Network) sharing
among multiple mobile operators. It uses Shapley values and various gain-sharing rules to
determine fair allocation of benefits when operators form coalitions and share infrastructure.

Key concepts:
- Coalition: A group of operators who agree to share their network resources
- Guardian set (l_s): Operators within a coalition who keep their equipment running
- Uniform-until-saturation: An allocation rule that distributes traffic evenly among guardians
- Shapley value: A fair division method based on marginal contributions
"""

from itertools import permutations, combinations
from typing import Any, Callable, Optional
from math import factorial

from utility import single_operator_utility
from generate_data import OperatorParams, get_example_operators, get_example_traffic
from optimiser import coalition_value_star
from profit import shapley_values, payoff_rule1, payoff_rule2, payoff_rule3




def simulate_one_hour(
    operators: list[OperatorParams],
    traffic: dict[int, list[float]],
    coalition: Optional[list[int]] = None
) -> dict[str, Any]:
    """
    Simulates one hour of coalition operation with 60 time steps.

    For each time step, computes:
    - Coalition value v*(s)
    - Payoffs under all three gain-sharing rules

    Args:
        operators: List of all operator parameters
        traffic: Dictionary mapping operator index to traffic time series
        coalition: Coalition to simulate (default: all operators)

    Returns:
        Dictionary containing:
        - 'time_steps': Number of time steps
        - 'coalition': The coalition being simulated
        - 'v_star': Time series of coalition values
        - 'guardians': Time series of optimal guardian sets
        - 'payoffs_rule1': Per-operator time series under rule 1
        - 'payoffs_rule2': Per-operator time series under rule 2
        - 'payoffs_rule3': Per-operator time series under rule 3
    """
    if coalition is None:
        coalition = list(range(len(operators)))

    num_steps = len(next(iter(traffic.values())))

    # Initialize result structure
    result: dict[str, Any] = {
        'time_steps': num_steps,
        'coalition': coalition,
        'v_star': [],
        'guardians': [],
        'payoffs_rule1': {i: [] for i in coalition},
        'payoffs_rule2': {i: [] for i in coalition},
        'payoffs_rule3': {i: [] for i in coalition},
    }

    # Define v_star callable for Shapley computation
    def v_star_func(s: list[int], t: int) -> float:
        if not s:
            return 0.0
        traffic_at_t = {i: traffic[i][t] for i in range(len(operators))}
        val, _, _ = coalition_value_star(s, operators, traffic_at_t)
        return val

    # Simulate each time step
    for t in range(num_steps):
        # Get traffic at this time step
        traffic_at_t = {i: traffic[i][t] for i in range(len(operators))}

        # Compute v*(coalition)
        v_star_t, guardians_t, _ = coalition_value_star(
            coalition, operators, traffic_at_t
        )
        result['v_star'].append(v_star_t)
        result['guardians'].append(guardians_t)

        # Create v_star callable for this time step
        def v_star_for_t(s: list[int], time_step: int = t) -> float:
            return v_star_func(s, time_step)

        # Compute payoffs under each rule
        payoffs1 = payoff_rule1(coalition, v_star_for_t, operators, traffic_at_t)
        payoffs2 = payoff_rule2(coalition, operators, traffic_at_t)
        payoffs3 = payoff_rule3(coalition, operators, traffic_at_t)

        for i in coalition:
            result['payoffs_rule1'][i].append(payoffs1.get(i, 0.0))
            result['payoffs_rule2'][i].append(payoffs2.get(i, 0.0))
            result['payoffs_rule3'][i].append(payoffs3.get(i, 0.0))

    return result


# Example usage
if __name__ == "__main__":
    # Get example data
    ops = get_example_operators()
    traffic_data = get_example_traffic()
    num_operators = len(ops)

    print("=== RAN Sharing Cooperative Game Simulation ===\n")

    # Display operator parameters
    print("Operator Parameters:")
    for i, op in enumerate(ops):
        print(f"  {op.name}: ε={op.capacity_epsilon}, c={op.c}, "
              f"β={op.beta}, K={op.K}")

    print("\nTraffic at t=0, t=30, t=59:")
    for i, t_list in traffic_data.items():
        print(f"  Operator {i}: T(0)={t_list[0]:.2f}, T(30)={t_list[30]:.2f}, T(59)={t_list[59]:.2f}")

    # Compute standalone utilities at t=0
    print("\n--- Standalone Utilities (t=0) ---")
    traffic_t0 = {i: traffic_data[i][0] for i in range(num_operators)}
    for i in range(num_operators):
        T_i = traffic_t0[i]
        rho_i = min(1.0, T_i / ops[i].capacity_epsilon)
        v_i = single_operator_utility(ops[i].c, T_i, ops[i].beta, rho_i, ops[i].K)
        print(f"  v(A_{i}) = {v_i:.4f} (ρ={rho_i:.4f})")

    # Compute grand coalition value
    print("\n--- Grand Coalition (t=0) ---")
    coalition = list(range(num_operators))
    v_star, guardians, allocation = coalition_value_star(coalition, ops, traffic_t0)
    print(f"  v*(grand coalition) = {v_star:.4f}")
    print(f"  Optimal guardians: {guardians}")
    print(f"  Traffic allocation: {dict((k, f'{v:.2f}') for k, v in allocation.items())}")

    # Compute payoffs under each rule
    def v_star_func(s: list[int]) -> float:
        if not s:
            return 0.0
        val, _, _ = coalition_value_star(s, ops, traffic_t0)
        return val

    print("\n--- Shapley Values ---")
    phi = shapley_values(coalition, v_star_func)
    for i in coalition:
        print(f"  φ(A_{i}) = {phi[i]:.4f}")

    print("\n--- Payoff Rule 1 (Equalized costs + Shapley revenues) ---")
    payoffs1 = payoff_rule1(coalition, v_star_func, ops, traffic_t0)
    for i in coalition:
        print(f"  g1(A_{i}) = {payoffs1[i]:.4f}")
    print(f"  Sum = {sum(payoffs1.values()):.4f}")

    print("\n--- Payoff Rule 2 (Guard/non-guard interpolated Shapley) ---")
    payoffs2 = payoff_rule2(coalition, ops, traffic_t0)
    for i in coalition:
        print(f"  g2(A_{i}) = {payoffs2[i]:.4f}")
    print(f"  Sum = {sum(payoffs2.values()):.4f}")

    print("\n--- Payoff Rule 3 (Proportional to standalone) ---")
    payoffs3 = payoff_rule3(coalition, ops, traffic_t0)
    for i in coalition:
        print(f"  g3(A_{i}) = {payoffs3[i]:.4f}")
    print(f"  Sum = {sum(payoffs3.values()):.4f}")

    # Run simulation
    print("\n--- One Hour Simulation (selected time steps) ---")
    sim_result = simulate_one_hour(ops, traffic_data, coalition)
    for t in range(len(sim_result['v_star'])):
        total_traffic = sum(traffic_data[i][t] for i in range(num_operators))
        print(f"  t={t:2d}: v*={sim_result['v_star'][t]:.4f}, "
              f"total_traffic={total_traffic:.2f}, "
              f"guardians={sim_result['guardians'][t]}")
