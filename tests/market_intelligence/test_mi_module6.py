import pytest
import json
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.modules["fastmcp"] = MagicMock()
sys.modules["litellm"] = MagicMock()
sys.modules["chromadb"] = MagicMock()

from config.paths import get_run_paths
from schemas.pydantic_models import MarketIntelContext
from agents.market_intelligence.module6_industry_macro import IndustryMacroExtractor
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
    paths["CHROMADB_DIR_PATH"].parent.mkdir(parents=True, exist_ok=True)
    paths["MI_SUMMARY_PATH"].parent.mkdir(parents=True, exist_ok=True)
    
    with open(paths["MI_SUMMARY_PATH"], "w") as f:
        json.dump({}, f)
        
    return MarketIntelContext(
        run_id=run_id,
        ticker=ticker,
        company_name="Apple Inc.",
        cik="0000320193",
        sic_code="7370", # Tech SIC
        industry_name="Services-Computer Programming, Data Processing, Etc.",
        fiscal_year_end_month=9,
        most_recent_fiscal_year=2025,
        is_sector_benchmark_partial=False,
        is_chromadb_reachable=True,
        top_peers=[],
        target_ratios={}
    )

@patch("agents.market_intelligence.module6_industry_macro.get_fred_series")
@patch("agents.market_intelligence.module6_industry_macro.litellm")
@patch("agents.market_intelligence.module6_industry_macro.chromadb")
def test_industry_macro_extractor(mock_chromadb, mock_litellm, mock_get_fred, mock_context):
    # Mock FRED
    def side_effect_get_fred(series_id, limit):
        if series_id == "DGS10":
            return json.dumps({
                "status": "OK",
                "observations": [
                    {"date": "2026-06-01", "value": "4.50"}, # cur
                    *([{"date": "x", "value": "0"}] * 10),
                    {"date": "2025-06-01", "value": "4.00"}, # 1y
                    *([{"date": "x", "value": "0"}] * 23),
                    {"date": "2023-06-01", "value": "3.00"}  # 3y
                ]
            })
        elif series_id == "PCE":
            return json.dumps({
                "status": "OK",
                "observations": [
                    {"date": "2026-06-01", "value": "15000"},
                    *([{"date": "x", "value": "0"}] * 10),
                    {"date": "2025-06-01", "value": "15000"} # 1y same -> STABLE
                ]
            })
        return json.dumps({"status": "NOT_FOUND"})
        
    mock_get_fred.side_effect = side_effect_get_fred
    
    # Mock ChromaDB
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_chromadb.PersistentClient.return_value = mock_client
    mock_client.get_collection.return_value = mock_collection
    
    mock_collection.query.return_value = {
        "documents": [
            ["We benefit from strong switching costs", "Our platform has deep network effects"]
        ]
    }
    
    # Mock LLM
    mock_litellm.completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="MOAT_WIDTH: WIDE\nNARRATIVE: Apple has a wide moat."))]
    )
    
    extractor = IndustryMacroExtractor(mock_context)
    extractor.run()
    
    with extractor.db_manager.get_connection() as conn:
        from sqlalchemy import text
        rows = conn.execute(text("SELECT * FROM industry_macro")).fetchall()
        cols = [c[1] for c in conn.execute(text("PRAGMA table_info(industry_macro)")).fetchall()]
        dicts = [dict(zip(cols, r)) for r in rows]
        
    # We expect 2 indicators for SIC 3571 (DGS10, PCE) + 1 for Moat Assessment = 3 rows
    assert len(dicts) == 3
    
    dgs10 = next(d for d in dicts if d["indicator_name"] == "10Y Treasury Yield")
    assert dgs10["current_value"] == 4.5
    assert dgs10["value_1y_ago"] == 4.0
    # 4.5 vs 4.0 is a 12.5% increase, so UP
    assert dgs10["trend_direction"] == "UP"
    
    pce = next(d for d in dicts if d["indicator_name"] == "Personal Consumption")
    # 15000 vs 15000 is 0% change, so STABLE
    assert pce["trend_direction"] == "STABLE"
    
    moat = next(d for d in dicts if d["indicator_name"] == "Competitive Moat Assessment")
    assert moat["moat_width"] == "WIDE"
    assert moat["moat_narrative"] == "Apple has a wide moat."
    
    # Check Context Update
    paths = get_run_paths(mock_context.ticker, mock_context.run_id)
    with open(paths["MI_SUMMARY_PATH"], "r") as f:
        ctx = json.load(f)
        
    assert ctx["moat_width"] == "WIDE"
    assert ctx["moat_narrative"] == "Apple has a wide moat."
