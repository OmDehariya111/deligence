import json
import pytest
from pathlib import Path
from sqlalchemy import create_engine, text

from schemas.pydantic_models import (
    Phase5Result, CompanyFinancialHistory, AnnualFinancials,
    MissingFieldLog, IngestionSummary
)
from agents.ingestion.phase7_final_output import run_phase7
import time

def test_run_phase7(tmp_path):
    paths = {
        "AUDIT_LOG_PATH": tmp_path / "audit.jsonl",
        "SQLITE_DB_PATH": tmp_path / "financials.db",
        "INGESTION_SUMMARY_PATH": tmp_path / "summary.json"
    }
    
    fin1 = AnnualFinancials(fiscal_year=2024, revenue=1000)
    history = CompanyFinancialHistory(
        ticker="TEST",
        cik="0000000000",
        company_name="Test Co",
        annual_data=[fin1]
    )
    
    missing = [
        MissingFieldLog(
            field="operating_cash_flow",
            years=[2024],
            impact="None",
            criticality="HIGH",
            reason="Test"
        )
    ]
    
    phase5_res = Phase5Result(
        financial_history=history,
        warnings=["Some warning"],
        missing_fields=missing
    )
    
    module_status = {"phase_1_company_identity": "COMPLETED"}
    start_time = time.time() - 10 # 10 seconds ago
    
    result = run_phase7(
        run_id="RUN1",
        phase5_result=phase5_res,
        paths=paths,
        module_status=module_status,
        start_time=start_time
    )
    
    # Check Ingestion Summary
    assert result.status == "COMPLETE_WITH_WARNINGS"
    assert result.field_coverage_summary.fields_missing == 1
    assert result.field_coverage_summary.fields_with_data == 44
    assert result.ingestion_duration_seconds >= 10
    
    # Check JSON file written
    summary_json = json.loads(paths["INGESTION_SUMMARY_PATH"].read_text())
    assert summary_json["status"] == "COMPLETE_WITH_WARNINGS"
    
    # Check SQLite
    engine = create_engine(f"sqlite:///{paths['SQLITE_DB_PATH']}")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT ticker, fiscal_year, revenue FROM financial_data")).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "TEST"
        assert rows[0][1] == 2024
        assert rows[0][2] == 1000.0
