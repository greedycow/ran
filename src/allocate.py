def allocate_uniform_until_saturation(
    guardians: list[int],
    capacities: dict[int, float],
    total_traffic: float
) -> dict[int, float]:
    """
    Allocates traffic to guardians using the uniform-until-saturation rule.

    This rule finds a threshold λ such that each guardian receives min(ε_i, λ),
    and the sum equals the total traffic. Smaller capacity guardians may become
    saturated while larger ones share the remaining load equally.

    Algorithm (water-filling style):
    1. Sort guardians by capacity (ascending)
    2. Progressively saturate smallest capacities
    3. Find the λ interval that satisfies the equation

    Args:
        guardians: List of guardian operator indices
        capacities: Dictionary mapping operator index to their capacity
        total_traffic: Total traffic to allocate

    Returns:
        Dictionary mapping guardian index to allocated traffic.

    Raises:
        ValueError: If total capacity is insufficient for the traffic.
    """
    if not guardians:
        if total_traffic > 0:
            raise ValueError("No guardians available to handle traffic")
        return {}

    # Get capacities for guardians and check feasibility
    guardian_caps = [(g, capacities[g]) for g in guardians]
    total_capacity = sum(cap for _, cap in guardian_caps)

    if total_capacity < total_traffic - 1e-9:
        raise ValueError(
            f"Insufficient capacity: {total_capacity:.2f} < {total_traffic:.2f}"
        )

    # Sort guardians by capacity (ascending)
    guardian_caps.sort(key=lambda x: x[1])

    allocation: dict[int, float] = {}
    remaining_traffic = total_traffic
    remaining_guardians = list(guardian_caps)

    while remaining_guardians:
        n_remaining = len(remaining_guardians)
        # Try to distribute remaining traffic equally
        lambda_candidate = remaining_traffic / n_remaining

        # Check if the smallest guardian can handle lambda_candidate
        smallest_guardian, smallest_cap = remaining_guardians[0]

        if smallest_cap <= lambda_candidate:
            # Saturate the smallest guardian
            allocation[smallest_guardian] = smallest_cap
            remaining_traffic -= smallest_cap
            remaining_guardians.pop(0)
        else:
            # All remaining guardians can handle lambda_candidate
            for g, _ in remaining_guardians:
                allocation[g] = lambda_candidate
            break

    return allocation