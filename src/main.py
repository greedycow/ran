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

Two simulation modes:
- Oracle mode: Full knowledge of traffic at each time step (upper bound on performance)
- Online mode: Predict traffic using historical data (realistic scenario)
"""

from itertools import permutations, combinations
from typing import Any, Callable, Optional
from math import factorial, sqrt

from utility import single_operator_utility
from generate_data import OperatorParams, get_example_operators, get_example_traffic
from optimiser import coalition_value_star
from profit import shapley_values, payoff_rule1, payoff_rule2, payoff_rule3
from predict import predict_traffic


def simulate_one_hour_oracle(
    operators: list[OperatorParams],
    traffic: dict[int, list[float]],
    coalition: Optional[list[int]] = None
) -> dict[str, Any]:
    """
    Oracle mode simulation: full knowledge of traffic at each time step.

    This is the "god's eye view" where we know the exact traffic at time t
    when making decisions at time t. Used as an upper bound for comparison.

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
        'mode': 'oracle',
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


def simulate_one_hour_online(
    operators: list[OperatorParams],
    traffic: dict[int, list[float]],
    coalition: Optional[list[int]] = None,
    window_size: int = 5,
    safety_margin: float = 0.15
) -> dict[str, Any]:
    """
    Online mode simulation: predict traffic using historical data (0..t-1).

    This is the realistic scenario where we don't know the exact traffic at time t.
    Instead, we use a moving average of past observations to predict future traffic,
    then make decisions based on the prediction.

    To avoid capacity failures (losing traffic is more severe than suboptimal profit),
    predicted traffic is inflated by `safety_margin` before guardian selection.

    At each time step t:
    1. Use history (0..t-1) to predict traffic at t
    2. Inflate prediction by safety_margin for guardian selection
    3. Select guardians based on inflated traffic
    4. Compute actual coalition value using real traffic

    Args:
        operators: List of all operator parameters
        traffic: Dictionary mapping operator index to traffic time series
        coalition: Coalition to simulate (default: all operators)
        window_size: Number of past observations for moving average prediction
        safety_margin: Fraction to inflate predicted traffic for guardian selection (default 0.15 = 15%)

    Returns:
        Dictionary containing:
        - 'time_steps': Number of time steps
        - 'coalition': The coalition being simulated
        - 'v_star': Time series of coalition values (actual, based on decisions)
        - 'guardians': Time series of guardian sets (chosen based on prediction)
        - 'predicted_traffic': Predicted traffic at each time step
        - 'actual_traffic': Actual traffic at each time step
        - 'prediction_errors': Per-operator prediction errors
        - 'payoffs_rule1/2/3': Per-operator time series under each rule
    """
    if coalition is None:
        coalition = list(range(len(operators)))

    num_steps = len(next(iter(traffic.values())))
    num_operators = len(operators)

    # Initialize result structure
    result: dict[str, Any] = {
        'mode': 'online',
        'time_steps': num_steps,
        'coalition': coalition,
        'window_size': window_size,
        'safety_margin': safety_margin,
        'v_star': [],
        'guardians': [],
        'predicted_traffic': [],
        'actual_traffic': [],
        'prediction_errors': {i: [] for i in range(num_operators)},
        'capacity_failures': [],  # Time steps where chosen guardians couldn't handle actual traffic
        'payoffs_rule1': {i: [] for i in coalition},
        'payoffs_rule2': {i: [] for i in coalition},
        'payoffs_rule3': {i: [] for i in coalition},
    }

    # Build history incrementally
    history: dict[int, list[float]] = {i: [] for i in range(num_operators)}

    # Simulate each time step
    for t in range(num_steps):
        # Actual traffic at this time step
        actual_at_t = {i: traffic[i][t] for i in range(num_operators)}
        result['actual_traffic'].append(actual_at_t)

        # Predict traffic based on history (0..t-1)
        if t == 0:
            # No history, use actual traffic for first step (cold start)
            predicted_at_t = actual_at_t.copy()
        else:
            predicted_at_t = predict_traffic(history, window_size)

        result['predicted_traffic'].append(predicted_at_t)

        # Record prediction errors
        for i in range(num_operators):
            error = predicted_at_t[i] - actual_at_t[i]
            result['prediction_errors'][i].append(error)

        # Inflate predicted traffic by safety margin for guardian selection
        margined_traffic = {
            i: predicted_at_t[i] * (1.0 + safety_margin)
            for i in predicted_at_t
        }

        # Make decision based on MARGINED predicted traffic
        _, guardians_t, _ = coalition_value_star(
            coalition, operators, margined_traffic
        )
        result['guardians'].append(guardians_t)

        # But compute actual value using REAL traffic with chosen guardians
        # This represents what actually happens when we apply the decision
        from optimiser import coalition_utility
        from allocate import allocate_uniform_until_saturation

        # Check if guardians can handle actual traffic
        total_actual_traffic = sum(actual_at_t[i] for i in coalition)
        guardian_capacity = sum(operators[g].capacity_epsilon for g in guardians_t)

        if guardian_capacity >= total_actual_traffic - 1e-9:
            # Guardians can handle the actual traffic
            actual_v_star = coalition_utility(coalition, guardians_t, operators, actual_at_t)
            # Compute actual allocation for payoff calculation
            capacities = {g: operators[g].capacity_epsilon for g in guardians_t}
            actual_allocation = allocate_uniform_until_saturation(
                guardians_t, capacities, total_actual_traffic
            )
        else:
            # CAPACITY FAILURE: Guardians can't handle actual traffic!
            # In reality, this means service degradation - we can only serve up to capacity
            # Revenue is reduced proportionally to the traffic we can actually serve
            result['capacity_failures'].append({
                't': t,
                'needed': total_actual_traffic,
                'available': guardian_capacity,
                'shortfall': total_actual_traffic - guardian_capacity,
            })
            
            # Compute degraded value: scale revenue by served fraction, keep full costs
            served_fraction = guardian_capacity / total_actual_traffic
            
            # Revenue only for traffic we can serve
            degraded_revenue = sum(
                operators[i].c * actual_at_t[i] * served_fraction
                for i in coalition
            )
            
            # Guardians are fully loaded (rho = 1.0 for all)
            total_variable_cost = sum(operators[g].beta * 1.0 for g in guardians_t)
            total_fixed_cost = sum(operators[g].K for g in guardians_t)
            
            actual_v_star = degraded_revenue - total_variable_cost + total_fixed_cost
            
            # Allocation is at full capacity for each guardian
            actual_allocation = {g: operators[g].capacity_epsilon for g in guardians_t}

        result['v_star'].append(actual_v_star)

        # Compute payoffs using ACTUAL v_star, guardians, and allocation
        def v_star_for_t(s: list[int]) -> float:
            if not s:
                return 0.0
            val, _, _ = coalition_value_star(s, operators, actual_at_t)
            return val

        # Pass actual values to payoff functions
        payoffs1 = payoff_rule1(
            coalition, v_star_for_t, operators, actual_at_t,
            actual_v_star=actual_v_star,
            actual_guardians=guardians_t,
            actual_allocation=actual_allocation
        )
        payoffs2 = payoff_rule2(
            coalition, operators, actual_at_t,
            actual_v_star=actual_v_star,
            actual_guardians=guardians_t
        )
        payoffs3 = payoff_rule3(
            coalition, operators, actual_at_t,
            actual_v_star=actual_v_star
        )

        for i in coalition:
            result['payoffs_rule1'][i].append(payoffs1.get(i, 0.0))
            result['payoffs_rule2'][i].append(payoffs2.get(i, 0.0))
            result['payoffs_rule3'][i].append(payoffs3.get(i, 0.0))

        # Update history for next iteration
        for i in range(num_operators):
            history[i].append(traffic[i][t])

    return result


