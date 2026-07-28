import pytest
import json
import sys
from unittest.mock import patch, MagicMock

sys.modules["litellm"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["fastmcp"] = MagicMock()

from config.paths import get_run_paths
from schemas.pydantic_models import MarketIntelContext
from agents.market_intelligence.module8_mi_summary import MarketIntelligenceSummarizer
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
    
    ctx_data = {
        "moat_width": "WIDE",
        "moat_narrative": "Apple wide moat",
        "sentiment_trend": "UP",
        "implied_valuation": {"primary_method": "EV_EBITDA", "peer_median_multiple": 20.0}
    }
    with open(paths["MI_SUMMARY_PATH"], "w") as f:
        json.dump(ctx_data, f)
        
    db = DatabaseManager(paths["SQLITE_DB_PATH"])
    
    from agents.market_intelligence.module1_named_competitors import get_named_competitors_table
    from agents.market_intelligence.module7_market_risk import get_market_risk_signals_table
    from agents.market_intelligence.module3_live_market_data import get_market_data_table
    from agents.market_intelligence.module4_comps_valuation import get_comps_table
    
    db.create_tables([
        get_named_competitors_table(db.metadata),
        get_market_risk_signals_table(db.metadata),
        get_market_data_table(db.metadata),
        get_comps_table(db.metadata)
    ])
    
    with db.get_connection() as conn:
        from sqlalchemy import text
        conn.execute(text("INSERT INTO named_competitors (ticker, company_name) VALUES ('MSFT', 'Microsoft')"))
        conn.execute(text("INSERT INTO named_competitors (ticker, company_name) VALUES ('GOOG', 'Alphabet')"))
        
        conn.execute(text("INSERT INTO market_risk_signals (signal_category, signal_name, risk_level, points_contribution) VALUES ('SENTIMENT', 'Test', 'HIGH', 15)"))
        
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

@patch("agents.market_intelligence.module8_mi_summary.litellm")
def test_market_intelligence_summarizer(mock_litellm, mock_context):
    mock_litellm.completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='{"verdict": "ABOVE AVERAGE", "basis": "Strong moat.", "key_advantages": ["Moat"], "key_vulnerabilities": ["Price"]}'))]
    )
    
    summarizer = MarketIntelligenceSummarizer(mock_context)
    summarizer.run()
    
    paths = get_run_paths(mock_context.ticker, mock_context.run_id)
    with open(paths["MI_SUMMARY_PATH"], "r") as f:
        data = json.load(f)
        
    assert data["ticker"] == "AAPL"
    assert data["modules_status"]["module_1_named_competitors"] == "COMPLETE"
    assert data["modules_status"]["module_2_ltm_financials"] == "FAILED" # Table doesn't exist in our mock
    assert data["modules_status"]["competitor_count"] == 2
    
    assert len(data["NAMED_COMPETITORS"]) == 2
    
    assert data["IMPLIED_VALUATION"]["primary_method"] == "EV_EBITDA"
    assert data["COMPETITIVE_MOAT"]["moat_width"] == "WIDE"
    
    assert data["MARKET_RISK_SIGNALS_COUNT"]["high_severity"] == 1
    assert data["MARKET_RISK_SIGNALS_COUNT"]["total_points"] == 15
    
    assert data["OVERALL_COMPETITIVE_POSITION"]["verdict"] == "ABOVE AVERAGE"
