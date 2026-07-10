from data_manager import DataManager
from market_agent import MarketAgent
from paper_account import PaperAccount
from trade_monitor import TradeMonitor


def test_same_thesis_cannot_rearm_every_five_minutes(tmp_path):
    dm = DataManager()
    monitor = TradeMonitor(dm, str(tmp_path / "trades.json"))
    paper = PaperAccount(str(tmp_path / "paper.json"), 100)
    agent = MarketAgent(dm, monitor, paper, str(tmp_path / "agent.json"))
    trade = {
        "id": "T-old", "symbol": "ETH/USDT", "model": "MODEL_C_BOS_PULLBACK",
        "entry": 1750.0, "initial_stop_loss": 1740.0,
    }
    agent._record_tombstone(trade, "target reached without entry")
    same = {"model": "MODEL_C_BOS_PULLBACK", "entry": 1750.2, "stop_loss": 1740.1}
    assert agent._can_rearm("ETH/USDT", same) is False
