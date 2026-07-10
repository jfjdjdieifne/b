from ict_math_engine import find_tp_targets


def test_tp1_uses_nearest_real_level_without_forcing_three_r():
    n = 30
    highs = [100 + i * 0.1 for i in range(n)]
    highs[10] = 110.0
    for i in range(11, n):
        highs[i] = 105 + (i - 11) * 0.1  # stays below old unswept 110
    lows = [h - 2 for h in highs]
    opens = [h - 1.2 for h in highs]
    closes = [h - 1 for h in highs]
    data = {
        "opens": opens, "highs": highs, "lows": lows, "closes": closes,
        "volumes": [1] * n, "timestamps": list(range(n)), "count": n,
    }
    result = find_tp_targets(data, entry_price=100, sl_price=95, is_long=True, lookback=30)
    assert result["tp1"] is not None
    assert result["tp1"]["level_price"] == 110.0
    assert result["tp1"]["rr"] < 3.0
