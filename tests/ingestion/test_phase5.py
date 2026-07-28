import pytest
from pathlib import Path
from schemas.pydantic_models import CompanyFinancialHistory, AnnualFinancials
from agents.ingestion.phase5_validation import run_phase5

def test_run_phase5(tmp_path):
    paths = {"AUDIT_LOG_PATH": tmp_path / "audit.jsonl"}
    
    fin1 = AnnualFinancials(
        fiscal_year=2024,
        revenue=1000,
        cost_of_revenue=400,
        # missing gross_profit, should be computed as 600
        total_assets=1000,
        total_liabilities=500,
        total_equity=500, # balanced
        net_income=100,
        weighted_avg_shares=10,
        eps_diluted=10, # exact match
        operating_cash_flow=200,
        capital_expenditures=50,
        # missing free_cash_flow, should be computed as 150
        income_tax_expense=20
        # missing income_before_tax, should be 120
    )
    
    fin2 = AnnualFinancials(
        fiscal_year=2023,
        revenue=1000,
        cost_of_revenue=400,
        gross_profit=500, # 100 off, should warn
        total_assets=1000,
        total_liabilities=600,
        total_equity=500, # 1100 vs 1000, should warn
        net_income=100,
        weighted_avg_shares=10,
        eps_diluted=9, # 10 vs 9, >5%, should warn
        operating_cash_flow=None, # Missing OCF
        capital_expenditures=None,
        income_tax_expense=None
    )
    
    history = CompanyFinancialHistory(
        ticker="TEST",
        cik="0000000000",
        company_name="Test Co",
        annual_data=[fin1, fin2]
    )
    
    result = run_phase5(history, paths)
    
    assert len(result.warnings) == 3
    assert any("Gross Profit inconsistency" in w for w in result.warnings)
    assert any("Balance Sheet does not balance" in w for w in result.warnings)
    assert any("EPS mismatch" in w for w in result.warnings)
    
    # Check computed values in 2024
    assert result.financial_history.annual_data[0].gross_profit == 600
    assert result.financial_history.annual_data[0].free_cash_flow == 150
    assert result.financial_history.annual_data[0].income_before_tax == 120
    
    # Check missing fields log
    missing_fields_names = [m.field for m in result.missing_fields]
    assert "operating_cash_flow" in missing_fields_names
    
    ocf_log = next(m for m in result.missing_fields if m.field == "operating_cash_flow")
    assert ocf_log.years == [2023]
    assert ocf_log.criticality == "HIGH"
