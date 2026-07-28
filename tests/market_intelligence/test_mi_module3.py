import json
import pytest
import sys
from unittest.mock import patch, MagicMock

sys.modules["fastmcp"] = MagicMock()
sys.modules["yfinance"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["litellm"] = MagicMock()

from config.paths import get_run_paths
from schemas.pydantic_models import MarketIntelContext
from agents.market_intelligence.module3_live_market_data import LiveMarketDataExtractor
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
    
    db = DatabaseManager(paths["SQLITE_DB_PATH"])
    from agents.market_intelligence.module1_named_competitors import get_named_competitors_table
    db.create_tables([get_named_competitors_table(db.metadata)])
    
    with db.get_connection() as conn:
        from sqlalchemy import text
        conn.execute(text("INSERT INTO named_competitors (ticker, company_name, cik) VALUES ('MSFT', 'Microsoft', '0000000001')"))
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

@patch("agents.market_intelligence.module3_live_market_data.get_earnings_surprise_history")
@patch("agents.market_intelligence.module3_live_market_data.get_analyst_data")
@patch("agents.market_intelligence.module3_live_market_data.get_market_snapshot")
def test_live_market_data_success(mock_snap, mock_ana, mock_earn, mock_context):
    mock_snap.return_value = json.dumps({
        "current_price": 150.0,
        "market_cap": 2000000,
        "fifty_two_week_high": 180.0,
        "fifty_two_week_low": 120.0,
        "beta": 1.2,
        "shares_outstanding": 10000,
        "ytd_return_pct": 10.5,
        "one_year_return_pct": 20.0,
        "data_date": "2026-07-05"
    })
    
    mock_ana.return_value = json.dumps({
        "analyst_consensus_rating": 2.1,
        "analyst_price_target": 170.0,
        "num_analysts_covering": 35,
        "short_interest_pct": 2.5,
        "institutional_ownership": 60.5,
        "data_date": "2026-07-05"
    })
    
    mock_earn.return_value = json.dumps({
        "quarters": [
            {"quarter_label": "Q2_2026", "surprise_pct": 5.0},
            {"quarter_label": "Q1_2026", "surprise_pct": -2.0}
        ],
        "data_date": "2026-07-05"
    })
    
    extractor = LiveMarketDataExtractor(mock_context)
    extractor.run()
    
    with extractor.db_manager.get_connection() as conn:
        from sqlalchemy import text
        res = conn.execute(text("SELECT * FROM competitor_market_data")).fetchall()
        
    # Should be 2 rows (MSFT + AAPL)
    assert len(res) == 2
    
    # Check MSFT
    msft = next(r for r in res if r[0] == 'MSFT')
    assert msft[1] == 150.0  # price
    assert msft[2] == 2000000  # mcap
    assert msft[14] == 5.0  # q1 surprise
    assert msft[15] == -2.0 # q2 surprise
    assert msft[16] is None # q3 surprise

@patch("agents.market_intelligence.module3_live_market_data.get_earnings_surprise_history")
@patch("agents.market_intelligence.module3_live_market_data.get_analyst_data")
@patch("agents.market_intelligence.module3_live_market_data.get_market_snapshot")
def test_live_market_data_degradation(mock_snap, mock_ana, mock_earn, mock_context):
    mock_snap.return_value = json.dumps({
        "current_price": None, "market_cap": None, "fifty_two_week_high": None,
        "fifty_two_week_low": None, "beta": None, "shares_outstanding": None,
        "ytd_return_pct": None, "one_year_return_pct": None, "data_date": "2026-07-05"
    })
    
    mock_ana.return_value = json.dumps({
        "analyst_consensus_rating": None, "analyst_price_target": None,
        "num_analysts_covering": None, "short_interest_pct": None,
        "institutional_ownership": None, "data_date": "2026-07-05"
    })
    
    mock_earn.return_value = json.dumps({"quarters": [], "data_date": "2026-07-05"})
    
    extractor = LiveMarketDataExtractor(mock_context)
    extractor.run()
    
    with extractor.db_manager.get_connection() as conn:
        from sqlalchemy import text
        res = conn.execute(text("SELECT ticker, current_price, analyst_consensus_rating FROM competitor_market_data")).fetchall()
        
    assert len(res) == 2
    assert res[0][1] is None
    assert res[0][2] is None
