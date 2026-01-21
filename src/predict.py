"""
Traffic Prediction Module

Provides simple moving average prediction for traffic forecasting.
Used by the online simulation mode to predict future traffic based on historical data.
"""


def predict_traffic(
    history: dict[int, list[float]],
    window_size: int = 5
) -> dict[int, float]:
    """
    Predicts traffic at time t using simple moving average of history (0..t-1).

    For each operator, computes the average of the last `window_size` observations.
    If history length < window_size, uses all available data.

    Args:
        history: Dictionary mapping operator index to their traffic history (0..t-1)
        window_size: Number of recent observations to average (default 5)

    Returns:
        Dictionary mapping operator index to predicted traffic at time t.

    Example:
        >>> history = {0: [10.0, 12.0, 11.0, 13.0, 14.0]}
        >>> predict_traffic(history, window_size=3)
        {0: 12.666...}  # average of [11.0, 13.0, 14.0]
    """
    predictions: dict[int, float] = {}

    for operator_id, traffic_list in history.items():
        if not traffic_list:
            # No history available, predict 0
            predictions[operator_id] = 0.0
        else:
            # Use min(window_size, available_data) for averaging
            effective_window = min(window_size, len(traffic_list))
            recent_traffic = traffic_list[-effective_window:]
            predictions[operator_id] = sum(recent_traffic) / len(recent_traffic)

    return predictions
