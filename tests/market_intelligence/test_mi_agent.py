import pytest
import sys
from unittest.mock import patch, MagicMock

sys.modules["chromadb"] = MagicMock()
sys.modules["fastmcp"] = MagicMock()
sys.modules["litellm"] = MagicMock()

from agents.market_intelligence.market_intelligence_agent import MarketIntelligenceAgent

@patch("agents.market_intelligence.market_intelligence_agent.MarketIntelligenceSummarizer")
@patch("agents.market_intelligence.market_intelligence_agent.MarketRiskSignalGenerator")
@patch("agents.market_intelligence.market_intelligence_agent.IndustryMacroExtractor")
@patch("agents.market_intelligence.market_intelligence_agent.NewsSentimentExtractor")
@patch("agents.market_intelligence.market_intelligence_agent.CompsAndValuationGenerator")
@patch("agents.market_intelligence.market_intelligence_agent.LiveMarketDataExtractor")
@patch("agents.market_intelligence.market_intelligence_agent.LTMExtractor")
@patch("agents.market_intelligence.market_intelligence_agent.NamedCompetitorIdentifier")
@patch("agents.market_intelligence.market_intelligence_agent.MarketIntelPreProcessor")
def test_market_intelligence_agent_run(
    mock_preprocessor,
    mock_m1, mock_m2, mock_m3, mock_m4,
    mock_m5, mock_m6, mock_m7, mock_m8
):
    mock_context = MagicMock()
    mock_preprocessor.return_value.run.return_value = mock_context
    
    agent = MarketIntelligenceAgent("AAPL", "test_run_123")
    agent.run()
    
    # Verify preprocessor ran
    mock_preprocessor.assert_called_once_with("AAPL", "test_run_123")
    mock_preprocessor.return_value.run.assert_called_once()
    
    # Verify each module was instantiated with context and run
    modules = [mock_m1, mock_m2, mock_m3, mock_m4, mock_m5, mock_m6, mock_m7, mock_m8]
    for m in modules:
        m.assert_called_once_with(mock_context)
        m.return_value.run.assert_called_once()
