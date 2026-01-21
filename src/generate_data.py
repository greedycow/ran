from dataclasses import dataclass


@dataclass
class OperatorParams:
    """
    Parameters for a single mobile network operator.

    Attributes:
        name: Identifier for the operator
        capacity_epsilon: Maximum traffic capacity (ε_i)
        c: Revenue per unit of traffic
        beta: Variable cost coefficient related to load (β_i)
        K: Fixed costs (typically negative)
    """
    name: str
    capacity_epsilon: float
    c: float
    beta: float
    K: float

def get_example_operators() -> list[OperatorParams]:
    """
    Returns a list of 4 example operators with predefined parameters.

    Returns:
        List of 4 OperatorParams representing different mobile operators.
    """
    return [
        OperatorParams(name="Operator1", capacity_epsilon=100.0, c=1.0, beta=0.3, K=-10.0),
        OperatorParams(name="Operator2", capacity_epsilon=80.0, c=1.0, beta=0.35, K=-12.0),
        OperatorParams(name="Operator3", capacity_epsilon=60.0, c=1.1, beta=0.25, K=-9.0),
        OperatorParams(name="Operator4", capacity_epsilon=70.0, c=0.95, beta=0.28, K=-11.0),
    ]


def get_example_traffic(num_steps: int = 60) -> dict[int, list[float]]:
    """
    Returns example traffic profiles for operators over a one-hour horizon.

    Traffic varies significantly over time to trigger different guardian configurations:
    - Phase 1 (t=0-15): Low traffic (~70) - single guardian may suffice
    - Phase 2 (t=15-30): Rising traffic, peak at ~180 - need multiple guardians
    - Phase 3 (t=30-45): High traffic (~150) - multiple guardians needed
    - Phase 4 (t=45-60): Declining back to moderate (~100)

    Args:
        num_steps: Number of time steps (default 60 for one hour, one per minute)

    Returns:
        Dictionary mapping operator index (0, 1, 2, 3) to their traffic time series.
    """
    import math

    traffic: dict[int, list[float]] = {0: [], 1: [], 2: [], 3: []}

    for t in range(num_steps):
        # Normalized time in [0, 1]
        t_norm = t / num_steps

        # Base multiplier: creates a wave that goes low -> high -> medium
        # Peak around t=25, trough at t=0 and t=55
        wave = 0.6 + 0.8 * math.sin(math.pi * t_norm) ** 2

        # Operator 1: Main traffic driver, follows the wave
        # Range: ~20 to ~70
        traffic[0].append(20.0 + 50.0 * wave)

        # Operator 2: Peaks earlier than operator 1
        # Range: ~15 to ~55
        early_wave = 0.5 + 0.9 * math.sin(math.pi * (t_norm + 0.1)) ** 2
        traffic[1].append(15.0 + 40.0 * early_wave)

        # Operator 3: Counter-cyclical - high when others are low
        # Range: ~10 to ~40
        counter_wave = 1.0 - 0.6 * math.sin(math.pi * t_norm) ** 2
        traffic[2].append(10.0 + 30.0 * counter_wave)

        # Operator 4: Steady growth throughout the hour
        # Range: ~10 to ~45
        traffic[3].append(10.0 + 35.0 * t_norm + 5.0 * math.sin(2 * math.pi * t_norm))

    return traffic

