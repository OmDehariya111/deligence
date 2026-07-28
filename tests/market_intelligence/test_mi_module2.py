import json
import pytest
import sys
from unittest.mock import patch, MagicMock

sys.modules["fastmcp"] = MagicMock()
sys.modules["litellm"] = MagicMock()
sys.modules["chromadb"] = MagicMock()

from config.paths import get_run_paths
from schemas.pydantic_models import MarketIntelContext
from agents.market_intelligence.module2_ltm_financials import LTMExtractor
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
    
    # Pre-populate named_competitors table
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

@patch("agents.market_intelligence.module2_ltm_financials.get_company_facts")
def test_ltm_detection_individual(mock_facts, mock_context):
    """Test Fix M-2: When Q1+Q2+Q3 ~ 3/4 Annual, treat as INDIVIDUAL."""
    
    # 100 Annual. Q1=25, Q2=25, Q3=25 (Individual)
    mock_facts.return_value = json.dumps({
        "success": True,
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fy": 2025, "fp": "FY", "val": 100},
                            {"form": "10-Q", "fy": 2025, "fp": "Q1", "val": 25},
                            {"form": "10-Q", "fy": 2025, "fp": "Q2", "val": 25},
                            {"form": "10-Q", "fy": 2025, "fp": "Q3", "val": 25},
                            {"form": "10-Q", "fy": 2026, "fp": "Q1", "val": 30},
                        ]
                    }
                }
            }
        }
    })
    
    extractor = LTMExtractor(mock_context)
    extractor.run()
    
    with extractor.db_manager.get_connection() as conn:
        from sqlalchemy import text
        res = conn.execute(text("SELECT ticker, ltm_revenue, reporting_style_detected FROM competitor_ltm_financials WHERE ticker='MSFT'")).fetchone()
        
    assert res is not None
    # LTM = FY(100) + cy_Q1(30) - py_Q1(25) = 105
    assert res[1] == 105.0
    assert res[2] == "INDIVIDUAL"

@patch("agents.market_intelligence.module2_ltm_financials.get_company_facts")
def test_ltm_detection_cumulative(mock_facts, mock_context):
    """Test Fix M-2: When Q3 alone ~ 3/4 Annual, treat as CUMULATIVE."""
    
    # 100 Annual. Q1=25, Q2=50, Q3=75 (Cumulative)
    mock_facts.return_value = json.dumps({
        "success": True,
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fy": 2025, "fp": "FY", "val": 100},
                            {"form": "10-Q", "fy": 2025, "fp": "Q1", "val": 25},
                            {"form": "10-Q", "fy": 2025, "fp": "Q2", "val": 50},
                            {"form": "10-Q", "fy": 2025, "fp": "Q3", "val": 75},
                            {"form": "10-Q", "fy": 2026, "fp": "Q1", "val": 30},
                        ]
                    }
                }
            }
        }
    })
    
    extractor = LTMExtractor(mock_context)
    extractor.run()
    
    with extractor.db_manager.get_connection() as conn:
        from sqlalchemy import text
        res = conn.execute(text("SELECT ticker, ltm_revenue, reporting_style_detected FROM competitor_ltm_financials WHERE ticker='MSFT'")).fetchone()
        
    assert res is not None
    # LTM = FY(100) + cy_Q1(30 individual) - py_Q1(25 individual) = 105
    assert res[1] == 105.0
    assert res[2] == "CUMULATIVE"

@patch("agents.market_intelligence.module2_ltm_financials.get_company_facts")
def test_graceful_degradation(mock_facts, mock_context):
    """Test when get_company_facts fails for a competitor."""
    mock_facts.return_value = json.dumps({
        "success": False,
        "error_reason": "API Limit"
    })
    
    extractor = LTMExtractor(mock_context)
    extractor.run()
    
    with extractor.db_manager.get_connection() as conn:
        from sqlalchemy import text
        res = conn.execute(text("SELECT ticker, ltm_revenue, quarters_used FROM competitor_ltm_financials WHERE ticker='MSFT'")).fetchone()
        
    assert res is not None
    assert res[1] is None  # ltm_revenue should be None
    assert "UNAVAILABLE" in res[2]
