import pytest
import json
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

sys.modules["fastmcp"] = MagicMock()
sys.modules["litellm"] = MagicMock()
sys.modules["chromadb"] = MagicMock()

from config.paths import get_run_paths
from schemas.pydantic_models import MarketIntelContext
from agents.market_intelligence.module5_news_sentiment import NewsSentimentExtractor
from tools.sqlite_tools import DatabaseManager

@pytest.fixture
def mock_context(tmp_path, monkeypatch):
    ticker = "AAPL"
    run_id = f"{ticker}_20260705_120000"
    
    monkeypatch.setattr("config.paths.OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr("config.paths.LOGS_DIR", tmp_path / "logs")
    
    paths = get_run_paths(ticker, run_id)
    paths["AUDIT_LOG_PATH"].parent.mkdir(parents=True, exist_ok=True)
    paths["SQLITE_DB_PATH"].parent.mkdir(parents=True, exist_ok=True)
    paths["MI_SUMMARY_PATH"].parent.mkdir(parents=True, exist_ok=True)
    
    with open(paths["MI_SUMMARY_PATH"], "w") as f:
        json.dump({}, f)
    
    db = DatabaseManager(paths["SQLITE_DB_PATH"])
    from agents.market_intelligence.module1_named_competitors import get_named_competitors_table
    db.create_tables([get_named_competitors_table(db.metadata)])
    
    with db.get_connection() as conn:
        from sqlalchemy import text
        conn.execute(text("INSERT INTO named_competitors (ticker, company_name) VALUES ('MSFT', 'Microsoft')"))
        conn.execute(text("INSERT INTO named_competitors (ticker, company_name) VALUES ('GOOG', 'Alphabet')"))
        
    db.dispose()
    
    return MarketIntelContext(
        run_id=run_id,
        ticker=ticker,
        company_name="Apple Inc.",
        cik="0000320193",
        sic_code="3571",
        industry_name="Electronic Computers",
        fiscal_year_end_month=9,
        most_recent_fiscal_year=2025,
        is_sector_benchmark_partial=False,
        is_chromadb_reachable=True,
        top_peers=[],
        target_ratios={}
    )

@patch("agents.market_intelligence.module5_news_sentiment.get_company_news")
@patch("agents.market_intelligence.module5_news_sentiment.litellm")
def test_news_sentiment_extractor(mock_litellm, mock_get_news, mock_context):
    mock_litellm.completion.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="Mocked Narrative"))])
    
    def side_effect_get_news(query, from_date, to_date):
        today = datetime.now()
        
        # Target chunk 1 (0-30 days)
        if "Apple" in query and from_date == (today - timedelta(days=30)).strftime("%Y-%m-%d"):
            return json.dumps({
                "articles": [
                    {
                        "headline": "Apple faces DOJ antitrust suit",
                        "description": "The DOJ has filed a massive lawsuit against Apple.",
                        "source_name": "Reuters",
                        "published_date": (today - timedelta(days=10)).strftime("%Y-%m-%d"),
                        "url": "http://test.com/1"
                    }
                ],
                "quota_exhausted": False,
                "served_from_cache": True
            })
            
        # Target chunk 2 (30-60 days)
        if "Apple" in query and from_date == (today - timedelta(days=60)).strftime("%Y-%m-%d"):
            return json.dumps({
                "articles": [
                    {
                        "headline": "Apple launches new iPhone",
                        "description": "It is great.",
                        "source_name": "TechCrunch",
                        "published_date": (today - timedelta(days=45)).strftime("%Y-%m-%d"),
                        "url": "http://test.com/2"
                    }
                ],
                "quota_exhausted": False,
                "served_from_cache": True
            })
            
        # Target chunk 3 (60-90 days) - Quota Exhausted!
        if "Apple" in query and from_date == (today - timedelta(days=90)).strftime("%Y-%m-%d"):
            return json.dumps({"articles": [], "quota_exhausted": True})
            
        # Competitors batch
        if "Microsoft" in query or "Alphabet" in query:
            return json.dumps({
                "articles": [
                    {
                        "headline": "Microsoft and Alphabet announce AI partnership",
                        "description": "Big news for AI.",
                        "source_name": "Verge",
                        "published_date": (today - timedelta(days=5)).strftime("%Y-%m-%d"),
                        "url": "http://test.com/3"
                    }
                ],
                "quota_exhausted": False,
                "served_from_cache": False
            })
            
        # Sector
        if "Electronic Computers" in query or "3571" in query:
            return json.dumps({"articles": [], "quota_exhausted": False})
            
        return json.dumps({"articles": [], "quota_exhausted": False})
        
    mock_get_news.side_effect = side_effect_get_news
    
    extractor = NewsSentimentExtractor(mock_context)
    extractor.run()
    
    with extractor.db_manager.get_connection() as conn:
        from sqlalchemy import text
        rows = conn.execute(text("SELECT * FROM news_sentiment")).fetchall()
        cols = [c[1] for c in conn.execute(text("PRAGMA table_info(news_sentiment)")).fetchall()]
        dicts = [dict(zip(cols, r)) for r in rows]
        
    # We expect:
    # 1 for Apple (DOJ suit)
    # 1 for Apple (iPhone launch)
    # 1 for Apple (Fallback for 60-90 days)
    # 2 for Competitor Batch (1 assigned to MSFT, 1 assigned to GOOG because both names are in headline)
    # 0 for sector
    # Total = 5
    
    assert len(dicts) == 5
    
    # Check DOJ Crisis Flag
    doj = next(d for d in dicts if "antitrust suit" in d["headline"].lower() or "antitrust suit" in d["description"].lower())
    assert doj["crisis_flag"] == 1
    assert doj["crisis_type"] == "MAJOR_LAWSUIT"
    assert doj["vader_label"] in ["NEGATIVE", "NEUTRAL"] 
    
    # Check fallback
    fallback = next(d for d in dicts if d["retrieval_source"] == "WEB_SEARCH_FALLBACK")
    assert fallback["ticker"] == "AAPL"
    
    # Check batch splitting
    msft = next((d for d in dicts if d["ticker"] == "MSFT"), None)
    goog = next((d for d in dicts if d["ticker"] == "GOOG"), None)
    assert msft is not None
    assert goog is not None
    assert msft["headline"] == "Microsoft and Alphabet announce AI partnership"
    assert goog["headline"] == "Microsoft and Alphabet announce AI partnership"
    
    # Check trend logic (iPhone was + / DOJ is -)
    # iPhone is in 30-60 (Window 2), DOJ is in 0-30 (Window 3). 
    # VADER should be lower in W3.
    # We should have written it to JSON context.
    paths = get_run_paths(mock_context.ticker, mock_context.run_id)
    with open(paths["MI_SUMMARY_PATH"], "r") as f:
        ctx = json.load(f)
    assert ctx["sentiment_narrative"] == "Mocked Narrative"
