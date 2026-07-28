"""
Module:  test_module_13.py
Agent:   Memo Generation Agent
Purpose: Test the final export logic, PDF conditional checking, and sqlite logging.
Inputs:  None
Outputs: None
"""

import json
import sqlite3
import time
from unittest.mock import MagicMock, patch

import pytest
from docx import Document

from agents.memo_generation.module_13_export import ExportModule
from schemas.pydantic_models import (
    MemoDataConfidence,
    MemoDocumentPlan,
    MemoModule1Result,
    MemoModule11Result,
    MemoModule12Result,
    SectionPlanEntry,
)

@pytest.fixture
def mock_run_id_m13():
    return "AAPL_20260703_190501"

@pytest.fixture
def mock_m1_result_success(mock_run_id_m13):
    return MemoModule1Result(
        run_id=mock_run_id_m13,
        status="COMPLETE",
        template_variant="STANDARD",
        template_sub_flags=[],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", risk_assessment="HIGH",
            recommendation="HIGH"
        ),
        section_plan=MemoDocumentPlan(
            executive_summary=SectionPlanEntry(target_words=500, depth="STANDARD"),
            company_overview=SectionPlanEntry(target_words=450, depth="STANDARD"),
            financial_analysis=SectionPlanEntry(target_words=1000, depth="STANDARD"),
            sector_benchmarking=SectionPlanEntry(target_words=500, depth="STANDARD"),
            market_context=SectionPlanEntry(target_words=550, depth="STANDARD"),
            risk_assessment=SectionPlanEntry(target_words=1100, depth="STANDARD"),
            action_items=SectionPlanEntry(target_words=300, depth="STANDARD"),
            recommendation=SectionPlanEntry(target_words=600, depth="STANDARD")
        )
    )

@pytest.fixture
def mock_m11_result(mock_run_id_m13):
    return MemoModule11Result(
        run_id=mock_run_id_m13,
        status="COMPLETE",
        total_claims_checked=10,
        regex_pass_claims=8,
        llm_supplemental_claims=2,
        verified=9,
        mismatch_corrected=1,
        not_found_removed=0,
        sections_excluded_placeholder=[],
        validation_passed="PASSED_WITH_CORRECTIONS",
        final_validated_sections={"exec_summary": "100 words here."}
    )

@pytest.fixture
def mock_m12_result(mock_run_id_m13):
    doc = Document()
    doc.add_paragraph("Test")
    return MemoModule12Result(
        run_id=mock_run_id_m13,
        status="COMPLETE",
        docx_document=doc
    )

@patch("win32com.client.Dispatch", side_effect=Exception("Mocked COM error"))
@patch("agents.memo_generation.module_13_export.subprocess.run")
@patch("agents.memo_generation.module_13_export.DatabaseManager")
@patch("agents.memo_generation.module_13_export.get_run_paths")
def test_export_success_with_pdf(mock_get_paths, mock_db, mock_subprocess, mock_win32, tmp_path, mock_m1_result_success, mock_m11_result, mock_m12_result):
    docx_path = tmp_path / "memo.docx"
    pdf_path = tmp_path / "memo.pdf"
    json_path = tmp_path / "cert.json"
    
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db",
        "MEMO_DOCX_PATH": docx_path,
        "MEMO_PDF_PATH": pdf_path,
        "MEMO_JSON_CERT_PATH": json_path,
    }
    
    # Mock the DB returning claims
    mock_conn = MagicMock()
    mock_cursor = [
        {"run_id": mock_m1_result_success.run_id, "claim_text": "Test claim"}
    ]
    mock_conn.exec_driver_sql.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    mock_db.return_value.get_connection.return_value = mock_conn
    
    # Mock subprocess success (touch the file to simulate LibreOffice creating it)
    def create_pdf(*args, **kwargs):
        pdf_path.touch()
    mock_subprocess.side_effect = create_pdf
    
    module = ExportModule(
        "AAPL", mock_m1_result_success, mock_m11_result, mock_m12_result, 
        {"ingestion": {"company_name": "Apple"}}, libreoffice_available=True, start_time=time.time()
    )
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.docx_path == str(docx_path)
    assert result.pdf_path == str(pdf_path)
    assert result.json_cert_path == str(json_path)
    
    # Verify files created
    assert docx_path.exists()
    assert pdf_path.exists()
    assert json_path.exists()
    
    # Verify JSON content
    with open(json_path) as f:
        cert = json.load(f)
        assert cert["run_completeness"]["pdf_generated"] is True


@patch("win32com.client.Dispatch", side_effect=Exception("Mocked COM error"))
@patch("agents.memo_generation.module_13_export.subprocess.run")
@patch("agents.memo_generation.module_13_export.DatabaseManager")
@patch("agents.memo_generation.module_13_export.get_run_paths")
def test_export_no_libreoffice(mock_get_paths, mock_db, mock_subprocess, mock_win32, tmp_path, mock_m1_result_success, mock_m11_result, mock_m12_result):
    docx_path = tmp_path / "memo2.docx"
    pdf_path = tmp_path / "memo2.pdf"
    json_path = tmp_path / "cert2.json"
    
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db",
        "MEMO_DOCX_PATH": docx_path,
        "MEMO_PDF_PATH": pdf_path,
        "MEMO_JSON_CERT_PATH": json_path,
    }
    
    mock_conn = MagicMock()
    mock_conn.exec_driver_sql.return_value = []
    mock_conn.__enter__.return_value = mock_conn
    mock_db.return_value.get_connection.return_value = mock_conn
    
    module = ExportModule(
        "AAPL", mock_m1_result_success, mock_m11_result, mock_m12_result, 
        {"ingestion": {"company_name": "Apple"}}, libreoffice_available=False, start_time=time.time()
    )
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.pdf_path is None # Skipped gracefully!
    
    # Subprocess shouldn't be called
    mock_subprocess.assert_not_called()
    
    # Certificate should reflect pdf skip
    with open(json_path) as f:
        cert = json.load(f)
        assert cert["run_completeness"]["pdf_generated"] is False
