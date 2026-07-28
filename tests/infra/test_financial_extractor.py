import pytest
from utils.financial_extractor import FinancialExtractor

def test_financial_extractor_basic():
    # Mock company facts
    mock_facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fp": "FY", "fy": 2024, "val": 1000}
                        ]
                    }
                },
                "CostOfRevenue": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fp": "FY", "fy": 2024, "val": 400}
                        ]
                    }
                },
                "GeneralAndAdministrativeExpense": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fp": "FY", "fy": 2024, "val": 100}
                        ]
                    }
                },
                "SellingAndMarketingExpense": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fp": "FY", "fy": 2024, "val": 50}
                        ]
                    }
                }
            }
        }
    }
    
    extractor = FinancialExtractor(mock_facts)
    years = extractor.get_available_years()
    assert years == [2024]
    
    fin = extractor.extract_year(2024)
    assert fin.fiscal_year == 2024
    assert fin.revenue == 1000
    assert fin.cost_of_revenue == 400
    assert fin.gross_profit == 600  # Computed
    assert fin.sga_expense == 150   # Computed sum of G&A and S&M
    
def test_financial_extractor_fallback():
    mock_facts = {
        "facts": {
            "us-gaap": {
                "SalesRevenueNet": { # 4th priority fallback
                    "units": {
                        "USD": [
                            {"form": "10-K", "fp": "FY", "fy": 2023, "val": 500}
                        ]
                    }
                }
            }
        }
    }
    extractor = FinancialExtractor(mock_facts)
    fin = extractor.extract_year(2023)
    assert fin.revenue == 500
