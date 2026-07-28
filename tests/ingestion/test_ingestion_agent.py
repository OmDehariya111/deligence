import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from agents.ingestion.ingestion_agent import IngestionAgent

@patch('agents.ingestion.phase1_company_identity.run_phase1')
@patch('agents.ingestion.phase2_text_processing.run_phase2')
@patch('agents.ingestion.phase3_user_file.run_phase3')
@patch('agents.ingestion.phase4_financial_data.run_phase4')
@patch('agents.ingestion.phase5_validation.run_phase5')
@patch('agents.ingestion.phase6_normalization.run_phase6')
@patch('agents.ingestion.phase7_final_output.run_phase7')
@patch('agents.ingestion.ingestion_agent.log_audit_event')
def test_ingestion_agent_success(
    mock_log, mock_p7, mock_p6, mock_p5, mock_p4, mock_p3, mock_p2, mock_p1, tmp_path
):
    mock_p1.return_value = "p1_res"
    mock_p4.return_value = "p4_res"
    mock_p5.return_value = "p5_res"
    
    agent = IngestionAgent(ticker="AAPL", run_id="test_run")
    # Patch paths to use tmp_path
    agent.paths["AUDIT_LOG_PATH"] = tmp_path / "audit.jsonl"
    agent.paths["INGESTION_SUMMARY_PATH"] = tmp_path / "summary.json"
    
    agent.run()
    
    mock_p1.assert_called_once()
    mock_p2.assert_called_once()
    mock_p3.assert_not_called() # No user file
    mock_p4.assert_called_once()
    mock_p5.assert_called_once()
    mock_p6.assert_called_once()
    mock_p7.assert_called_once()
    
    assert agent.module_status["phase_1_company_identity"] == "COMPLETED"
    assert agent.module_status["phase_3_user_file"] == "SKIPPED"


@patch('agents.ingestion.phase1_company_identity.run_phase1')
@patch('agents.ingestion.phase7_final_output.run_phase7')
def test_ingestion_agent_fatal_error(mock_p7, mock_p1, tmp_path):
    mock_p1.side_effect = Exception("API Down")
    
    agent = IngestionAgent(ticker="AAPL", run_id="test_run")
    agent.paths["AUDIT_LOG_PATH"] = tmp_path / "audit.jsonl"
    agent.paths["INGESTION_SUMMARY_PATH"] = tmp_path / "summary.json"
    
    agent.run()
    
    mock_p1.assert_called_once()
    mock_p7.assert_not_called() # Because phase5_result is None
    
    assert agent.module_status["phase_1_company_identity"] == "FAILED"
    assert agent.module_status["phase_4_financial_data"] == "NOT_STARTED"
    
    # Should write error summary JSON
    assert agent.paths["INGESTION_SUMMARY_PATH"].exists()
    content = agent.paths["INGESTION_SUMMARY_PATH"].read_text()
    assert "ERROR" in content
    assert "API Down" in content
