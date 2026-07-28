import json
import time

import pytest
from pydantic import ValidationError

from mcp_servers.sec_edgar_server import get_company_submissions, resolve_ticker_to_cik
from schemas.pydantic_models import CompanySubmissionsResult, TickerResolutionResult


def test_resolve_ticker_aapl_returns_correct_cik():
    result_json = resolve_ticker_to_cik("AAPL")
    result = TickerResolutionResult.model_validate_json(result_json)
    
    assert result.found is True
    assert result.cik == "0000320193"
    assert "Apple" in result.company_name
    assert result.ticker_matched == "AAPL"


def test_resolve_ticker_nonexistent_returns_not_found():
    result_json = resolve_ticker_to_cik("INVALIDTICKER123")
    result = TickerResolutionResult.model_validate_json(result_json)
    
    assert result.found is False
    assert result.cik is None


def test_get_company_submissions_returns_identity_and_filings():
    # Apple's CIK
    result_json = get_company_submissions("0000320193")
    
    # Ensure it's valid according to Pydantic
    result = CompanySubmissionsResult.model_validate_json(result_json)
    
    assert result.company_identity.company_name == "Apple Inc."
    assert result.company_identity.cik == "0000320193"
    assert result.company_identity.sic_code == "3571"
    assert result.company_identity.fiscal_year_end_month == 9
    
    assert len(result.filings) > 0


def test_submissions_filings_contain_10k():
    result_json = get_company_submissions("0000320193")
    result = CompanySubmissionsResult.model_validate_json(result_json)
    
    forms = [f.form for f in result.filings]
    assert "10-K" in forms
    assert "8-K" in forms


def test_rate_limiting_enforces_100ms_gap():
    # Make two quick calls
    start_time = time.time()
    resolve_ticker_to_cik("MSFT")
    resolve_ticker_to_cik("GOOGL")
    end_time = time.time()
    
    elapsed = end_time - start_time
    # Since the first call takes time, and the lock enforces *at least* 100ms gap
    # The elapsed time should be > 0.1s
    assert elapsed >= 0.1
