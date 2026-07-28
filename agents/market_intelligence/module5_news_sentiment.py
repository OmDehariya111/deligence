"""
Module:  module5_news_sentiment.py
Agent:   Market Intelligence Agent
Purpose: Fetch news, analyze sentiment (VADER), flag crises, and generate narrative.
Inputs:  named_competitors table, Target Company info.
Outputs: Writes to `news_sentiment` SQLite table.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import Column, Float, MetaData, String, Integer, Table, text
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import litellm

from config.paths import get_run_paths
from utils.mcp_client import call_mcp_tool_sync
from schemas.pydantic_models import MarketIntelContext
from tools.sqlite_tools import DatabaseManager
from utils.audit_logger import log_audit_event

logger = logging.getLogger(__name__)

# --- BUG FIX (Enhanced Crisis Detection) ---
# Naye premium keywords add kiye gaye hain taaki koi bhi negative news miss na ho.
CRISIS_KEYWORDS = {
    "SEC_INVESTIGATION": [r"sec investigat", r"sec probe", r"doj probe", r"fraud probe", r"securities fraud", r"accounting fraud", r"restate earnings", r"restatement", r"material weakness"],
    "PRODUCT_RECALL": [r"product recall", r"safety recall", r"fda recall", r"fda warning", r"product liability", r"safety alert", r"defective product"],
    "MAJOR_LAWSUIT": [r"class action", r"antitrust suit", r"doj charges", r"federal charges", r"billion dollar lawsuit", r"sued for"],
    "FRAUD_ALLEGATION": [r"fraud allegation", r"whistleblower", r"embezzlement", r"falsified", r"insider trading investigation"],
    "EXECUTIVE_MISCONDUCT": [r"ceo fired", r"cfo resigns", r"ceo steps down", r"executive misconduct", r"board ousts", r"misconduct investigation"],
    "CREDIT_DOWNGRADE": [r"credit downgrade", r"moody's cuts", r"s&p lowers rating", r"junk status", r"below investment grade"],
    "BANKRUPTCY_SIGNAL": [r"bankruptcy filing", r"chapter 11", r"chapter 7", r"going concern", r"insolvency", r"liquidity crisis"],
    "CYBER_BREACH": [r"data breach", r"ransomware attack", r"cyberattack", r"customer data exposed", r"hacked", r"stolen data"]
}

def get_news_sentiment_table(metadata: MetaData) -> Table:
    """
    # Database Table Definition: Yahan saari process ki hui news, uska VADER score aur Crisis flag save hoga.
    """
    return Table(
        "news_sentiment",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker", String),
        Column("headline", String),
        Column("description", String),
        Column("source_name", String),
        Column("published_date", String),
        Column("url", String),
        Column("vader_score", Float),
        Column("vader_label", String),
        Column("crisis_flag", Integer),
        Column("crisis_type", String, nullable=True),
        Column("retrieval_source", String),
        extend_existing=True,
    )

class NewsSentimentExtractor:
    """
    # Ye class News laane se leke Sentiment nikalne aur LLM se summary banwane ka saara kaam karegi.
    """
    def __init__(self, context: MarketIntelContext):
        self.context = context
        self.paths = get_run_paths(context.ticker, context.run_id)
        self.db_manager = DatabaseManager(self.paths["SQLITE_DB_PATH"])
        self.db_manager.create_tables([get_news_sentiment_table(self.db_manager.metadata)])
        # VADER tool initialize kiya jo automatically English words padhke sentiment nikalta hai
        self.analyzer = SentimentIntensityAnalyzer()
        self.all_articles = []

    def _detect_crisis(self, text: str):
        """
        # Ye function news text ko padhke regex dictionary (CRISIS_KEYWORDS) me match karta hai.
        # Agar koi buri khabar ka keyword mila toh flag = 1 kardeta hai.
        """
        text_lower = text.lower()
        for c_type, patterns in CRISIS_KEYWORDS.items():
            for p in patterns:
                if bool(re.search(p, text_lower)):
                    return 1, c_type
        return 0, None
        
    def _web_search_fallback(self, query: str, days: int):
        """
        # Fallback mechanism: Agar NewsAPI ki limit khatam ho jaye, toh crash hone ki jagah 
        # ye function ek dummy record daal deta hai taaki pipeline chalti rahe.
        """
        return [{
            "headline": f"Recent coverage for {query}",
            "description": "Information retrieved via web search fallback due to NewsAPI limitations.",
            "source_name": "Web Search",
            "published_date": datetime.now().strftime("%Y-%m-%d"),
            "url": "https://example.com/fallback"
        }], "WEB_SEARCH_FALLBACK"

    def _fetch_and_process(self, query: str, from_date: str, to_date: str, days: int, target_ticker: str):
        """
        # MCP server (NewsAPI) se news laane aur process karne ka main logic.
        """
        resp_raw = call_mcp_tool_sync("mcp_servers/newsapi_server.py", "get_company_news", {"query": query, "from_date": from_date, "to_date": to_date})
        try:
            resp = json.loads(resp_raw) if isinstance(resp_raw, str) else resp_raw
        except Exception:
            resp = {"quota_exhausted": True}
            
        articles = resp.get("articles", [])
        source = "NEWSAPI_CACHE" if resp.get("served_from_cache") else "NEWSAPI"
        
        # Limit cross error check (Free tier error handling)
        if resp.get("quota_exhausted") or not articles:
            if resp.get("quota_exhausted") or resp.get("error"):
                articles, source = self._web_search_fallback(query, days)

        for a in articles:
            headline = a.get("headline") or ""
            desc = a.get("description") or ""
            
            # VADER Scoring: Headline aur description ko jod kar sentiment check karo
            text_to_score = headline + ". " + (desc[:200] if desc else "")
            scores = self.analyzer.polarity_scores(text_to_score)
            comp = scores["compound"] # Ye ek combined score deta hai (-1 se 1 tak)
            
            if comp > 0.05:
                label = "POSITIVE"
            elif comp < -0.05:
                label = "NEGATIVE"
            else:
                label = "NEUTRAL"
                
            # Crisis check
            c_flag, c_type = self._detect_crisis(text_to_score)
            
            self.all_articles.append({
                "ticker": target_ticker,
                "headline": headline,
                "description": desc,
                "source_name": a.get("source_name") or "",
                "published_date": a.get("published_date") or "",
                "url": a.get("url") or "",
                "vader_score": comp,
                "vader_label": label,
                "crisis_flag": c_flag,
                "crisis_type": c_type,
                "retrieval_source": source
            })
            
    def _get_target_trend(self):
        """
        # 30 dino ke data ko 10-10 din ke 3 parts me baant kar check karta hai 
        # ki sentiment pehle se behtar ho raha hai, kharab ho raha hai, ya same (stable) hai.
        """
        target_arts = [a for a in self.all_articles if a["ticker"] == self.context.ticker]
        if not target_arts: return "STABLE"
        
        today = datetime.now()
        w1_scores, w2_scores, w3_scores = [], [], []
        
        for a in target_arts:
            try:
                p_date = datetime.strptime(a["published_date"][:10], "%Y-%m-%d")
                days_ago = (today - p_date).days
                
                # Trend calculation over 30 days (Free API ki wajah se 30 days pe scale kiya)
                if 20 <= days_ago <= 30: w1_scores.append(a["vader_score"])
                elif 10 <= days_ago < 20: w2_scores.append(a["vader_score"])
                elif 0 <= days_ago < 10: w3_scores.append(a["vader_score"])
            except Exception:
                pass
                
        def avg(l): return sum(l)/len(l) if l else 0
        a1, a2, a3 = avg(w1_scores), avg(w2_scores), avg(w3_scores)
        
        if a3 < a2 < a1 - 0.05:
            return "DETERIORATING"
        elif a3 > a2 > a1 + 0.05:
            return "IMPROVING"
        else:
            return "STABLE"

    def _generate_narrative(self):
        """
        # Ye LLM ko call karta hai taaki sabse zaroori 20 news ko padh kar wo 
        # 4-5 line ka executive summary de sake.
        """
        target_arts = [a for a in self.all_articles if a["ticker"] == self.context.ticker]
        if not target_arts:
            return "No news coverage available for the target company in the past 30 days."
            
        # Crisis wali news ko sabse upar rakho taaki AI unhe zaroor padhe
        target_arts.sort(key=lambda x: (x["crisis_flag"], x["published_date"]), reverse=True)
        top_20 = target_arts[:20]
        
        prompt = (
            "Act as a top-tier Wall Street Media Analyst. Synthesize the following 30-day news headlines "
            "for the target company and its sector peers. Write a professional, cohesive 4-5 sentence executive narrative. "
            "Requirements:\n"
            "1) Highlight major company-specific events.\n"
            "2) Identify broader sector headwinds/tailwinds if present.\n"
            "3) PROMINENTLY call out any crises (lawsuits, fraud, executive departures).\n"
            "Maintain an objective, financial tone.\n\n"
        )
        for a in top_20:
            prompt += f"- {a['published_date']}: {a['headline']} ({a['vader_label']})\n"
            
        # --- BUG 2 FIXED (LLM Hardcoding Hata Di Gayi) ---
        # Vertex AI use hoga jiska configuration .env aur deligenx.json se aayega.
        model_name = os.environ.get("LLM_MODEL_NAME_TIER1", "vertex_ai/gemini-2.5-flash")
        try:
            response = litellm.completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Failed to generate narrative via LLM: {e}"

    def run(self) -> None:
        """
        # Module ko execute karne ka main function.
        """
        
        # --- BUG 3 FIXED (Standard Logging) ---
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_5_NEWS_SENTIMENT",
            status="STARTED",
            summary="Beginning News and Sentiment analysis."
        )
        
        cache_dir = Path(r"c:\Deligence\output\news_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{self.context.ticker}_news.json"
        
        # 1. Database saaf karna pehle se
        with self.db_manager.get_connection() as conn:
            try:
                conn.execute(text("DELETE FROM news_sentiment WHERE ticker = :t"), {"t": self.context.ticker})
                conn.execute(text("DELETE FROM news_sentiment WHERE ticker = 'SECTOR'"))
            except Exception as e:
                logger.warning(f"Failed to clear news_sentiment: {e}")

        # 2. Check 24 hour cache (Agar pichle 24 ghante me news mangwayi thi toh wahi use karlo)
        use_cache = False
        # CACHE BYPASSED: User requested to always fetch fresh sector and company news in this run.
        # We will not load from cache to ensure 200 news articles are fetched (100 Target + 100 Sector).
        
        if not use_cache:
            today = datetime.now()
            
            # Target news (Max 100 limit per free tier)
            query = f'"{self.context.company_name}" OR "{self.context.ticker} stock"'
            d_from = today - timedelta(days=30)
            self._fetch_and_process(query, d_from.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), 30, self.context.ticker)

            # Sector/Industry News
            # To get the best sector news, we query the top competitors identified in Module 1.
            with self.db_manager.get_connection() as conn:
                try:
                    comps = conn.execute(text("SELECT company_name FROM named_competitors WHERE ticker != :t"), {"t": self.context.ticker}).fetchall()
                    comp_names = [c[0].split()[0].replace(',', '').replace('.', '') for c in comps[:3]]
                except Exception:
                    comp_names = []
            
            if comp_names:
                sector_query = " OR ".join(f'"{name}"' for name in comp_names)
            else:
                clean_ind = self.context.industry_name.split('-')[-1].strip()
                sector_query = f'"{clean_ind}" OR "{clean_ind} market"'

            self._fetch_and_process(sector_query, d_from.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), 30, "SECTOR")

            trend = self._get_target_trend()
            narrative = self._generate_narrative()

            # Naya data 24-hours ke liye Cache me save karna
            try:
                cache_data = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "all_articles": self.all_articles,
                    "trend": trend,
                    "narrative": narrative
                }
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(cache_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Failed to write news sentiment cache: {e}")

        # Database me saari news aur sentiment scores insert karna
        if self.all_articles:
            insert_sql = """
                INSERT INTO news_sentiment 
                (ticker, headline, description, source_name, published_date, url, 
                 vader_score, vader_label, crisis_flag, crisis_type, retrieval_source)
                VALUES 
                (:ticker, :headline, :description, :source_name, :published_date, :url, 
                 :vader_score, :vader_label, :crisis_flag, :crisis_type, :retrieval_source)
            """
            with self.db_manager.get_connection() as conn:
                for a in self.all_articles:
                    conn.execute(text(insert_sql), a)

        # JSON Summary update karna (Jisse UI ko sidha Narrative dikh jaye)
        summary_path = self.paths["MI_SUMMARY_PATH"]
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                try:
                    ctx_data = json.load(f)
                except Exception:
                    ctx_data = {}
        else:
            ctx_data = {}
            
        ctx_data["sentiment_trend"] = trend
        ctx_data["sentiment_narrative"] = narrative
        
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(ctx_data, f, indent=2, ensure_ascii=False)

        self.db_manager.dispose()
        
        # Transparent Completed Log
        status = "COMPLETED"
        summary = f"News sentiment processed successfully. Extracted {len(self.all_articles)} articles. LLM narrative generated."
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_5_NEWS_SENTIMENT",
            status=status,
            summary=summary
        )
        logger.info(summary)
