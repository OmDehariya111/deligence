"""
Module:  test_module_05.py
Agent:   Memo Generation Agent
Purpose: Test the SectorBenchmarkingModule logic and graceful degradation.
Inputs:  None
Outputs: None
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from agents.memo_generation.module_05_sector_benchmarking import SectorBenchmarkingModule
from schemas.pydantic_models import (
    MemoDataConfidence,
    MemoDocumentPlan,
    MemoModule1Result,
    SectionPlanEntry,
)

@pytest.fixture
def mock_run_id_m05():
    return "AAPL_20260703_190501"

@pytest.fixture
def mock_m1_result_success(mock_run_id_m05):
    return MemoModule1Result(
        run_id=mock_run_id_m05,
        status="COMPLETE",
        template_variant="STANDARD",
        template_sub_flags=[],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", # THIS ENABLES MODULE 5
            risk_assessment="HIGH", recommendation="HIGH"
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
def mock_m1_result_unavailable(mock_run_id_m05):
    return MemoModule1Result(
        run_id=mock_run_id_m05,
        status="COMPLETE",
        template_variant="LIMITED_DATA",
        template_sub_flags=["MARKET_INTEL_UNAVAILABLE"],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="UNAVAILABLE", # THIS DEGRADES MODULE 5
            risk_assessment="HIGH", recommendation="HIGH"
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
def mock_data_m05():
    return {
        "memo_data": {
            "ingestion": {"company_name": "Apple Inc.", "cik": "0000320193"},
        },
        "db_tables": {
            "trading_comps": pd.DataFrame([
                {"ticker": "MSFT", "company_name": "Microsoft"},
                {"ticker": "GOOG", "company_name": "Alphabet"}
            ])
        },
        "number_lookup": {"peer_multiple": 25.4},
        "number_lookup_metadata": {}
    }

@patch("agents.memo_generation.module_05_sector_benchmarking.DatabaseManager")
@patch("agents.memo_generation.module_05_sector_benchmarking.get_run_paths")
@patch("agents.memo_generation.module_05_sector_benchmarking.litellm.completion")
def test_sector_benchmarking_success(mock_llm, mock_get_paths, mock_db, tmp_path, mock_m1_result_success, mock_data_m05):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db"
    }
    
    # 1 narrative call, 1 validation call
    def make_mock(content):
        m = MagicMock()
        m.message.content = content
        c = MagicMock()
        c.message = m.message
        ret = MagicMock()
        ret.choices = [c]
        return ret
    
    mock_llm.side_effect = [
        make_mock("Apple has a wide moat and strong competitive positioning against peers."),
        make_mock(json.dumps([])) # Validation
    ]
    
    module = SectorBenchmarkingModule("AAPL", mock_m1_result_success, **mock_data_m05)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.fallback_used is False
    assert result.data_unavailable_disclosure is None
    assert "Microsoft" in result.comps_table
    assert "Apple has a wide moat" in result.competitive_narrative
    assert mock_llm.call_count == 2

@patch("agents.memo_generation.module_05_sector_benchmarking.DatabaseManager")
@patch("agents.memo_generation.module_05_sector_benchmarking.get_run_paths")
@patch("agents.memo_generation.module_05_sector_benchmarking.litellm.completion")
def test_sector_benchmarking_unavailable(mock_llm, mock_get_paths, mock_db, tmp_path, mock_m1_result_unavailable, mock_data_m05):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db"
    }
    
    module = SectorBenchmarkingModule("AAPL", mock_m1_result_unavailable, **mock_data_m05)
    result = module.run()
    
    assert result.status == "SKIPPED_UNAVAILABLE"
    assert result.comps_table is None
    assert result.competitive_narrative is None
    assert "Due to limited data availability" in result.data_unavailable_disclosure
    assert mock_llm.call_count == 0  # Should short-circuit completely!
