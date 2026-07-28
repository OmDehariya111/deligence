import pytest
import sys
from unittest.mock import patch, MagicMock

sys.modules["fastmcp"] = MagicMock()
sys.modules["yfinance"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["litellm"] = MagicMock()

from config.paths import get_run_paths
from schemas.pydantic_models import MarketIntelContext
from agents.market_intelligence.module4_comps_valuation import CompsAndValuationGenerator
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
    
    # Create required tables for testing Module 4
    from agents.market_intelligence.module2_ltm_financials import get_ltm_table
    from agents.market_intelligence.module3_live_market_data import get_market_data_table
    db.create_tables([
        get_ltm_table(db.metadata),
        get_market_data_table(db.metadata)
    ])
    
    with db.get_connection() as conn:
        from sqlalchemy import text
        # Insert target AAPL
        conn.execute(text("""
            INSERT INTO competitor_ltm_financials (ticker, ltm_revenue, ltm_ebitda, ltm_operating_inc, ltm_net_income, ltm_fcf, latest_net_debt, prior_fy_revenue) 
            VALUES ('AAPL', 300, 100, 90, 80, 75, 50, 280)
        """))
        conn.execute(text("""
            INSERT INTO competitor_market_data (ticker, current_price, market_cap, shares_outstanding) 
            VALUES ('AAPL', 150, 1500, 10)
        """))
        
        # Insert peer MSFT
        conn.execute(text("""
            INSERT INTO competitor_ltm_financials (ticker, ltm_revenue, ltm_ebitda, ltm_operating_inc, ltm_net_income, ltm_fcf, latest_net_debt, prior_fy_revenue) 
            VALUES ('MSFT', 200, 80, 75, 70, 65, 20, 180)
        """))
        conn.execute(text("""
            INSERT INTO competitor_market_data (ticker, current_price, market_cap, shares_outstanding) 
            VALUES ('MSFT', 300, 1500, 5)
        """))
        
        # Insert peer GOOG
        conn.execute(text("""
            INSERT INTO competitor_ltm_financials (ticker, ltm_revenue, ltm_ebitda, ltm_operating_inc, ltm_net_income, ltm_fcf, latest_net_debt, prior_fy_revenue) 
            VALUES ('GOOG', 250, 90, 85, 75, 70, 30, 230)
        """))
        conn.execute(text("""
            INSERT INTO competitor_market_data (ticker, current_price, market_cap, shares_outstanding) 
            VALUES ('GOOG', 100, 1200, 12)
        """))
        
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

def test_comps_valuation(mock_context):
    generator = CompsAndValuationGenerator(mock_context)
    generator.run()
    
    with generator.db_manager.get_connection() as conn:
        from sqlalchemy import text
        comps = conn.execute(text("SELECT * FROM trading_comps_table")).fetchall()
        vals = conn.execute(text("SELECT * FROM implied_valuation")).fetchall()
        
    # We inserted AAPL, MSFT, GOOG. Plus Median and Mean rows = 5 rows.
    assert len(comps) == 5
    
    # 3 valuation methods (EV_EBITDA, EV_REVENUE, P_E)
    assert len(vals) == 3
    
    # Check EV computation
    aapl_comp = next(c for c in comps if c[0] == 'AAPL')
    # cols: ticker, current_price, market_cap, enterprise_value, ytd_return_pct, beta, ltm_revenue, rev_growth_pct...
    # EV = market_cap (1500) + latest_net_debt (50) = 1550
    assert aapl_comp[3] == 1550
    
    # MSFT EV = 1500 + 20 = 1520
    # MSFT EV/EBITDA = 1520 / 80 = 19.0
    msft_comp = next(c for c in comps if c[0] == 'MSFT')
    assert msft_comp[13] == 19.0
    
    # GOOG EV = 1200 + 30 = 1230
    # GOOG EV/EBITDA = 1230 / 90 = 13.666...
    goog_comp = next(c for c in comps if c[0] == 'GOOG')
    assert round(goog_comp[13], 3) == 13.667

    # Valuation check for EV_EBITDA
    ev_ebitda_val = next(v for v in vals if v[0] == 'EV_EBITDA')
    # peers ev_ebitda = [13.666..., 19.0]
    # median peer EV/EBITDA = 16.333...
    assert round(ev_ebitda_val[2], 3) == 16.333
    
    # Target LTM EBITDA = 100
    # Implied EV Base = 1633.333...
    assert round(ev_ebitda_val[6], 2) == 1633.33
    
    # Target Net Debt = 50
    # Implied Eq Base = 1633.333 - 50 = 1583.33...
    assert round(ev_ebitda_val[8], 2) == 1583.33
    
    # Target Shares = 10
    # Implied PS = 158.33
    assert round(ev_ebitda_val[9], 2) == 158.33
