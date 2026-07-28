import pytest
import json
from unittest.mock import patch
from pathlib import Path
from agents.ingestion.phase4_financial_data import run_phase4
from agents.ingestion.phase1_company_identity import Phase1Result, CompanyIdentity

@patch("agents.ingestion.phase4_financial_data.get_company_facts")
@patch("agents.ingestion.phase4_financial_data.get_company_market_profile")
@patch("agents.ingestion.phase4_financial_data.get_historical_close_price")
def test_run_phase4(mock_get_price, mock_get_profile, mock_get_facts, tmp_path):
    mock_get_facts.return_value = json.dumps({
        "success": True,
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fp": "FY", "fy": 2024, "val": 1000}
                        ]
                    }
                }
            }
        }
    })
    
    mock_get_profile.return_value = json.dumps({"beta": 1.2})
    mock_get_price.return_value = json.dumps({"price": 150.0, "actual_trading_date": "2024-09-28"})
    
    paths = {
        "AUDIT_LOG_PATH": tmp_path / "audit.jsonl"
    }
    
    phase1_result = Phase1Result(
        company_identity=CompanyIdentity(
            ticker="AAPL",
            cik="0000320193",
            company_name="Apple Inc.",
            sic_code="3571",
            industry_name="Electronic Computers",
            exchange="Nasdaq",
            state_of_incorp="CA",
            fiscal_year_end="0930",
            fiscal_year_end_month=9
        ),
        selected_filings=None,
        cik="0000320193"
    )
    
    history = run_phase4(phase1_result, "AAPL", "AAPL_RUN1", paths)
    
    assert history.ticker == "AAPL"
    assert history.beta == 1.2
    assert len(history.annual_data) == 1
    
    fin = history.annual_data[0]
    assert fin.fiscal_year == 2024
    assert fin.revenue == 1000
    assert fin.stock_price_fy_end == 150.0
    
    audit_text = paths["AUDIT_LOG_PATH"].read_text()
    assert "Beginning financial data collection" in audit_text
    assert "Extracted 1 years of financial data." in audit_text

def test_run_phase4_no_facts(tmp_path):
    with patch("agents.ingestion.phase4_financial_data.get_company_facts") as mock_get_facts:
        mock_get_facts.return_value = json.dumps({"success": False, "error_reason": "Not found"})
        
        paths = {"AUDIT_LOG_PATH": tmp_path / "audit.jsonl"}
        phase1_result = Phase1Result(
            company_identity=CompanyIdentity(
                ticker="INVALID", cik="0000000000", company_name="Inv", sic_code="0000", industry_name="Inv", exchange="OTC", state_of_incorp="DE", fiscal_year_end="1231", fiscal_year_end_month=12
            ),
            selected_filings=None,
            cik="0000000000"
        )
        
        with pytest.raises(ValueError, match="CompanyFacts data unavailable"):
            run_phase4(phase1_result, "INVALID", "RUN1", paths)