def compare_oracle_vs_online(
    oracle_result: dict[str, Any],
    online_result: dict[str, Any]
) -> dict[str, Any]:
    """
    Compare oracle mode vs online mode results.

    Args:
        oracle_result: Result from simulate_one_hour_oracle
        online_result: Result from simulate_one_hour_online

    Returns:
        Dictionary containing:
        - 'guardian_agreement': Fraction of time steps with same guardian selection
        - 'value_loss_total': Total value loss (oracle - online)
        - 'value_loss_percent': Value loss as percentage
        - 'prediction_rmse': Root mean square error of traffic prediction
        - 'capacity_failure_count': Number of time steps with capacity failures
        - 'capacity_failures': List of capacity failure details
    """
    num_steps = oracle_result['time_steps']
    num_operators = len(online_result['prediction_errors'])

    # Guardian agreement rate
    agreements = 0
    for t in range(num_steps):
        oracle_guardians = set(oracle_result['guardians'][t])
        online_guardians = set(online_result['guardians'][t])
        if oracle_guardians == online_guardians:
            agreements += 1
    guardian_agreement = agreements / num_steps

    # Value comparison
    oracle_total = sum(oracle_result['v_star'])
    online_total = sum(online_result['v_star'])
    value_loss_total = oracle_total - online_total
    value_loss_percent = (value_loss_total / oracle_total * 100) if oracle_total > 0 else 0.0

    # Prediction RMSE
    total_squared_error = 0.0
    total_count = 0
    for i in range(num_operators):
        for error in online_result['prediction_errors'][i]:
            total_squared_error += error ** 2
            total_count += 1
    prediction_rmse = sqrt(total_squared_error / total_count) if total_count > 0 else 0.0

    # Capacity failures
    capacity_failures = online_result.get('capacity_failures', [])
    capacity_failure_count = len(capacity_failures)

    return {
        'guardian_agreement': guardian_agreement,
        'value_loss_total': value_loss_total,
        'value_loss_percent': value_loss_percent,
        'prediction_rmse': prediction_rmse,
        'oracle_total_value': oracle_total,
        'online_total_value': online_total,
        'capacity_failure_count': capacity_failure_count,
        'capacity_failures': capacity_failures,
    }


