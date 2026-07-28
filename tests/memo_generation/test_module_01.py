"""
Module:  test_module_01.py
Agent:   Memo Generation Agent
Purpose: Test the DocumentPlanModule logic.
Inputs:  None
Outputs: None
"""

from unittest.mock import patch

import pandas as pd
import pytest

from agents.memo_generation.module_01_document_plan import DocumentPlanModule
from schemas.pydantic_models import MemoPreProcessingResult

@pytest.fixture
def mock_run_id_m01():
    return "AAPL_20260703_190501"

@pytest.fixture
def mock_pp_result_full(mock_run_id_m01):
    return MemoPreProcessingResult(
        run_id=mock_run_id_m01,
        status="COMPLETE",
        market_intel_available=True,
        risk_assessment_available=True,
        libreoffice_available=True
    )

@pytest.fixture
def mock_pp_result_limited(mock_run_id_m01):
    return MemoPreProcessingResult(
        run_id=mock_run_id_m01,
        status="COMPLETE",
        market_intel_available=False,
        risk_assessment_available=False,
        libreoffice_available=True
    )

@patch("agents.memo_generation.module_01_document_plan.get_run_paths")
def test_module_01_full_data(mock_get_paths, tmp_path, mock_run_id_m01, mock_pp_result_full):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{mock_run_id_m01}.jsonl",
        "CHROMADB_DIR_PATH": tmp_path / "chromadb"
    }
    
    # Mock data
    memo_data = {
        "ingestion": {
            "field_coverage_summary": {"fields_missing": 0},
            "missing_critical_fields": []
        },
        "analysis": {
            "earnings_quality_label": "GOOD",
            "anomaly_flags": {"critical": 0, "high": 1}
        },
        "risk": {
            "COMPOSITE_RISK": {"investment_stance": "PROCEED"}
        }
    }
    
    db_tables = {
        "trading_comps": pd.DataFrame([{"symbol": "A"}, {"symbol": "B"}, {"symbol": "C"}]), # 3 rows -> HIGH conf
        "news_sentiment": pd.DataFrame([{"id": i} for i in range(10)]), # >5 rows -> HIGH conf
        "risk_evidence": pd.DataFrame([{"id": i} for i in range(15)]) # >10 rows -> HIGH conf
    }
    
    module = DocumentPlanModule("AAPL", mock_pp_result_full, memo_data, db_tables)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.template_variant == "STANDARD"
    assert result.tone_profile == "PROCEED"
    assert result.data_confidence.executive_summary == "HIGH"
    assert result.data_confidence.financial_analysis == "HIGH"
    assert result.data_confidence.sector_benchmarking == "HIGH"
    
    # Section Plan
    assert result.section_plan.financial_analysis.depth == "STANDARD"
    assert result.section_plan.sector_benchmarking.depth == "STANDARD"
    assert result.section_plan.risk_assessment.depth == "STANDARD"

@patch("agents.memo_generation.module_01_document_plan.get_run_paths")
def test_module_01_limited_data(mock_get_paths, tmp_path, mock_run_id_m01, mock_pp_result_limited):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{mock_run_id_m01}.jsonl",
        "CHROMADB_DIR_PATH": tmp_path / "chromadb"
    }
    
    # Mock data with missing fields and bad financials
    memo_data = {
        "ingestion": {
            "field_coverage_summary": {"fields_missing": 6}, # Forces LOW conf, LIMITED_DATA
            "missing_critical_fields": ["revenue"]
        },
        "analysis": {
            "earnings_quality_label": "POOR", # Forces DEEP depth
            "anomaly_flags": {"critical": 2, "high": 2}
        },
        "risk": None
    }
    
    db_tables = {}
    
    module = DocumentPlanModule("AAPL", mock_pp_result_limited, memo_data, db_tables)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.template_variant == "LIMITED_DATA"
    assert "FINANCIAL_DATA_LIMITED" in result.template_sub_flags
    assert "MARKET_INTEL_UNAVAILABLE" in result.template_sub_flags
    assert result.tone_profile == "ENHANCED_DD" # Forced by lack of risk
    
    assert result.data_confidence.financial_analysis == "LOW"
    assert result.data_confidence.sector_benchmarking == "UNAVAILABLE"
    
    # Section Plan
    assert result.section_plan.financial_analysis.depth == "DEEP" # POOR label overrides LOW confidence
    assert result.section_plan.financial_analysis.target_words == 1200
    assert result.section_plan.sector_benchmarking.depth == "UNAVAILABLE"
    assert result.section_plan.risk_assessment.depth == "UNAVAILABLE"

@patch("agents.memo_generation.module_01_document_plan.get_run_paths")
def test_module_01_deal_breaker(mock_get_paths, tmp_path, mock_run_id_m01, mock_pp_result_full):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{mock_run_id_m01}.jsonl",
        "CHROMADB_DIR_PATH": tmp_path / "chromadb"
    }
    
    memo_data = {
        "ingestion": {},
        "analysis": {},
        "risk": {
            "DEAL_BREAKER_STATUS": {"triggered": 1},
            "COMPOSITE_RISK": {"investment_stance": "AVOID"}
        }
    }
    db_tables = {}
    
    module = DocumentPlanModule("AAPL", mock_pp_result_full, memo_data, db_tables)
    result = module.run()
    
    assert result.template_variant == "DEAL_BREAKER_ALERT"
    assert result.tone_profile == "AVOID"
    assert result.section_plan.risk_assessment.depth == "DEEP"
    assert result.section_plan.risk_assessment.target_words == 1600
