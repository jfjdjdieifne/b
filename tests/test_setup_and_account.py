from setup_policy import setup_expiry
from paper_account import PaperAccount


def test_setup_expiry_is_finite():
    created = 1_783_659_247_000
    policy = setup_expiry(created, "MODEL_C_BOS_PULLBACK", "5m")
    assert policy["expires_at_ms"] > created
    assert policy["expires_at_ms"] - created <= 72 * 5 * 60 * 1000


def test_paper_account_scenario_preserves_original(tmp_path):
    account = PaperAccount(str(tmp_path / "account.json"), 100)
    trade = {
        "id": "T-1", "symbol": "ETH/USDT", "exchange": "binance", "timeframe": "5m",
        "model": "MODEL_B", "side": "BUY_LIMIT", "entry": 100,
        "initial_stop_loss": 95, "tp1": 110, "tp2": 120, "risk_usd": 1,
    }
    account.register_plan(trade, {"audit_id": "A-1", "candidate": {"basis": "test", "conditions": []}})
    journal_before = account.journal_with_scenarios()[0]
    scenario = account.set_scenario("T-1", capital=500, risk_pct=2)
    journal_after = account.journal_with_scenarios()[0]
    assert scenario["capital"] == 500
    assert journal_after["planned_entry"] == journal_before["planned_entry"] == 100
