"""
Module:  test_module_02.py
Agent:   Memo Generation Agent
Purpose: Test the ExecutiveSummaryModule logic and fallback pattern.
Inputs:  None
Outputs: None
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from agents.memo_generation.module_02_executive_summary import ExecutiveSummaryModule
from schemas.pydantic_models import (
    MemoDataConfidence,
    MemoDocumentPlan,
    MemoModule1Result,
    SectionPlanEntry,
)

@pytest.fixture
def mock_run_id_m02():
    return "AAPL_20260703_190501"

@pytest.fixture
def mock_m1_result_m02(mock_run_id_m02):
    return MemoModule1Result(
        run_id=mock_run_id_m02,
        status="COMPLETE",
        template_variant="STANDARD",
        template_sub_flags=[],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", risk_assessment="HIGH", recommendation="HIGH"
        ),
        section_plan=MemoDocumentPlan(
            executive_summary=SectionPlanEntry(target_words=500, depth="STANDARD"),
            company_overview=SectionPlanEntry(target_words=450, depth="STANDARD"),
            financial_analysis=SectionPlanEntry(target_words=900, depth="STANDARD"),
            sector_benchmarking=SectionPlanEntry(target_words=500, depth="STANDARD"),
            market_context=SectionPlanEntry(target_words=550, depth="STANDARD"),
            risk_assessment=SectionPlanEntry(target_words=1100, depth="STANDARD"),
            action_items=SectionPlanEntry(target_words=300, depth="STANDARD"),
            recommendation=SectionPlanEntry(target_words=600, depth="STANDARD")
        )
    )

@pytest.fixture
def mock_data_m02():
    return {
        "memo_data": {
            "ingestion": {"company_name": "Apple Inc."},
            "analysis": {"earnings_quality_score": 85}
        },
        "db_tables": {},
        "number_lookup": {"revenue_fy2023_millions": 383285},
        "number_lookup_metadata": {
            "revenue_fy2023_millions": {
                "value": 383285, "source_table": "financial_data", "source_key": "revenue"
            }
        }
    }

@patch("agents.memo_generation.module_02_executive_summary.DatabaseManager")
@patch("agents.memo_generation.module_02_executive_summary.get_run_paths")
@patch("agents.memo_generation.module_02_executive_summary.litellm.completion")
def test_exec_summary_success(mock_llm, mock_get_paths, mock_db, tmp_path, mock_run_id_m02, mock_m1_result_m02, mock_data_m02):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{mock_run_id_m02}.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db"
    }
    
    # First call: Prose generation. Second call: Validation JSON.
    mock_msg1 = MagicMock()
    mock_msg1.message.content = "Apple Inc. generated 383,285 million in revenue during this fiscal year, showing strong growth."
    mock_choice1 = MagicMock()
    mock_choice1.message = mock_msg1.message
    
    mock_msg2 = MagicMock()
    mock_msg2.message.content = json.dumps([]) # No mismatches
    mock_choice2 = MagicMock()
    mock_choice2.message = mock_msg2.message
    
    mock_llm.side_effect = [
        MagicMock(choices=[mock_choice1]),
        MagicMock(choices=[mock_choice2])
    ]
    
    module = ExecutiveSummaryModule("AAPL", mock_m1_result_m02, **mock_data_m02)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.fallback_used is False
    assert result.validation_mismatches_found == 0
    assert "Apple Inc." in result.executive_summary_text

@patch("agents.memo_generation.module_02_executive_summary.DatabaseManager")
@patch("agents.memo_generation.module_02_executive_summary.get_run_paths")
@patch("agents.memo_generation.module_02_executive_summary.litellm.completion")
def test_exec_summary_correction(mock_llm, mock_get_paths, mock_db, tmp_path, mock_run_id_m02, mock_m1_result_m02, mock_data_m02):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{mock_run_id_m02}.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db"
    }
    
    mock_conn = MagicMock()
    mock_db.return_value.get_connection.return_value.__enter__.return_value = mock_conn
    
    # First call: Prose generation with error
    mock_msg1 = MagicMock()
    mock_msg1.message.content = "Apple Inc. generated 400,000 million in revenue during this fiscal year, showing strong growth."
    mock_choice1 = MagicMock()
    mock_choice1.message = mock_msg1.message
    
    # Second call: Validation catches the error
    mock_msg2 = MagicMock()
    mismatches = [{
        "number_in_text": "400,000",
        "matched_key": "revenue_fy2023_millions",
        "source_value": "383285",
        "match": False,
        "corrected_sentence": "Apple Inc. generated 383,285 million in revenue."
    }]
    mock_msg2.message.content = json.dumps(mismatches)
    mock_choice2 = MagicMock()
    mock_choice2.message = mock_msg2.message
    
    mock_llm.side_effect = [
        MagicMock(choices=[mock_choice1]),
        MagicMock(choices=[mock_choice2])
    ]
    
    module = ExecutiveSummaryModule("AAPL", mock_m1_result_m02, **mock_data_m02)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.fallback_used is False
    assert result.validation_mismatches_found == 1
    assert result.validation_mismatches_corrected == 1
    
    # Check that it logged to DB
    assert mock_conn.exec_driver_sql.called
    args = mock_conn.exec_driver_sql.call_args[0]
    assert "INSERT INTO memo_integrity_claims" in args[0]

@patch("agents.memo_generation.module_02_executive_summary.DatabaseManager")
@patch("agents.memo_generation.module_02_executive_summary.get_run_paths")
@patch("agents.memo_generation.module_02_executive_summary.litellm.completion")
def test_exec_summary_fallback(mock_llm, mock_get_paths, mock_db, tmp_path, mock_run_id_m02, mock_m1_result_m02, mock_data_m02):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{mock_run_id_m02}.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db"
    }
    
    # Simulate API failure 3 times
    mock_llm.side_effect = Exception("API Error")
    
    module = ExecutiveSummaryModule("AAPL", mock_m1_result_m02, **mock_data_m02)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.fallback_used is True
    assert "could not be generated" in result.executive_summary_text
    assert mock_llm.call_count == 3  # Tried 3 times before falling back
