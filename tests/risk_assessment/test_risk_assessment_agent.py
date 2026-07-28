"""
Tests for the Risk Assessment Agent Orchestrator
"""

import pytest
from unittest.mock import patch, MagicMock
from agents.risk_assessment.risk_assessment_agent import RiskAssessmentAgent

@pytest.fixture
def agent():
    return RiskAssessmentAgent("TEST", "run123")

def test_successful_run(agent):
    with patch("agents.risk_assessment.risk_assessment_agent.RiskPreProcessor") as mock_pre, \
         patch("agents.risk_assessment.risk_assessment_agent.FinancialRiskScorer") as mock_m1, \
         patch("agents.risk_assessment.risk_assessment_agent.MarketRiskScorer") as mock_m2, \
         patch("agents.risk_assessment.risk_assessment_agent.OperationalRiskScorer") as mock_m3, \
         patch("agents.risk_assessment.risk_assessment_agent.LegalRiskScorer") as mock_m4, \
         patch("agents.risk_assessment.risk_assessment_agent.ManagementRiskScorer") as mock_m5, \
         patch("agents.risk_assessment.risk_assessment_agent.ESGRiskScorer") as mock_m6, \
         patch("agents.risk_assessment.risk_assessment_agent.DealBreakerDetector") as mock_m7, \
         patch("agents.risk_assessment.risk_assessment_agent.CompositeRiskScorer") as mock_m8, \
         patch("agents.risk_assessment.risk_assessment_agent.MitigationRecommender") as mock_m9, \
         patch("agents.risk_assessment.risk_assessment_agent.RiskAssessmentSummary") as mock_m10:
         
         pre_instance = mock_pre.return_value
         pre_instance.process.return_value = True
         
         agent.run()
         
         mock_m1.return_value.run.assert_called_once()
         mock_m9.return_value.run.assert_called_once()
         mock_m10.return_value.run.assert_called_once()

def test_halt_fatal_error(agent):
    with patch("agents.risk_assessment.risk_assessment_agent.RiskPreProcessor") as mock_pre, \
         patch("agents.risk_assessment.risk_assessment_agent.FinancialRiskScorer") as mock_m1, \
         patch("agents.risk_assessment.risk_assessment_agent.RiskAssessmentSummary") as mock_m10:
         
         pre_instance = mock_pre.return_value
         pre_instance.process.return_value = False
         
         agent.run()
         
         mock_m1.assert_not_called()
         
         mock_m10.return_value.run.assert_called_once()
