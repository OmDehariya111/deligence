"""
Module:  test_module_03.py
Agent:   Memo Generation Agent
Purpose: Test the CompanyOverviewModule logic and fallback pattern.
Inputs:  None
Outputs: None
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from agents.memo_generation.module_03_company_overview import CompanyOverviewModule
from schemas.pydantic_models import (
    MemoDataConfidence,
    MemoDocumentPlan,
    MemoModule1Result,
    SectionPlanEntry,
)

@pytest.fixture
def mock_run_id_m03():
    return "AAPL_20260703_190501"

@pytest.fixture
def mock_m1_result_m03(mock_run_id_m03):
    return MemoModule1Result(
        run_id=mock_run_id_m03,
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
def mock_data_m03():
    return {
        "memo_data": {
            "ingestion": {"company_identity": {"company_name": "Apple Inc.", "cik": "0000320193"}},
            "analysis": {"earnings_quality_score": 85},
            "risk": {"COMPOSITE_RISK": {"composite_score": 35, "investment_stance": "PROCEED"}}
        },
        "db_tables": {
            "financial_data": pd.DataFrame([{"fiscal_year": 2023, "revenue": 383285, "market_cap": 2500000}])
        },
        "number_lookup": {"revenue_fy2023": 383285},
        "number_lookup_metadata": {
            "revenue_fy2023": {
                "value": 383285, "source_table": "financial_data", "source_key": "revenue"
            }
        }
    }

@patch("agents.memo_generation.module_03_company_overview.DatabaseManager")
@patch("agents.memo_generation.module_03_company_overview.get_run_paths")
@patch("agents.memo_generation.module_03_company_overview.litellm.completion")
@patch("agents.memo_generation.module_03_company_overview.chromadb.PersistentClient")
def test_company_overview_success(mock_chroma, mock_llm, mock_get_paths, mock_db, tmp_path, mock_run_id_m03, mock_m1_result_m03, mock_data_m03):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{mock_run_id_m03}.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db",
        "CHROMADB_DIR_PATH": tmp_path / "chromadb"
    }
    
    # Mock Chroma
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_chroma.return_value = mock_client
    mock_client.get_collection.return_value = mock_collection
    
    mock_collection.query.side_effect = [
        {"documents": [["Apple makes iPhones", "Apple makes Macs"]]},
        {"documents": [["Apple sells globally"]]}
    ]
    
    # Mock LLM
    mock_msg1 = MagicMock()
    mock_msg1.message.content = "Apple Inc. designs, manufactures, and markets smartphones. It generated substantial revenue this year."
    mock_choice1 = MagicMock()
    mock_choice1.message = mock_msg1.message
    
    mock_msg2 = MagicMock()
    mock_msg2.message.content = json.dumps([])
    mock_choice2 = MagicMock()
    mock_choice2.message = mock_msg2.message
    
    mock_llm.side_effect = [
        MagicMock(choices=[mock_choice1]),
        MagicMock(choices=[mock_choice2])
    ]
    
    module = CompanyOverviewModule("AAPL", mock_m1_result_m03, **mock_data_m03)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.fallback_used is False
    assert "Apple Inc. designs" in result.company_overview_narrative_text
    assert "0000320193" in result.company_facts_table_text
    assert "2,500,000.0" in result.company_facts_table_text

@patch("agents.memo_generation.module_03_company_overview.DatabaseManager")
@patch("agents.memo_generation.module_03_company_overview.get_run_paths")
@patch("agents.memo_generation.module_03_company_overview.litellm.completion")
@patch("agents.memo_generation.module_03_company_overview.chromadb.PersistentClient")
def test_company_overview_zero_chunks(mock_chroma, mock_llm, mock_get_paths, mock_db, tmp_path, mock_run_id_m03, mock_m1_result_m03, mock_data_m03):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{mock_run_id_m03}.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db",
        "CHROMADB_DIR_PATH": tmp_path / "chromadb"
    }
    
    # Mock Chroma failure (e.g. collection missing)
    mock_chroma.return_value.get_collection.side_effect = ValueError("Collection not found")
    
    module = CompanyOverviewModule("AAPL", mock_m1_result_m03, **mock_data_m03)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.fallback_used is True
    assert "A detailed business description could not be retrieved" in result.company_overview_narrative_text
    assert mock_llm.call_count == 0  # Should NOT attempt LLM call if no chunks!

@patch("agents.memo_generation.module_03_company_overview.DatabaseManager")
@patch("agents.memo_generation.module_03_company_overview.get_run_paths")
@patch("agents.memo_generation.module_03_company_overview.litellm.completion")
@patch("agents.memo_generation.module_03_company_overview.chromadb.PersistentClient")
def test_company_overview_llm_failure(mock_chroma, mock_llm, mock_get_paths, mock_db, tmp_path, mock_run_id_m03, mock_m1_result_m03, mock_data_m03):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{mock_run_id_m03}.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db",
        "CHROMADB_DIR_PATH": tmp_path / "chromadb"
    }
    
    # Mock Chroma success
    mock_collection = MagicMock()
    mock_chroma.return_value.get_collection.return_value = mock_collection
    mock_collection.query.return_value = {"documents": [["Chunk1"]]}
    
    # Mock LLM failure
    mock_llm.side_effect = Exception("API Error")
    
    module = CompanyOverviewModule("AAPL", mock_m1_result_m03, **mock_data_m03)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.fallback_used is True
    assert "could not be retrieved" in result.company_overview_narrative_text
    assert mock_llm.call_count == 3  # Tried 3 times
