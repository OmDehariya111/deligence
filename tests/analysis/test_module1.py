import pytest
from agents.analysis.module1_ratio_engine import RatioEngine

def _get_mock_data():
    return {
        2020: {
            "revenue": 1000.0,
            "net_income": 100.0,
        },
        2021: {
            "revenue": 1200.0,
            "net_income": -10.0,
        },
        2022: {
            "revenue": 1500.0,
            "net_income": 50.0,
        },
        2023: {
            "revenue": 2000.0,
            "net_income": 150.0,
            "gross_profit": 800.0,
            "operating_income": 200.0,
            "ebitda": 250.0,
            "total_assets": 5000.0,
            "total_equity": 2000.0,
            "long_term_debt": 1000.0,
            "income_tax_expense": 30.0,
            "income_before_tax": 180.0,
            "current_assets": 1000.0,
            "current_liabilities": 500.0,
            "inventory": 200.0,
            "cash_and_equivalents": 300.0,
            "total_liabilities": 3000.0,
            "short_term_debt": 100.0,
            "interest_expense": 50.0,
            "cost_of_revenue": 1200.0,
            "accounts_receivable": 400.0,
            "accounts_payable": 300.0,
            "free_cash_flow": 120.0,
            "operating_cash_flow": 180.0,
            "capital_expenditures": 60.0,
            "eps_diluted": 1.5,
            "market_cap": 10000.0
        },
        2024: {
            "revenue": 2500.0,
            "net_income": 300.0,
            "gross_profit": 1000.0,
            "operating_income": 400.0,
            "ebitda": 450.0,
            "total_assets": 5500.0,
            "total_equity": 2500.0,
            "long_term_debt": 900.0,
            "income_tax_expense": 60.0,
            "income_before_tax": 360.0,
            "current_assets": 1200.0,
            "current_liabilities": 600.0,
            "inventory": 250.0,
            "cash_and_equivalents": 400.0,
            "total_liabilities": 3000.0,
            "short_term_debt": 50.0,
            "interest_expense": 40.0,
            "cost_of_revenue": 1500.0,
            "accounts_receivable": 500.0,
            "accounts_payable": 350.0,
            "free_cash_flow": 250.0,
            "operating_cash_flow": 300.0,
            "capital_expenditures": 50.0,
            "eps_diluted": 3.0,
            "market_cap": 15000.0
        }
    }


def test_guard_missing_denominator():
    data = {
        2024: {
            "revenue": 100.0,
            "gross_profit": 40.0
            # missing total_assets
        }
    }
    engine = RatioEngine(data, "MINIMAL", 1)
    results = engine.run()
    
    roa = next(r for r in results if r.ratio_name == "roa" and r.fiscal_year == 2024)
    assert roa.status == "MISSING"
    assert "average_assets not available" in roa.reason
    assert roa.value is None


def test_guard_zero_denominator():
    data = {
        2024: {
            "operating_income": 100.0,
            "interest_expense": 0.0  # true zero
        }
    }
    engine = RatioEngine(data, "MINIMAL", 1)
    results = engine.run()
    
    int_cov = next(r for r in results if r.ratio_name == "interest_coverage" and r.fiscal_year == 2024)
    assert int_cov.status == "NOT_APPLICABLE"
    assert "zero interest expense" in int_cov.reason
    assert int_cov.value is None


def test_guard_negative_meaningless():
    data = {
        2024: {
            "net_income": 50.0,
            "total_equity": -100.0  # negative equity
        }
    }
    engine = RatioEngine(data, "MINIMAL", 1)
    results = engine.run()
    
    roe = next(r for r in results if r.ratio_name == "roe" and r.fiscal_year == 2024)
    assert roe.status == "NOT_MEANINGFUL"
    assert "Total Equity is negative" in roe.reason
    assert roe.value is None


def test_cagr_not_computable_base():
    data = {
        2020: {"revenue": -10.0}, # negative base year
        2021: {"revenue": 10.0},
        2022: {"revenue": 20.0},
        2023: {"revenue": 30.0},
        2024: {"revenue": 40.0},
    }
    engine = RatioEngine(data, "FULL", 5)
    results = engine.run()
    
    cagr = next((r for r in results if "cagr" in r.ratio_name and r.fiscal_year == 2024), None)
    assert cagr is not None
    assert cagr.status == "NOT_COMPUTABLE"
    assert "negative" in cagr.reason


def test_cagr_not_computable_years():
    data = {
        2023: {"revenue": 10.0},
        2024: {"revenue": 20.0}, # n_years = 2, so n = 1 (< 2)
    }
    engine = RatioEngine(data, "MINIMAL", 2)
    results = engine.run()
    
    cagr = next((r for r in results if "cagr" in r.ratio_name and r.fiscal_year == 2024), None)
    assert cagr is not None
    assert cagr.status == "NOT_COMPUTABLE"
    assert "Fewer than 3" in cagr.reason


def test_all_ratios_computed():
    data = _get_mock_data()
    engine = RatioEngine(data, "FULL", 5)
    results = engine.run()
    
    # 2024 should have exactly 36 ratios
    ratios_2024 = [r for r in results if r.fiscal_year == 2024]
    
    # Total ratios is 36 (34 year-specific + 2 CAGRs)
    assert len(ratios_2024) == 36
    
    for r in ratios_2024:
        # P/FCF has some weird values if not careful, but our mock data is solid
        assert r.status == "COMPUTED", f"Ratio {r.ratio_name} failed with status {r.status} reason {r.reason}"
        assert r.value is not None

