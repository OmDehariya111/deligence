"""
Module:  module4_comps_valuation.py
Agent:   Market Intelligence Agent
Purpose: Generate IB Comps Table and compute Implied Valuation (with outlier handling).
Inputs:  SQLite tables (competitor_ltm_financials, competitor_market_data, named_competitors).
Outputs: Writes to `trading_comps_table` and `implied_valuation` SQLite tables.
"""

import json
import logging
import statistics
from datetime import datetime, timezone
from sqlalchemy import Column, Float, MetaData, String, Table, Integer, text

from config.paths import get_run_paths
from schemas.pydantic_models import MarketIntelContext
from tools.sqlite_tools import DatabaseManager
from utils.audit_logger import log_audit_event

logger = logging.getLogger(__name__)

def get_comps_table(metadata: MetaData) -> Table:
    """
    # SQLite Database me `trading_comps_table` banane ke liye definition hai.
    # Ye table bilkul ek Investment Banking "Comps" excel sheet jaisi hoti hai jisme 
    # sabhi companies ke valuation multiples (Jaise P/E, EV/EBITDA) save hote hain.
    # Ise seedha Frontend UI par ek detailed table banakar User ko dikhaya ja sakta hai.
    """
    return Table(
        "trading_comps_table",
        metadata,
        Column("ticker", String, primary_key=True),
        Column("company_name", String),
        Column("period_label", String),
        Column("current_price", Float, nullable=True),
        Column("market_cap", Float, nullable=True),
        Column("enterprise_value", Float, nullable=True),
        Column("ytd_return_pct", Float, nullable=True),
        Column("beta", Float, nullable=True),
        Column("ltm_revenue", Float, nullable=True),
        Column("revenue_growth_pct", Float, nullable=True),
        Column("gross_margin", Float, nullable=True),
        Column("ebitda_margin", Float, nullable=True),
        Column("net_margin", Float, nullable=True),
        Column("fcf_margin", Float, nullable=True),
        Column("ev_revenue", Float, nullable=True),
        Column("ev_ebitda", Float, nullable=True),
        Column("ev_ebit", Float, nullable=True),
        Column("p_e", Float, nullable=True),
        Column("p_fcf", Float, nullable=True),
        Column("is_target", Integer),
        extend_existing=True,
    )

def get_implied_valuation_table(metadata: MetaData) -> Table:
    """
    # SQLite Database me `implied_valuation` banane ki definition hai.
    # Isme Target company ka 'sahi price' (Implied Stock Price) aur uski real current price
    # ke beech ka difference (premium/discount) save hota hai.
    """
    return Table(
        "implied_valuation",
        metadata,
        Column("method", String, primary_key=True),
        Column("peer_25p_multiple", Float, nullable=True),
        Column("peer_median_mult", Float, nullable=True),
        Column("peer_75p_multiple", Float, nullable=True),
        Column("target_metric", Float, nullable=True),
        Column("implied_ev_low", Float, nullable=True),
        Column("implied_ev_base", Float, nullable=True),
        Column("implied_ev_high", Float, nullable=True),
        Column("implied_eq_low", Float, nullable=True),
        Column("implied_eq_base", Float, nullable=True),
        Column("implied_eq_high", Float, nullable=True),
        Column("implied_ps_low", Float, nullable=True),
        Column("implied_ps_base", Float, nullable=True),
        Column("implied_ps_high", Float, nullable=True),
        Column("vs_current_price", Float, nullable=True),
        extend_existing=True,
    )

