import pytest
from pathlib import Path
from schemas.pydantic_models import Phase5Result, CompanyFinancialHistory, AnnualFinancials
from agents.ingestion.phase6_normalization import run_phase6

def test_run_phase6(tmp_path):
    paths = {"AUDIT_LOG_PATH": tmp_path / "audit.jsonl"}
    
    fin1 = AnnualFinancials(fiscal_year=2024, revenue=1000)
    history = CompanyFinancialHistory(
        ticker="TEST",
        cik="0000000000",
        company_name="Test Co",
        annual_data=[fin1]
    )
    
    phase5_res = Phase5Result(
        financial_history=history,
        warnings=[],
        missing_fields=[]
    )
    
    result = run_phase6(phase5_res, paths)
    
    assert result == phase5_res
    
    audit_text = paths["AUDIT_LOG_PATH"].read_text()
    assert "Checking unit normalization for TEST" in audit_text
    assert "All monetary fields confirmed in full USD, no rescaling needed." in audit_text
