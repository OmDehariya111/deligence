import pytest
import json
import sys
from unittest.mock import MagicMock

sys.modules["litellm"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["fastmcp"] = MagicMock()

from config.paths import get_run_paths
from schemas.pydantic_models import MarketIntelContext
from agents.market_intelligence.module7_market_risk import MarketRiskSignalGenerator
from tools.sqlite_tools import DatabaseManager

@pytest.fixture
def mock_context(tmp_path, monkeypatch):
    ticker = "AAPL"
    run_id = f"{ticker}_20260705_120000"
    
    monkeypatch.setattr("config.paths.OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr("config.paths.LOGS_DIR", tmp_path / "logs")
    
    paths = get_run_paths(ticker, run_id)
    paths["AUDIT_LOG_PATH"].parent.mkdir(parents=True, exist_ok=True)
    paths["SQLITE_DB_PATH"].parent.mkdir(parents=True, exist_ok=True)
    paths["MI_SUMMARY_PATH"].parent.mkdir(parents=True, exist_ok=True)
    
    # 1. JSON Context (Moat and Sentiment)
    ctx_data = {
        "moat_width": "NARROW",
        "moat_narrative": "No moat.",
        "sentiment_trend": "DETERIORATING"
    }
    with open(paths["MI_SUMMARY_PATH"], "w") as f:
        json.dump(ctx_data, f)
        
    db = DatabaseManager(paths["SQLITE_DB_PATH"])
    
    # Tables
    from agents.market_intelligence.module5_news_sentiment import get_news_sentiment_table
    from agents.market_intelligence.module3_live_market_data import get_market_data_table
    from agents.market_intelligence.module4_comps_valuation import get_comps_table
    from agents.market_intelligence.module6_industry_macro import get_industry_macro_table
    
    db.create_tables([
        get_news_sentiment_table(db.metadata),
        get_market_data_table(db.metadata),
        get_comps_table(db.metadata),
        get_industry_macro_table(db.metadata)
    ])
    
    with db.get_connection() as conn:
        from sqlalchemy import text
        # 3. Crisis News
        conn.execute(text("INSERT INTO news_sentiment (ticker, headline, crisis_flag, crisis_type) VALUES ('AAPL', 'Crisis1', 1, 'FRAUD')"))
        conn.execute(text("INSERT INTO news_sentiment (ticker, headline, crisis_flag, crisis_type) VALUES ('AAPL', 'Crisis2', 1, 'FRAUD')"))
        # Should sum to 30 pts
        
        # 4. Market Data
        conn.execute(text("INSERT INTO competitor_market_data (ticker, analyst_consensus_rating, short_interest_pct, earn_surp_q1_pct, earn_surp_q2_pct, earn_surp_q3_pct, earn_surp_q4_pct) VALUES ('AAPL', 4.0, 20.0, -16.0, -5.0, -2.0, 1.0)"))
        
        # 5. Comps
        conn.execute(text("INSERT INTO trading_comps_table (ticker, rev_growth_pct, ebitda_margin, ev_ebitda) VALUES ('AAPL', 5.0, 10.0, 20.0)"))
        conn.execute(text("INSERT INTO trading_comps_table (ticker, rev_growth_pct, ebitda_margin, ev_ebitda) VALUES ('Sector Median', 10.0, 20.0, 10.0)"))
        
        # 6. Macro
        conn.execute(text("INSERT INTO industry_macro (ticker, indicator_name, trend_direction) VALUES ('AAPL', '10Y Treasury Yield', 'UP')"))
        
    db.dispose()
    
    return MarketIntelContext(
        run_id=run_id,
        ticker=ticker,
        company_name="Apple Inc.",
        cik="0000320193",
        sic_code="3571",
        industry_name="Electronic Computers",
        fiscal_year_end_month=9,
        most_recent_fiscal_year=2025,
        is_sector_benchmark_partial=False,
        is_chromadb_reachable=True,
        top_peers=[],
        target_ratios={}
    )

def test_market_risk_signal_generator(mock_context):
    generator = MarketRiskSignalGenerator(mock_context)
    generator.run()
    
    with generator.db_manager.get_connection() as conn:
        from sqlalchemy import text
        rows = conn.execute(text("SELECT * FROM market_risk_signals")).fetchall()
        cols = [c[1] for c in conn.execute(text("PRAGMA table_info(market_risk_signals)")).fetchall()]
        dicts = [dict(zip(cols, r)) for r in rows]
        
    assert len(dicts) > 0
    names = [d["signal_name"] for d in dicts]
    
    assert "Narrow Competitive Moat" in names
    assert "Deteriorating News Sentiment" in names
    assert "Crisis News Detected: FRAUD" in names
    assert "Analyst Bearish Consensus" in names
    assert "High Short Interest" in names
    assert "Consistent Earnings Misses" in names
    assert "Significant Earnings Miss" in names
    assert "Below Sector Median Growth" in names
    assert "Below Sector Median Margin" in names
    assert "Significant Valuation Premium" in names
    assert "Macro Headwind: 10Y Treasury Yield" in names
    
    # Check Crisis capping (2 crises = 30 pts)
    crises = [d for d in dicts if "Crisis News" in d["signal_name"]]
    assert len(crises) == 2
    assert crises[0]["points_contribution"] == 15
    assert crises[1]["points_contribution"] == 15
    
    # Check Moat pts
    moat = next(d for d in dicts if "Moat" in d["signal_name"])
    assert moat["points_contribution"] == 20
