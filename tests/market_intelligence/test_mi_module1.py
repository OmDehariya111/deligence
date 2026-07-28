import json
import pytest
import sys
from unittest.mock import patch, MagicMock

# Mock before importing agent
sys.modules["chromadb"] = MagicMock()
sys.modules["litellm"] = MagicMock()
sys.modules["fastmcp"] = MagicMock()

from config.paths import get_run_paths
from schemas.pydantic_models import MarketIntelContext, PeerInfo
from agents.market_intelligence.module1_named_competitors import NamedCompetitorIdentifier

@pytest.fixture
def mock_context(tmp_path, monkeypatch):
    ticker = "AAPL"
    run_id = f"{ticker}_20260705_120000"
    
    monkeypatch.setattr("config.paths.OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr("config.paths.LOGS_DIR", tmp_path / "logs")
    
    paths = get_run_paths(ticker, run_id)
    paths["AUDIT_LOG_PATH"].parent.mkdir(parents=True, exist_ok=True)
    paths["CHROMADB_DIR_PATH"].mkdir(parents=True, exist_ok=True)
    
    # Setup list B
    top_peers = [
        PeerInfo(cik="0000000001", entity_name="Microsoft Corporation", revenue=200000),
        PeerInfo(cik="0000000002", entity_name="Google LLC", revenue=150000),
        PeerInfo(cik="0000000003", entity_name="Amazon.com Inc.", revenue=300000)
    ]
    
    return MarketIntelContext(
        run_id=run_id,
        ticker=ticker,
        company_name="Apple Inc.",
        cik="0000320193",
        sic_code="3571",
        industry_name="Electronic Computers",
        fiscal_year_end_month=9,
        most_recent_fiscal_year=2023,
        is_sector_benchmark_partial=False,
        is_chromadb_reachable=True,
        top_peers=top_peers,
        target_ratios={"revenue": {"value": 350000}}
    )

@patch("agents.market_intelligence.module1_named_competitors.chromadb.PersistentClient")
@patch("agents.market_intelligence.module1_named_competitors.completion")
@patch("agents.market_intelligence.module1_named_competitors.get_company_tickers")
def test_deterministic_verification(mock_tickers, mock_completion, mock_chroma, mock_context):
    """Test Fix M-4: Hallucinated names are removed, valid names are kept."""
    # Mock SEC mapping
    mock_tickers.return_value = json.dumps({
        "0": {"cik_str": 1, "ticker": "MSFT", "title": "Microsoft Corporation"},
        "1": {"cik_str": 2, "ticker": "GOOGL", "title": "Google LLC"},
        "2": {"cik_str": 4, "ticker": "META", "title": "Meta Platforms Inc."},
        "3": {"cik_str": 3, "ticker": "AMZN", "title": "Amazon.com Inc."}
    })
    
    # Mock Chroma
    mock_collection = MagicMock()
    mock_chroma.return_value.get_collection.return_value = mock_collection
    
    # 2 valid mentions, 1 hallucination (Tesla)
    mock_collection.query.return_value = {
        "documents": [["our main competitors are microsoft corporation and meta platforms. we also compete with google."]]
    }
    
    # Mock LLM returning valid and hallucinated names
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '["Microsoft", "Meta Platforms", "Tesla"]'
    mock_completion.return_value = mock_response
    
    identifier = NamedCompetitorIdentifier(mock_context)
    identifier.run()
    
    # Check SQLite DB
    with identifier.db_manager.get_connection() as conn:
        from sqlalchemy import text
        res = conn.execute(text("SELECT * FROM named_competitors")).fetchall()
        
    names = [row[1] for row in res]
    
    # Microsoft and Meta should be in, Tesla should NOT be in (hallucinated)
    # Amazon (from List B) should be in
    assert "Microsoft Corporation" in names
    assert "Meta Platforms Inc." in names
    assert "Tesla" not in names
    assert "Amazon.com Inc." in names

def test_degraded_chroma(mock_context):
    """Test when ChromaDB is unreachable."""
    mock_context.is_chromadb_reachable = False
    
    identifier = NamedCompetitorIdentifier(mock_context)
    
    with patch("agents.market_intelligence.module1_named_competitors.get_company_tickers") as mock_tickers:
        mock_tickers.return_value = json.dumps({
            "0": {"cik_str": 1, "ticker": "MSFT", "title": "Microsoft Corporation"},
            "1": {"cik_str": 2, "ticker": "GOOGL", "title": "Google LLC"},
            "2": {"cik_str": 3, "ticker": "AMZN", "title": "Amazon.com Inc."}
        })
        identifier.run()
        
    with identifier.db_manager.get_connection() as conn:
        from sqlalchemy import text
        res = conn.execute(text("SELECT selection_method FROM named_competitors")).fetchall()
        
    # All should be SIC_TOP_REVENUE since List A is empty
    assert all(r[0] == "SIC_TOP_REVENUE" for r in res)
    assert len(res) == 3
