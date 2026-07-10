from risk_manager import RiskManager


def test_structured_targets_are_supported():
    result = RiskManager(balance=100).evaluate({
        "signal": "BUY_LIMIT", "confidence": 80,
        "entry": 100, "stop_loss": 95,
        "tp1": {"price": 108, "kind": "UNSWEPT_SWING_HIGH"},
        "tp2": {"mode": "OPEN_TRAILING"},
    })
    assert result["approved"] is True
    assert result["tp1"] == 108
    assert result["tp2"] is None
    assert result["risk_reward"] == "1:1.6"