class CompsAndValuationGenerator:
    """
    # Ye main class target company aur uske peers (competitors) ke financial aur market data ko mila kar 
    # unka valuation analysis (Comparison) karti hai.
    """
    def __init__(self, context: MarketIntelContext):
        self.context = context
        self.paths = get_run_paths(context.ticker, context.run_id)
        self.db_manager = DatabaseManager(self.paths["SQLITE_DB_PATH"])
        self.db_manager.create_tables([
            get_comps_table(self.db_manager.metadata),
            get_implied_valuation_table(self.db_manager.metadata)
        ])

    def _get_percentile(self, lst: list, q: float) -> float | None:
        """
        # Ye math function hai jo 25th aur 75th percentile nikalta hai. 
        # Valuation me humein ek Low (25%) aur High (75%) range deni hoti hai.
        """
        if not lst:
            return None
        sorted_lst = sorted(lst)
        idx = (len(sorted_lst) - 1) * (q / 100.0)
        low = int(idx)
        high = min(low + 1, len(sorted_lst) - 1)
        diff = idx - low
        return sorted_lst[low] + diff * (sorted_lst[high] - sorted_lst[low])

    def _filter_outliers(self, values: list) -> list:
        """Exclude values > 3 standard deviations from mean, and negative/extreme multiples.
        
        # BAHUT IMPORTANT: Ye un companies ko average calculation se nikal deta hai 
        # jinke numbers abnormally high/low (outliers) ya negative hain taaki hamara Industry Average kharab na ho.
        """
        clean_vals = [v for v in values if v is not None and v > 0]
        if len(clean_vals) < 3:
            return clean_vals
        mean = sum(clean_vals) / len(clean_vals)
        try:
            # Standard Deviation nikal rahe hain
            stdev = statistics.stdev(clean_vals)
        except Exception:
            stdev = 0.0
        if stdev == 0.0:
            return clean_vals
        # Agar value average se 3 standard deviations bahar hai, toh usko filter kardo
        return [v for v in clean_vals if abs(v - mean) <= 3 * stdev]

    def run(self) -> None:
        # Naye logging standard ke hisab se duration track karne ke liye STARTED bheja gaya.
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_4_COMPS_AND_VALUATION",
            status="STARTED",
            summary="Building comps table and generating implied valuation math."
        )

        # Module 2 (Financials) aur Module 3 (Market Data) ke results ko database se padhna.
        financials = {}
        market_data = {}
        names = {}

        with self.db_manager.get_connection() as conn:
            try:
                res_fin = conn.execute(text("SELECT * FROM competitor_ltm_financials")).fetchall()
                # Col names lana taaki unhe dictionary me zip kar sakein
                keys_fin = conn.execute(text("PRAGMA table_info(competitor_ltm_financials)")).fetchall()
                col_names_fin = [k[1] for k in keys_fin]
                for r in res_fin:
                    financials[r[0]] = dict(zip(col_names_fin, r))

                res_mkt = conn.execute(text("SELECT * FROM competitor_market_data")).fetchall()
                keys_mkt = conn.execute(text("PRAGMA table_info(competitor_market_data)")).fetchall()
                col_names_mkt = [k[1] for k in keys_mkt]
                for r in res_mkt:
                    market_data[r[0]] = dict(zip(col_names_mkt, r))

                res_names = conn.execute(text("SELECT ticker, company_name FROM named_competitors")).fetchall()
                for r in res_names:
                    names[r[0]] = r[1]
                # Target company ko bhi manually naam assign karna
                names[self.context.ticker] = self.context.company_name
            except Exception as e:
                logger.error(f"Failed to fetch input tables for comps generator: {e}")

        # Comps Table ke records build karna
        records = []
        all_tickers = set(financials.keys()) | set(market_data.keys())
        
        for ticker in all_tickers:
            fin = financials.get(ticker, {})
            mkt = market_data.get(ticker, {})
            
            ltm_rev = fin.get("ltm_revenue")
            ltm_ebitda = fin.get("ltm_ebitda")
            ltm_opinc = fin.get("ltm_operating_inc")
            ltm_ni = fin.get("ltm_net_income")
            ltm_fcf = fin.get("ltm_fcf")
            
            mkt_cap = mkt.get("market_cap")
            ev = mkt.get("enterprise_value")

            # Valuation Multiples ki math: (Zero ya divide-by-zero errors handle kiye gaye hain)
            ev_rev = (ev / ltm_rev) if ev is not None and ltm_rev and ltm_rev > 0 else None
            ev_ebitda = (ev / ltm_ebitda) if ev is not None and ltm_ebitda and ltm_ebitda > 0 else None
            ev_ebit = (ev / ltm_opinc) if ev is not None and ltm_opinc and ltm_opinc > 0 else None
            p_e = (mkt_cap / ltm_ni) if mkt_cap is not None and ltm_ni and ltm_ni > 0 else None
            p_fcf = (mkt_cap / ltm_fcf) if mkt_cap is not None and ltm_fcf and ltm_fcf > 0 else None

            # Revenue Growth calculation
            prior_rev = fin.get("prior_fy_revenue")
            rev_growth = None
            if ltm_rev is not None and prior_rev and prior_rev > 0:
                rev_growth = ((ltm_rev - prior_rev) / prior_rev) * 100

            rec = {
                "ticker": ticker,
                "company_name": names.get(ticker, ticker),
                "period_label": "LTM",
                "current_price": mkt.get("current_price"),
                "market_cap": mkt_cap,
                "enterprise_value": ev,
                "ytd_return_pct": mkt.get("ytd_return_pct"),
                "beta": mkt.get("beta"),
                "ltm_revenue": ltm_rev,
                "revenue_growth_pct": rev_growth,
                "gross_margin": fin.get("ltm_gross_margin"),
                "ebitda_margin": fin.get("ltm_ebitda_margin"),
                "net_margin": fin.get("ltm_net_margin"),
                "fcf_margin": fin.get("ltm_fcf_margin"),
                "ev_revenue": ev_rev,
                "ev_ebitda": ev_ebitda,
                "ev_ebit": ev_ebit,
                "p_e": p_e,
                "p_fcf": p_fcf,
                "is_target": 1 if ticker == self.context.ticker else 0
            }
            records.append(rec)

        # Database me `trading_comps_table` ko overwrite karte hain
        with self.db_manager.get_connection() as conn:
            try:
                # Clear existing table first to prevent duplicate keys
                conn.execute(text("DELETE FROM trading_comps_table"))
                for rec in records:
                    conn.execute(
                        text("""
                            INSERT INTO trading_comps_table (
                                ticker, company_name, period_label, current_price, market_cap, enterprise_value,
                                ytd_return_pct, beta, ltm_revenue, revenue_growth_pct, gross_margin,
                                ebitda_margin, net_margin, fcf_margin, ev_revenue, ev_ebitda, ev_ebit, p_e, p_fcf, is_target
                            ) VALUES (
                                :ticker, :company_name, :period_label, :current_price, :market_cap, :enterprise_value,
                                :ytd_return_pct, :beta, :ltm_revenue, :revenue_growth_pct, :gross_margin,
                                :ebitda_margin, :net_margin, :fcf_margin, :ev_revenue, :ev_ebitda, :ev_ebit, :p_e, :p_fcf, :is_target
                            )
                        """),
                        rec
                    )
            except Exception as e:
                logger.error(f"Failed to save comps table: {e}")

        # Compute Sector Median and Mean (Target company ko include mat karo taaki industry avg saaf ho)
        peers = [r for r in records if r["ticker"] != self.context.ticker]
        
        numeric_cols = [
            "current_price", "market_cap", "enterprise_value", "ytd_return_pct", "beta", "ltm_revenue",
            "revenue_growth_pct", "gross_margin", "ebitda_margin", "net_margin", "fcf_margin",
            "ev_revenue", "ev_ebitda", "ev_ebit", "p_e", "p_fcf"
        ]

        medians = {"ticker": "SECTOR_MEDIAN", "company_name": "Sector Median", "period_label": "LTM", "is_target": 0}
        means = {"ticker": "SECTOR_MEAN", "company_name": "Sector Mean", "period_label": "LTM", "is_target": 0}

        for col in numeric_cols:
            col_vals = [p[col] for p in peers if p[col] is not None]
            
            # Valuation Multiples par Outlier filtering lagao (Ghalat values nikal do)
            if col in ["ev_revenue", "ev_ebitda", "ev_ebit", "p_e", "p_fcf"]:
                col_vals = self._filter_outliers(col_vals)

            if col_vals:
                medians[col] = statistics.median(col_vals)
                means[col] = sum(col_vals) / len(col_vals)
            else:
                medians[col] = None
                means[col] = None

        with self.db_manager.get_connection() as conn:
            try:
                for row in [medians, means]:
                    conn.execute(
                        text("""
                            INSERT OR REPLACE INTO trading_comps_table (
                                ticker, company_name, period_label, current_price, market_cap, enterprise_value,
                                ytd_return_pct, beta, ltm_revenue, revenue_growth_pct, gross_margin,
                                ebitda_margin, net_margin, fcf_margin, ev_revenue, ev_ebitda, ev_ebit, p_e, p_fcf, is_target
                            ) VALUES (
                                :ticker, :company_name, :period_label, :current_price, :market_cap, :enterprise_value,
                                :ytd_return_pct, :beta, :ltm_revenue, :revenue_growth_pct, :gross_margin,
                                :ebitda_margin, :net_margin, :fcf_margin, :ev_revenue, :ev_ebitda, :ev_ebit, :p_e, :p_fcf, :is_target
                            )
                        """),
                        row
                    )
            except Exception as e:
                logger.error(f"Failed to save sector statistics: {e}")

        # -------------------------------------------------------------------------------------------------
        # Step 8: Implied Valuation (Target company ka Sahi Price nikalna using competitors' multiples)
        # -------------------------------------------------------------------------------------------------
        
        # Target ke core numbers lo
        target_fin = financials.get(self.context.ticker, {})
        target_mkt = market_data.get(self.context.ticker, {})
        
        target_rev = target_fin.get("ltm_revenue")
        target_ebitda = target_fin.get("ltm_ebitda")
        target_ni = target_fin.get("ltm_net_income")
        
        target_net_debt = target_fin.get("latest_net_debt") or 0.0
        target_shares = target_mkt.get("shares_outstanding")
        target_current_price = target_mkt.get("current_price")

        # Teen tareeko se valuation nikali jayegi
        valuation_methods = [
            ("EV_EBITDA", target_ebitda, "ev_ebitda", True),
            ("EV_REVENUE", target_rev, "ev_revenue", True),
            ("PE", target_ni, "p_e", False)
        ]

        with self.db_manager.get_connection() as conn:
            try:
                conn.execute(text("DELETE FROM implied_valuation"))
            except Exception as e:
                logger.error(f"Failed to clear implied valuation table: {e}")

        successful_methods = 0

        for method, target_metric, col_name, is_ev_based in valuation_methods:
            # Competitors ke multiples ikattha karo aur ghalat (outliers) ko nikal do
            peer_multiples = [p[col_name] for p in peers if p[col_name] is not None]
            peer_multiples = self._filter_outliers(peer_multiples)

            if len(peer_multiples) < 2 or target_metric is None or target_metric <= 0:
                logger.warning(f"Implied valuation skipped for {method}: insufficient peer data or invalid target metric.")
                continue

            # Low (25%), Base (Median), aur High (75%) range nikalo
            p25 = self._get_percentile(peer_multiples, 25.0)
            p50 = self._get_percentile(peer_multiples, 50.0) # Median
            p75 = self._get_percentile(peer_multiples, 75.0)

            # Implied EV aur EqV (Equity Value) ka hisaab lagao
            if is_ev_based:
                # Agar EV based hai, toh Target Metric se multiply karke Enterprise value milegi
                implied_ev_low = p25 * target_metric
                implied_ev_base = p50 * target_metric
                implied_ev_high = p75 * target_metric
                
                # Uss Enterprise value me se target ki udhaari (Debt) hata do toh asli Equity Value aa jayegi
                implied_eq_low = implied_ev_low - target_net_debt
                implied_eq_base = implied_ev_base - target_net_debt
                implied_eq_high = implied_ev_high - target_net_debt
            else:
                # P/E method direct Equity Value deta hai (kyunki isme interest/debt pehle hi minus ho chuka hota hai)
                implied_eq_low = p25 * target_metric
                implied_eq_base = p50 * target_metric
                implied_eq_high = p75 * target_metric
                
                implied_ev_low = implied_eq_low + target_net_debt
                implied_ev_base = implied_eq_base + target_net_debt
                implied_ev_high = implied_eq_high + target_net_debt

            # Asli per-share Price nikalo total shares outstanding se divide karke
            implied_ps_low = (implied_eq_low / target_shares) if target_shares and target_shares > 0 else None
            implied_ps_base = (implied_eq_base / target_shares) if target_shares and target_shares > 0 else None
            implied_ps_high = (implied_eq_high / target_shares) if target_shares and target_shares > 0 else None

            # User ko dikhane ke liye percentage nikalo ki target market me abhi sasta hai ya mehanga (vs_current_price)
            vs_price = None
            if implied_ps_base is not None and target_current_price and target_current_price > 0:
                vs_price = ((implied_ps_base / target_current_price) - 1.0) * 100

            val_row = {
                "method": method,
                "peer_25p_multiple": p25,
                "peer_median_mult": p50,
                "peer_75p_multiple": p75,
                "target_metric": target_metric,
                "implied_ev_low": implied_ev_low,
                "implied_ev_base": implied_ev_base,
                "implied_ev_high": implied_ev_high,
                "implied_eq_low": implied_eq_low,
                "implied_eq_base": implied_eq_base,
                "implied_eq_high": implied_eq_high,
                "implied_ps_low": implied_ps_low,
                "implied_ps_base": implied_ps_base,
                "implied_ps_high": implied_ps_high,
                "vs_current_price": vs_price
            }

            with self.db_manager.get_connection() as conn:
                try:
                    conn.execute(
                        text("""
                            INSERT INTO implied_valuation (
                                method, peer_25p_multiple, peer_median_mult, peer_75p_multiple, target_metric,
                                implied_ev_low, implied_ev_base, implied_ev_high,
                                implied_eq_low, implied_eq_base, implied_eq_high,
                                implied_ps_low, implied_ps_base, implied_ps_high, vs_current_price
                            ) VALUES (
                                :method, :peer_25p_multiple, :peer_median_mult, :peer_75p_multiple, :target_metric,
                                :implied_ev_low, :implied_ev_base, :implied_ev_high,
                                :implied_eq_low, :implied_eq_base, :implied_eq_high,
                                :implied_ps_low, :implied_ps_base, :implied_ps_high, :vs_current_price
                            )
                        """),
                        val_row
                    )
                    successful_methods += 1
                except Exception as e:
                    logger.error(f"Failed to insert implied valuation for {method}: {e}")

        # Summary ko descriptive aur UI friendly banana
        status = "COMPLETED"
        summary = (
            f"Trading comps and implied valuation generated. "
            f"Successfully applied {successful_methods}/{len(valuation_methods)} valuation methods."
        )
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_4_COMPS_AND_VALUATION",
            status=status,
            summary=summary
        )
        logger.info(summary)