# Example usage
if __name__ == "__main__":
    # Get example data
    ops = get_example_operators()
    traffic_data = get_example_traffic()
    num_operators = len(ops)

    # Create a list of all operator indices (0 to num_operators-1)
    # Used to specify the operators participating in the RAN sharing coalition.
    # For example, if num_operators is 4, then coalition = [0, 1, 2, 3]
    coalition = list(range(num_operators))

    print("=" * 60)
    print("RAN Sharing Cooperative Game Simulation")
    print("=" * 60)

    # Display operator parameters
    print("\nOperator Parameters:")
    for i, op in enumerate(ops):
        print(f"  {op.name}: ε={op.capacity_epsilon}, c={op.c}, "
              f"β={op.beta}, K={op.K}")

    print("\nTraffic at t=0, t=30, t=59:")
    for i, t_list in traffic_data.items():
        print(f"  Operator {i}: T(0)={t_list[0]:.2f}, T(30)={t_list[30]:.2f}, T(59)={t_list[59]:.2f}")

    # Run both simulation modes
    print("\n" + "=" * 60)
    print("Running Oracle Mode (god's eye view)...")
    print("=" * 60)
    oracle_result = simulate_one_hour_oracle(ops, traffic_data, coalition)

    safety_margin = 0.15
    print("\n" + "=" * 60)
    print(f"Running Online Mode (prediction-based, {safety_margin:.0%} safety margin)...")
    print("=" * 60)
    online_result = simulate_one_hour_online(
        ops, traffic_data, coalition, window_size=5, safety_margin=safety_margin
    )

    # Compare results
    print("\n" + "=" * 60)
    print("Comparison: Oracle vs Online")
    print("=" * 60)
    comparison = compare_oracle_vs_online(oracle_result, online_result)

    print(f"\n  Safety Margin:           {safety_margin:.0%}")
    print(f"  Guardian Agreement Rate: {comparison['guardian_agreement']:.1%}")
    print(f"  Oracle Total Value:      {comparison['oracle_total_value']:.2f}")
    print(f"  Online Total Value:      {comparison['online_total_value']:.2f}")
    print(f"  Value Loss:              {comparison['value_loss_total']:.2f} ({comparison['value_loss_percent']:.2f}%)")
    print(f"  Prediction RMSE:         {comparison['prediction_rmse']:.4f}")
    print(f"  Capacity Failures:       {comparison['capacity_failure_count']} time steps")
    
    # Show capacity failure details if any
    if comparison['capacity_failures']:
        print("\n" + "-" * 60)
        print("Capacity Failures (prediction underestimated traffic)")
        print("-" * 60)
        for failure in comparison['capacity_failures']:
            print(f"  t={failure['t']:2d}: needed {failure['needed']:.2f}, "
                  f"available {failure['available']:.2f}, "
                  f"shortfall {failure['shortfall']:.2f}")

    # Show detailed comparison for selected time steps
    print("\n" + "-" * 60)
    print("Detailed Comparison (selected time steps)")
    print("-" * 60)
    print(f"{'t':>3} | {'Oracle Guardians':<18} | {'Online Guardians':<18} | {'Match':<5} | {'Oracle v*':>10} | {'Online v*':>10}")
    print("-" * 80)

    for t in [0, 10, 20, 30, 40, 50, 59]:
        oracle_g = oracle_result['guardians'][t]
        online_g = online_result['guardians'][t]
        match = "✓" if set(oracle_g) == set(online_g) else "✗"
        oracle_v = oracle_result['v_star'][t]
        online_v = online_result['v_star'][t]
        print(f"{t:>3} | {str(oracle_g):<18} | {str(online_g):<18} | {match:^5} | {oracle_v:>10.2f} | {online_v:>10.2f}")

    # Show prediction errors
    print("\n" + "-" * 60)
    print("Prediction Errors (selected time steps)")
    print("-" * 60)
    print(f"{'t':>3} | ", end="")
    for i in range(num_operators):
        print(f"{'Op'+str(i)+' Pred':>10} {'Actual':>10} {'Error':>8} | ", end="")
    print()

    for t in [5, 15, 30, 45]:
        print(f"{t:>3} | ", end="")
        for i in range(num_operators):
            pred = online_result['predicted_traffic'][t][i]
            actual = online_result['actual_traffic'][t][i]
            error = online_result['prediction_errors'][i][t]
            print(f"{pred:>10.2f} {actual:>10.2f} {error:>+8.2f} | ", end="")
        print()

    # Compute non-cooperative standalone profits (each operator alone, all 60 steps)
    standalone_profits: dict[int, float] = {}
    for i in coalition:
        total = 0.0
        for t in range(len(traffic_data[0])):
            T_i = traffic_data[i][t]
            rho_i = min(1.0, T_i / ops[i].capacity_epsilon)
            total += single_operator_utility(ops[i].c, T_i, ops[i].beta, rho_i, ops[i].K)
        standalone_profits[i] = total
    standalone_total = sum(standalone_profits.values())

    # Show per-operator total profit
    print("\n" + "=" * 60)
    print("Per-Operator Total Profit (summed over 60 time steps)")
    print("=" * 60)

    print("\n--- Non-Cooperative (each operator alone) ---")
    print(f"{'Operator':<12} | {'Standalone':>12}")
    print("-" * 28)
    for i in coalition:
        print(f"{ops[i].name:<12} | {standalone_profits[i]:>12.2f}")
    print("-" * 28)
    print(f"{'Total':<12} | {standalone_total:>12.2f}")

    print("\n--- Oracle Mode ---")
    print(f"{'Operator':<12} | {'Rule 1':>12} | {'Rule 2':>12} | {'Rule 3':>12} | {'vs Alone':>12}")
    print("-" * 70)
    for i in coalition:
        r1 = sum(oracle_result['payoffs_rule1'][i])
        r2 = sum(oracle_result['payoffs_rule2'][i])
        r3 = sum(oracle_result['payoffs_rule3'][i])
        gain = r1 - standalone_profits[i]
        print(f"{ops[i].name:<12} | {r1:>12.2f} | {r2:>12.2f} | {r3:>12.2f} | {gain:>+12.2f}")
    print("-" * 70)
    total_r1 = sum(sum(oracle_result['payoffs_rule1'][i]) for i in coalition)
    total_r2 = sum(sum(oracle_result['payoffs_rule2'][i]) for i in coalition)
    total_r3 = sum(sum(oracle_result['payoffs_rule3'][i]) for i in coalition)
    print(f"{'Total':<12} | {total_r1:>12.2f} | {total_r2:>12.2f} | {total_r3:>12.2f} | {total_r1 - standalone_total:>+12.2f}")

    print("\n--- Online Mode ---")
    print(f"{'Operator':<12} | {'Rule 1':>12} | {'Rule 2':>12} | {'Rule 3':>12} | {'vs Alone':>12}")
    print("-" * 70)
    for i in coalition:
        r1 = sum(online_result['payoffs_rule1'][i])
        r2 = sum(online_result['payoffs_rule2'][i])
        r3 = sum(online_result['payoffs_rule3'][i])
        gain = r1 - standalone_profits[i]
        print(f"{ops[i].name:<12} | {r1:>12.2f} | {r2:>12.2f} | {r3:>12.2f} | {gain:>+12.2f}")
    print("-" * 70)
    total_r1 = sum(sum(online_result['payoffs_rule1'][i]) for i in coalition)
    total_r2 = sum(sum(online_result['payoffs_rule2'][i]) for i in coalition)
    total_r3 = sum(sum(online_result['payoffs_rule3'][i]) for i in coalition)
    print(f"{'Total':<12} | {total_r1:>12.2f} | {total_r2:>12.2f} | {total_r3:>12.2f} | {total_r1 - standalone_total:>+12.2f}")
