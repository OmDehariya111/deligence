"""
Module:  module1_named_competitors.py
Agent:   Market Intelligence Agent
Purpose: Identify 5-7 strategically relevant named competitors through a
         multi-step pipeline:
         1. LLM-based real-world competitor identification (PRIMARY)
         2. ChromaDB RAG extraction for enrichment (SECONDARY)
         3. Sector benchmark peers as fallback (TERTIARY)
         4. Intelligent merge with SEC ticker resolution
Inputs:  MarketIntelContext (context object with peers, ratios, ChromaDB flag).
Outputs: Writes to `named_competitors` SQLite table.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import chromadb
from litellm import completion
from sqlalchemy import Column, Integer, MetaData, String, Table, text

from config.paths import get_run_paths
from schemas.pydantic_models import MarketIntelContext
from tools.sqlite_tools import DatabaseManager
from utils.llm_utils import parse_llm_json_response
from utils.mcp_client import call_mcp_tool_sync
from utils.audit_logger import log_audit_event

logger = logging.getLogger(__name__)

# Suffixes stripped when creating a "short form" for verification
# Ye ek regex expression hai jo kisi bhi company ke aage lage 'Inc', 'Corp' ko hata deta hai
_CORP_SUFFIXES = re.compile(
    r",?\s*\b(Inc\.?|Corp\.?|Corporation|LLC|PLC|Ltd\.?)\s*$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# SQLite table definition
# ---------------------------------------------------------------------------
def get_named_competitors_table(metadata: MetaData) -> Table:
    """
    # Ye function database me 'named_competitors' naam ki table banata hai 
    # jisme hum final competitors ka ticker, naam, CIK aur kyo select kiya (reason) save karenge.
    """
    return Table(
        "named_competitors",
        metadata,
        Column("ticker", String, primary_key=True),
        Column("company_name", String),
        Column("cik", String),
        Column("market_cap_usd", Integer),
        Column("why_selected", String),
        Column("selection_method", String),
        extend_existing=True,
    )


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class NamedCompetitorIdentifier:
    """Identifies 5-7 strategically relevant named competitors.
    
    Pipeline:
    1. LLM Knowledge — Ask AI for real-world competitors (PRIMARY SOURCE)
    2. ChromaDB RAG — Extract competitor mentions from 10-K filings (ENRICHMENT)
    3. Sector Benchmark Peers — Use Analysis Agent's peer list (FALLBACK)
    4. Intelligent Merge — Combine all sources with priority ranking
    """

    # ChromaDB search queries targeting competitor mentions in 10-K Item 1
    _RAG_QUERIES = [
        "our main competitors are",
        "we compete with",
        "competition includes",
        "principal competitors",
        "competitive landscape",
    ]

    def __init__(self, context: MarketIntelContext) -> None:
        self.context = context
        self.paths = get_run_paths(context.ticker, context.run_id)
        # Database se connect karke table create karte hain
        self.db_manager = DatabaseManager(self.paths["SQLITE_DB_PATH"])
        self.db_manager.create_tables(
            [get_named_competitors_table(self.db_manager.metadata)]
        )

    # ------------------------------------------------------------------
    # Step 0 — LLM-based competitor identification (NEW PRIMARY SOURCE)
    # ------------------------------------------------------------------
    def _step0_llm_competitors(self) -> list[dict]:
        """Ask LLM to identify real-world competitors for the target company.
        
        Returns:
            List of dicts with keys: name, reason
            
        # Ye step LLM (Gemini) se seedha puuchta hai ki is company ke 
        # real-world competitors kaun hain jo SEC me registered hain.
        """
        model_name = os.environ.get("LLM_MODEL_NAME_TIER1", "vertex_ai/gemini-2.5-flash")
        
        prompt = (
            f"You are a senior equity research analyst. For {self.context.company_name} "
            f"(ticker: {self.context.ticker}, SIC: {self.context.sic_code}, "
            f"industry: {self.context.industry_name}), identify the top 7 direct business "
            f"competitors that are:\n"
            f"1. Publicly traded in the US\n"
            f"2. Registered with the SEC (have CIK numbers and file 10-K reports)\n"
            f"3. Competing in the same core product/service markets\n"
            f"4. Relevant for institutional-grade competitive analysis\n\n"
            f"Use EXACT legal names as registered with the SEC "
            f"(e.g. 'MICROSOFT CORP' not 'Microsoft', 'ALPHABET INC' not 'Google').\n"
            f"Do NOT include {self.context.ticker} ({self.context.company_name}) itself.\n\n"
            f"Return ONLY a valid JSON array of objects:\n"
            f'[{{"name": "MICROSOFT CORP", "reason": "Competes in consumer electronics and cloud"}}]\n'
            f"No markdown formatting, no explanations outside the JSON."
        )
        
        try:
            response = completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = response.choices[0].message.content
            result = parse_llm_json_response(raw_text, default=[])
            
            if isinstance(result, list):
                valid = []
                for item in result:
                    if isinstance(item, dict) and item.get("name"):
                        valid.append({
                            "name": item["name"].strip(),
                            "reason": item.get("reason", "LLM-identified competitor")
                        })
                    elif isinstance(item, str) and item.strip():
                        valid.append({
                            "name": item.strip(),
                            "reason": "LLM-identified competitor"
                        })
                logger.info(f"LLM identified {len(valid)} competitors: {[v['name'] for v in valid]}")
                return valid
            return []
        except Exception as e:
            logger.error(f"LLM competitor identification failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Step 1 — ChromaDB RAG extraction (now ENRICHMENT, not primary)
    # ------------------------------------------------------------------
    def _step1_chromadb_extraction(self) -> list[str]:
        """Query ChromaDB for competitor names mentioned in 10-K Item 1.

        Returns:
            Raw list of competitor company names (List A - unverified).
        # Ye step ChromaDB me report padhta hai, wahan se chunk nikalta hai aur LLM se puchta hai.
        """
        if not self.context.is_chromadb_reachable:
            logger.info("ChromaDB unreachable — skipping RAG extraction.")
            return []

        # Build collection name (lowercase, hyphens, max 63 chars)
        collection_name = (
            f"{self.context.run_id.lower().replace('_', '-')}-filings"[:63]
        )

        try:
            client = chromadb.PersistentClient(
                path=str(self.paths["CHROMADB_DIR_PATH"])
            )
            collection = client.get_collection(name=collection_name)
        except Exception as e:
            logger.warning("Could not open ChromaDB collection '%s': %s", collection_name, e)
            return []

        # ChromaDB where filter: sirf Target Ticker ki latest 10-K ka Item 1 chahiye
        where_filter = {
            "$and": [
                {"ticker": self.context.ticker},
                {"section_code": {"$in": ["item_1", "full_document"]}},
                {"filing_type": "10-K"},
                {"fiscal_year": str(self.context.most_recent_fiscal_year)},
            ]
        }

        all_chunks: list[str] = []

        for query_text in self._RAG_QUERIES:
            try:
                results = collection.query(
                    query_texts=[query_text],
                    n_results=8,
                    where=where_filter,
                )
                if results and results.get("documents"):
                    for doc_list in results["documents"]:
                        all_chunks.extend(doc_list)
            except Exception as e:
                logger.warning("ChromaDB query failed for '%s': %s", query_text, e)

        if not all_chunks:
            logger.info("No ChromaDB chunks retrieved for competitor extraction.")
            return []

        # Store chunks for verification
        self._retrieved_chunk_text = "\n".join(all_chunks)

        # Duplicates remove karte hain
        seen: set[str] = set()
        unique_chunks: list[str] = []
        for chunk in all_chunks:
            normalized = chunk.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_chunks.append(normalized)

        concatenated = "\n---\n".join(unique_chunks)

        prompt = (
            "Act as a strict financial data extraction algorithm. Review the provided SEC 10-K excerpts. "
            "Identify direct named competitors, peers, or companies in the same industry mentioned by the target. "
            "Ignore generic terms (e.g., 'local businesses', 'international firms'). "
            "Output ONLY a valid JSON array of strings, e.g. [\"Oracle\", \"Adobe\"]. "
            "Do not include markdown formatting or conversational text.\n\n"
            f"{concatenated}"
        )

        model_name = os.environ.get("LLM_MODEL_NAME_TIER1", "vertex_ai/gemini-2.5-flash")
        try:
            response = completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = response.choices[0].message.content
            names = parse_llm_json_response(raw_text, default=[])
            if isinstance(names, list):
                return [n.strip() for n in names if isinstance(n, str) and n.strip()]
            return []
        except Exception as e:
            logger.error("LLM competitor extraction failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Step 1B — Verification against retrieved text
    # ------------------------------------------------------------------
    def _step1b_verify(self, raw_names: list[str]) -> list[str]:
        """Verify each name from RAG list actually appears in the retrieved text.
        # Hallucination roka jaata hai yahan.
        """
        if not raw_names:
            return []

        chunk_text_lower = getattr(self, "_retrieved_chunk_text", "").lower()
        if not chunk_text_lower:
            return raw_names

        verified: list[str] = []
        for name in raw_names:
            name_lower = name.lower()
            if name_lower in chunk_text_lower:
                verified.append(name)
                continue

            short = _CORP_SUFFIXES.sub("", name).strip()
            if short and short.lower() != name_lower and short.lower() in chunk_text_lower:
                verified.append(name)
                continue

            logger.debug("Competitor name '%s' not verified in chunk text — dropped.", name)

        logger.info(
            "Step 1B verification: %d/%d names verified.",
            len(verified),
            len(raw_names),
        )
        return verified

    # ------------------------------------------------------------------
    # Step 2 — List B from sector benchmark peers
    # ------------------------------------------------------------------
    def _step2_sector_peers(self) -> list[dict]:
        """Build fallback list from context.top_peers.
        # Ye step Analysis Agent ke Sector benchmark ke output se companies nikalta hai.
        """
        if self.context.is_sector_benchmark_partial:
            logger.info("Sector benchmark is partial — proceeding with available peers.")

        peers = self.context.top_peers
        if not peers:
            return []

        # Target Company ki revenue dhoondhte hain
        target_revenue: float | None = None
        for r_name in ["gross_margin", "operating_margin", "net_profit_margin", "ebitda_margin"]:
            ratio_obj = self.context.target_ratios.get(r_name)
            if isinstance(ratio_obj, dict):
                inputs = ratio_obj.get("inputs_used", {})
                if inputs and inputs.get("revenue"):
                    target_revenue = inputs.get("revenue")
                    break

        # CIK match karke khud ko ignore karte hain
        target_cik = self.context.cik.lstrip("0")
        filtered: list[dict] = []
        for p in peers:
            peer_cik = p.cik.lstrip("0")
            if peer_cik == target_cik:
                continue
            if target_revenue and target_revenue > 0 and p.revenue < (target_revenue * 0.05):
                continue
            filtered.append({
                "cik": p.cik,
                "entity_name": p.entity_name,
                "revenue": p.revenue,
            })

        filtered.sort(key=lambda x: x["revenue"], reverse=True)
        return filtered[:10]

    # ------------------------------------------------------------------
    # Ticker Resolution (shared utility)
    # ------------------------------------------------------------------
    def _resolve_tickers(self, names: list[str]) -> dict[str, dict]:
        """Resolve company names to tickers/CIKs via MCP get_company_tickers().
        # LLM ke diye hue naam ko actual SEC tickers se match karta hai.
        """
        if not names:
            return {}

        try:
            tickers_data = call_mcp_tool_sync(
                "mcp_servers/sec_edgar_server.py",
                "get_company_tickers",
                {},
            )
        except Exception as e:
            logger.error("Failed to fetch company tickers via MCP: %s", e)
            return {}

        mapping: dict[str, Any] = {}
        if isinstance(tickers_data, dict):
            mapping = tickers_data.get("mapping", tickers_data)

        entity_lookup: list[tuple[str, str, str]] = []
        if mapping:
            first_val = next(iter(mapping.values()))
            if isinstance(first_val, dict):
                for item in mapping.values():
                    t = item.get("ticker")
                    title = item.get("title")
                    cik_val = item.get("cik_str")
                    if t and title:
                        cik_str = str(cik_val).zfill(10) if cik_val is not None else ""
                        entity_lookup.append((t, title, cik_str))
            else:
                for ticker_key, entity_name in mapping.items():
                    if isinstance(entity_name, str):
                        entity_lookup.append((ticker_key, entity_name, ""))

        resolved: dict[str, dict] = {}
        for name in names:
            name_lower = name.lower()
            short_name = _CORP_SUFFIXES.sub("", name).strip().lower()

            best_match: tuple[str, str, str] | None = None

            # Pass 1: Exact match
            for ticker_key, entity_name, cik_str in entity_lookup:
                tk_lower = ticker_key.lower()
                ent_lower = entity_name.lower()
                if ent_lower == name_lower or ent_lower == short_name or tk_lower == name_lower or tk_lower == short_name:
                    best_match = (ticker_key, entity_name, cik_str)
                    break

            # Pass 2: Substring match
            if not best_match:
                for ticker_key, entity_name, cik_str in entity_lookup:
                    ent_lower = entity_name.lower()
                    if re.search(r'\b' + re.escape(name_lower) + r'\b', ent_lower):
                        best_match = (ticker_key, entity_name, cik_str)
                        break
                    if short_name and re.search(r'\b' + re.escape(short_name) + r'\b', ent_lower):
                        best_match = (ticker_key, entity_name, cik_str)
                        break

            if best_match:
                resolved[name] = {
                    "ticker": best_match[0],
                    "cik": best_match[2],
                    "entity_name": best_match[1],
                }

        logger.info(
            "Ticker resolution: %d/%d names resolved.", len(resolved), len(names)
        )
        return resolved

    # ------------------------------------------------------------------
    # Step 3 — Intelligent merge (updated priorities)
    # ------------------------------------------------------------------
    def _step3_merge(
        self,
        llm_competitors: list[dict],
        rag_list: list[str],
        benchmark_peers: list[dict],
    ) -> list[dict]:
        """Intelligently merge all competitor sources with priority ranking.

        Priority 1: LLM-identified competitors (highest quality)
        Priority 2: RAG-extracted names verified in 10-K text
        Priority 3: Sector benchmark peers (fallback)

        Returns:
            Final list of competitor dicts for DB insertion (max 7).
        """
        # Resolve LLM competitor names to SEC tickers
        llm_names = [c["name"] for c in llm_competitors]
        resolved_llm = self._resolve_tickers(llm_names)
        
        # Resolve RAG names to SEC tickers
        resolved_rag = self._resolve_tickers(rag_list)
        
        # Build CIK set from benchmark peers
        list_b_by_cik: dict[str, dict] = {}
        for peer in benchmark_peers:
            cik_norm = peer["cik"].lstrip("0")
            list_b_by_cik[cik_norm] = peer

        priority_1: list[dict] = []  # LLM-identified (best quality)
        priority_2: list[dict] = []  # RAG-only (from 10-K filings)
        priority_3: list[dict] = []  # Benchmark-only (SEC sector peers)

        used_tickers: set[str] = set()

        # --- Process LLM competitors (Priority 1) ---
        for comp in llm_competitors:
            info = resolved_llm.get(comp["name"])
            if not info:
                continue

            ticker = info["ticker"]
            if ticker.upper() == self.context.ticker.upper():
                continue
            if ticker in used_tickers:
                continue

            priority_1.append({
                "ticker": ticker,
                "company_name": info["entity_name"],
                "cik": info.get("cik", ""),
                "market_cap_usd": None,
                "why_selected": comp.get("reason", "LLM-identified real-world competitor"),
                "selection_method": "PRIORITY_1_LLM",
            })
            used_tickers.add(ticker)

        # --- Process RAG names (Priority 2) ---
        for name in rag_list:
            info = resolved_rag.get(name)
            if not info:
                continue

            ticker = info["ticker"]
            if ticker.upper() == self.context.ticker.upper():
                continue
            if ticker in used_tickers:
                continue

            priority_2.append({
                "ticker": ticker,
                "company_name": info["entity_name"],
                "cik": info.get("cik", ""),
                "market_cap_usd": None,
                "why_selected": f"Mentioned as competitor in 10-K filings (originally: '{name}').",
                "selection_method": "PRIORITY_2_RAG",
            })
            used_tickers.add(ticker)

        # --- Process Benchmark peers (Priority 3 - fallback) ---
        for peer in benchmark_peers:
            cik_norm = peer["cik"].lstrip("0")

            peer_resolved = self._resolve_tickers([peer["entity_name"]])
            peer_info = peer_resolved.get(peer["entity_name"])
            ticker = peer_info["ticker"] if peer_info else f"CIK_{peer['cik']}"

            if ticker.upper() == self.context.ticker.upper():
                continue
            if ticker in used_tickers:
                continue

            priority_3.append({
                "ticker": ticker,
                "company_name": peer["entity_name"],
                "cik": peer["cik"],
                "market_cap_usd": None,
                "why_selected": f"SEC sector peer (SIC {self.context.sic_code}) with revenue ${peer['revenue']:,.0f}.",
                "selection_method": "PRIORITY_3_BENCHMARK",
            })
            used_tickers.add(ticker)

        # Combine all priorities, cap at 7
        final = priority_1 + priority_2 + priority_3
        final = final[:7]

        logger.info(
            "Merge result: P1_LLM=%d, P2_RAG=%d, P3_BENCH=%d → final=%d competitors.",
            len(priority_1),
            len(priority_2),
            len(priority_3),
            len(final),
        )
        return final

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Execute the full named-competitor identification pipeline."""
        
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_1_NAMED_COMPETITORS",
            status="STARTED",
            summary="Beginning Named Competitor Identification (LLM + RAG + Benchmark Merge)."
        )

        # Step 0 — LLM-based competitor identification (PRIMARY)
        llm_competitors = self._step0_llm_competitors()
        logger.info("Step 0 LLM competitors: %d identified.", len(llm_competitors))

        # Step 1 — ChromaDB RAG extraction (ENRICHMENT)
        raw_list_a = self._step1_chromadb_extraction()
        logger.info("Step 1 raw RAG List: %d names extracted.", len(raw_list_a))

        # Step 1B — Verification
        verified_rag = self._step1b_verify(raw_list_a)
        logger.info("Step 1B verified RAG: %d names.", len(verified_rag))

        # Step 2 — Sector benchmark peers (FALLBACK)
        benchmark_peers = self._step2_sector_peers()
        logger.info("Step 2 Benchmark peers: %d sector peers.", len(benchmark_peers))

        # Step 3 — Intelligent merge with priority ranking
        final_competitors = self._step3_merge(llm_competitors, verified_rag, benchmark_peers)

        # Database (SQLite) me competitors save karte hain
        if final_competitors:
            insert_sql = """
                INSERT OR REPLACE INTO named_competitors
                (ticker, company_name, cik, market_cap_usd, why_selected, selection_method)
                VALUES
                (:ticker, :company_name, :cik, :market_cap_usd, :why_selected, :selection_method)
            """
            with self.db_manager.get_connection() as conn:
                try:
                    conn.execute(text("DELETE FROM named_competitors"))
                except Exception as e:
                    logger.warning(f"Failed to clear named_competitors: {e}")
                for comp in final_competitors:
                    conn.execute(text(insert_sql), comp)

        count = len(final_competitors)
        p1_count = sum(1 for c in final_competitors if c["selection_method"] == "PRIORITY_1_LLM")
        
        if count >= 5:
            status = "COMPLETED"
            summary = f"Identified {count} named competitors (target 5-7). LLM: {p1_count}, RAG+Benchmark: {count - p1_count}."
        elif count > 0:
            status = "COMPLETED"
            summary = (
                f"Identified only {count} competitors (target 5-7). "
                f"LLM: {p1_count}, RAG: {len(verified_rag)}, Benchmark: {len(benchmark_peers)}."
            )
        else:
            status = "COMPLETED"
            summary = "No competitors identified — LLM, RAG, and benchmark sources all yielded no results."

        self.db_manager.dispose()
        
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_1_NAMED_COMPETITORS",
            status=status,
            summary=summary
        )
        logger.info("Module 1 finished: %s — %s", status, summary)
