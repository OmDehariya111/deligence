"""
Module:  module3_live_market_data.py
Agent:   Market Intelligence Agent
Purpose: Fetch current market data (price, valuation multiples, analyst coverage,
         earnings surprises) for the target company and its named competitors
         via MCP market-data-server.
Inputs:  MarketIntelContext, named_competitors table, competitor_ltm_financials table.
Outputs: Writes to `competitor_market_data` SQLite table.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import Column, Float, Integer, MetaData, String, Table, text

from config.paths import get_run_paths
from utils.mcp_client import call_mcp_tool_sync
from schemas.pydantic_models import MarketIntelContext
from tools.sqlite_tools import DatabaseManager
from utils.audit_logger import log_audit_event

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Table definition
# ---------------------------------------------------------------------------

def get_market_data_table(metadata: MetaData) -> Table:
    """
    # SQLite Database me `competitor_market_data` table ki definition hai.
    # Isme sabhi companies (target + competitors) ka live stock market data save hoga.
    """
    return Table(
        "competitor_market_data",
        metadata,
        Column("ticker", String, primary_key=True),
        Column("current_price", Float, nullable=True),
        # --- BUG 1 FIXED (Market Cap Data Type) ---
        # Integer ki jagah Float kar diya gaya hai kyunki badi companies ($3 Trillion) 
        # ka data aksar decimals (floats) me aa sakta hai jisse truncate error aa sakta tha.
        Column("market_cap", Float, nullable=True),
        Column("enterprise_value", Float, nullable=True),
        Column("ytd_return_pct", Float, nullable=True),
        Column("one_year_return_pct", Float, nullable=True),
        Column("fifty_two_week_high", Float, nullable=True),
        Column("fifty_two_week_low", Float, nullable=True),
        Column("beta", Float, nullable=True),
        Column("shares_outstanding", Integer, nullable=True),
        Column("analyst_consensus_rating", Float, nullable=True),
        Column("analyst_price_target", Float, nullable=True),
        Column("num_analysts_covering", Integer, nullable=True),
        Column("short_interest_pct", Float, nullable=True),
        Column("institutional_ownership", Float, nullable=True),
        Column("earn_surp_q1_pct", Float, nullable=True),
        Column("earn_surp_q2_pct", Float, nullable=True),
        Column("earn_surp_q3_pct", Float, nullable=True),
        Column("earn_surp_q4_pct", Float, nullable=True),
        Column("data_date", String),
        extend_existing=True,
    )


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class LiveMarketDataExtractor:
    """Fetches live market data for target + competitors and persists to SQLite.
    
    # Ye main class hai jo sabhi tickers ka live data fetch karne ka logic handle karti hai.
    """

    def __init__(self, context: MarketIntelContext):
        self.context = context
        self.paths = get_run_paths(context.ticker, context.run_id)
        # Database connection setup
        self.db_manager = DatabaseManager(self.paths["SQLITE_DB_PATH"])
        self.db_manager.create_tables(
            [get_market_data_table(self.db_manager.metadata)]
        )

    # ------------------------------------------------------------------
    # MCP helpers (each returns a dict or {} on failure)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_mcp_response(raw) -> dict:
        """Safely parse an MCP response into a dict.
        
        # Ye helper function MCP tool ke string response ko Python dictionary (JSON) me badalta hai.
        # Agar error aaye (json kharab ho), toh empty dict {} return karta hai taaki code crash na ho.
        """
        try:
            return json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (json.JSONDecodeError, TypeError):
            return {}

    def _fetch_market_snapshot(self, ticker: str) -> dict:
        """
        # Ye function Market Data Server (MCP) se current stock price, market cap, 
        # aur 52-week highs/lows fetch karta hai.
        """
        raw = call_mcp_tool_sync(
            "mcp_servers/market_data_server.py",
            "get_market_snapshot",
            {"ticker": ticker},
        )
        return self._parse_mcp_response(raw)

    def _fetch_analyst_data(self, ticker: str) -> dict:
        """
        # Ye function Analysts ki rating (buy/sell), price targets, 
        # aur short interest fetch karta hai.
        """
        raw = call_mcp_tool_sync(
            "mcp_servers/market_data_server.py",
            "get_analyst_data",
            {"ticker": ticker},
        )
        return self._parse_mcp_response(raw)

    def _fetch_earnings_surprise(self, ticker: str) -> dict:
        """
        # Ye function fetch karta hai ki pichle 4 quarters me company ne kitna profit 
        # "surprise" kiya (market expectations se kitna behtar perform kiya).
        """
        raw = call_mcp_tool_sync(
            "mcp_servers/market_data_server.py",
            "get_earnings_surprise_history",
            {"ticker": ticker},
        )
        return self._parse_mcp_response(raw)

    # ------------------------------------------------------------------
    # Enterprise-value computation
    # ------------------------------------------------------------------

    def _get_net_debt(self, ticker: str) -> float | None:
        """Read latest_net_debt for *ticker* from competitor_ltm_financials.
        
        # Enterprise value nikalne ke liye company ki udhaari (Net Debt) chahiye.
        # Ye function Module 2 ke banaye hue `competitor_ltm_financials` table se net debt padhta hai.
        """
        try:
            with self.db_manager.get_connection() as conn:
                row = conn.execute(
                    text(
                        "SELECT latest_net_debt FROM competitor_ltm_financials "
                        "WHERE ticker = :ticker"
                    ),
                    {"ticker": ticker},
                ).fetchone()
                if row and row[0] is not None:
                    return float(row[0])
        except Exception as exc:
            logger.debug(
                "Could not read net debt for %s: %s", ticker, exc
            )
        return None

    @staticmethod
    def _compute_enterprise_value(
        market_cap: float | None, net_debt: float | None
    ) -> float | None:
        """
        # Enterprise Value = Market Cap + Net Debt
        # Agar dono values hain, toh calculate karta hai, warna None return karta hai.
        """
        if market_cap is not None and net_debt is not None:
            return float(market_cap) + float(net_debt)
        return None

    # ------------------------------------------------------------------
    # Collect tickers
    # ------------------------------------------------------------------

    def _get_tickers(self) -> list[str]:
        """Return a deduplicated list of tickers (target first, then peers).
        
        # Target company aur uske competitors ke tickers ki list banata hai SQLite se.
        """
        tickers: list[str] = [self.context.ticker]
        try:
            with self.db_manager.get_connection() as conn:
                rows = conn.execute(
                    text("SELECT ticker FROM named_competitors")
                ).fetchall()
                for row in rows:
                    t = row[0]
                    if t and t not in tickers:
                        tickers.append(t)
        except Exception as exc:
            logger.warning(
                "Could not read named_competitors: %s", exc
            )
        return tickers

    # ------------------------------------------------------------------
    # Build a single row for one ticker
    # ------------------------------------------------------------------

    def _build_row(self, ticker: str) -> dict:
        """Fetch all three MCP endpoints for *ticker* and merge into one row.
        
        # Ek ticker (company) ke liye teeno APIs ko call karke data ek row me jodata hai.
        """
        row: dict = {"ticker": ticker}
        data_date = None

        # --- A. Market Snapshot ---
        snap = self._fetch_market_snapshot(ticker)
        row["current_price"] = snap.get("current_price")
        row["market_cap"] = snap.get("market_cap")
        row["fifty_two_week_high"] = snap.get("fifty_two_week_high")
        row["fifty_two_week_low"] = snap.get("fifty_two_week_low")
        row["beta"] = snap.get("beta")
        row["shares_outstanding"] = snap.get("shares_outstanding")
        row["ytd_return_pct"] = snap.get("ytd_return_pct")
        row["one_year_return_pct"] = snap.get("one_year_return_pct")
        if snap.get("data_date"):
            data_date = snap["data_date"]

        # --- B. Analyst Data ---
        analyst = self._fetch_analyst_data(ticker)
        row["analyst_consensus_rating"] = analyst.get("analyst_consensus_rating")
        row["analyst_price_target"] = analyst.get("analyst_price_target")
        row["num_analysts_covering"] = analyst.get("num_analysts_covering")
        row["short_interest_pct"] = analyst.get("short_interest_pct")
        row["institutional_ownership"] = analyst.get("institutional_ownership")
        if analyst.get("data_date"):
            data_date = analyst["data_date"]

        # --- C. Earnings Surprise History ---
        earnings = self._fetch_earnings_surprise(ticker)
        quarters = earnings.get("quarters", [])
        # Map last 4 quarters (most recent first) to q1..q4
        # Pichle 4 quarters ka data columns (q1 se q4) me alag-alag daalta hai
        for i in range(4):
            key = f"earn_surp_q{i + 1}_pct"
            if i < len(quarters):
                row[key] = quarters[i].get("surprise_pct")
            else:
                row[key] = None
        if earnings.get("data_date"):
            data_date = earnings["data_date"]

        # --- D. Enterprise Value ---
        # Module 2 ka debt nikal kar live market cap se jodta hai
        net_debt = self._get_net_debt(ticker)
        row["enterprise_value"] = self._compute_enterprise_value(
            row.get("market_cap"), net_debt
        )

        # Fallback data_date to current UTC date if none returned
        row["data_date"] = data_date or datetime.now(timezone.utc).strftime(
            "%Y-%m-%d"
        )

        return row

    # ------------------------------------------------------------------
    # Persist rows
    # ------------------------------------------------------------------

    def _write_rows(self, rows: list[dict]) -> None:
        """
        # Ek saath saari rows ko `competitor_market_data` table me INSERT karta hai.
        """
        insert_sql = """
            INSERT OR REPLACE INTO competitor_market_data
            (ticker, current_price, market_cap, enterprise_value,
             ytd_return_pct, one_year_return_pct,
             fifty_two_week_high, fifty_two_week_low,
             beta, shares_outstanding,
             analyst_consensus_rating, analyst_price_target,
             num_analysts_covering, short_interest_pct,
             institutional_ownership,
             earn_surp_q1_pct, earn_surp_q2_pct,
             earn_surp_q3_pct, earn_surp_q4_pct,
             data_date)
            VALUES
            (:ticker, :current_price, :market_cap, :enterprise_value,
             :ytd_return_pct, :one_year_return_pct,
             :fifty_two_week_high, :fifty_two_week_low,
             :beta, :shares_outstanding,
             :analyst_consensus_rating, :analyst_price_target,
             :num_analysts_covering, :short_interest_pct,
             :institutional_ownership,
             :earn_surp_q1_pct, :earn_surp_q2_pct,
             :earn_surp_q3_pct, :earn_surp_q4_pct,
             :data_date)
        """
        with self.db_manager.get_connection() as conn:
            for row in rows:
                conn.execute(text(insert_sql), row)

    # ------------------------------------------------------------------
    # run()
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Orchestrate live market data extraction for all tickers.
        
        # Ye is module ka main function hai jo baaki sabhi functions ko sequence me call karta hai.
        """
        
        # --- BUG 2 FIXED: NEW AUDIT LOGGING STANDARD ---
        # Ab hum utils.audit_logger ke log_audit_event ka use karte hain.
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_3_LIVE_MARKET_DATA",
            status="STARTED",
            summary="Beginning live market data extraction from MCP APIs."
        )

        # Clear existing market data to prevent stale rows (Purana kachra saaf karna)
        with self.db_manager.get_connection() as conn:
            try:
                conn.execute(text("DELETE FROM competitor_market_data"))
            except Exception as e:
                logger.warning(f"Failed to clear competitor_market_data: {e}")

        # Tickers laao
        tickers = self._get_tickers()
        logger.info(
            "Module 3: fetching market data for %d ticker(s): %s",
            len(tickers),
            tickers,
        )

        rows: list[dict] = []
        success_count = 0
        failed_tickers = []

        # Har ticker ke liye row build karo (APIs call hongi)
        for ticker in tickers:
            try:
                row = self._build_row(ticker)
                rows.append(row)
                success_count += 1
                logger.info("Fetched market data for %s", ticker)
            except Exception as exc:
                failed_tickers.append(ticker)
                logger.error(
                    "Failed to fetch market data for %s: %s",
                    ticker,
                    exc,
                    exc_info=True,
                )

        # Agar rows mili hain toh Database me insert karo
        if rows:
            self._write_rows(rows)

        self.db_manager.dispose()
        
        # Status aur summary ko detailed aur transparent banate hain
        status = "COMPLETED"
        
        if failed_tickers:
            summary = f"Live market data fetched successfully for {success_count}/{len(tickers)} tickers. Failed for: {', '.join(failed_tickers)}."
        else:
            summary = f"Live market data fetched successfully for all {success_count}/{len(tickers)} tickers. No failures."
        
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_3_LIVE_MARKET_DATA",
            status=status,
            summary=summary
        )
        logger.info(summary)
