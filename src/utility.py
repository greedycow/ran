def single_operator_utility(c: float, T: float, beta: float, rho: float, K: float) -> float:
    """
    Computes the utility (profit) of a single operator operating alone.

    The utility is: v(A_i) = c * T - beta * rho + K

    Where:
    - c * T: Revenue from selling traffic
    - beta * rho: Variable cost related to load
    - K: Fixed costs (usually negative)

    Args:
        c: Revenue per unit of traffic
        T: Traffic volume
        beta: Variable cost coefficient
        rho: Load factor (0 to 1)
        K: Fixed costs

    Returns:
        The operator's utility value.
    """
    return c * T - beta * rho + K

