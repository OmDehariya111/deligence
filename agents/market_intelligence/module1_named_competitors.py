"""
Module:  module1_named_competitors.py
Agent:   Market Intelligence Agent
Purpose: Identify 5-7 strategically relevant named competitors through a
         three-step pipeline: ChromaDB RAG extraction (List A), sector
         benchmark peers (List B), and intelligent merge with MCP-based
         ticker resolution.
Inputs:  MarketIntelContext (context object with peers, ratios, ChromaDB flag).
Outputs: Writes to `named_competitors` SQLite table.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone

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
    # Ye main class hai jo saare kaam ko 3 step me karegi: 
    # 1. RAG (Filings se naam nikalna), 2. Benchmark peers nikalna, 3. Dono ko merge karna.
    """

    # ChromaDB search queries targeting competitor mentions in 10-K Item 1
    # Hum target company ki Annual Report (10-K) me in 5 questions (queries) se competitors dhoondhte hain.
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
    # Step 1 — ChromaDB RAG extraction
    # ------------------------------------------------------------------
    def _step1_chromadb_extraction(self) -> list[str]:
        """Query ChromaDB for competitor names mentioned in 10-K Item 1.

        Returns:
            Raw list of competitor company names (List A - unverified).
        # Ye step ChromaDB me report padhta hai, wahan se chunk nikalta hai aur LLM se puchta hai.
        """
        if not self.context.is_chromadb_reachable:
            logger.info("ChromaDB unreachable — skipping Step 1 RAG extraction.")
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

        # ChromaDB where filter: Hame sirf Target Ticker ki latest 10-K ka Item 1 chahiye
        where_filter = {
            "$and": [
                {"ticker": self.context.ticker},
                {"section_code": {"$in": ["item_1", "full_document"]}},
                {"filing_type": "10-K"},
                {"fiscal_year": str(self.context.most_recent_fiscal_year)},
            ]
        }

        all_chunks: list[str] = []

        # Humare paas jo 5 RAG queries hain unko ek ek karke run karte hain
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

        # Store chunks for Step 1B verification (verification step ke liye save kar rakha hai)
        self._retrieved_chunk_text = "\n".join(all_chunks)

        # Duplicates remove karte hain taaki AI ko clear context mile
        seen: set[str] = set()
        unique_chunks: list[str] = []
        for chunk in all_chunks:
            normalized = chunk.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_chunks.append(normalized)

        concatenated = "\n---\n".join(unique_chunks)

        # Ye wo prompt hai jo LLM ko bheja jaayega taaki wo sirf JSON format me names de sake.
        prompt = (
            "Act as a strict financial data extraction algorithm. Review the provided SEC 10-K excerpts. "
            "Identify direct named competitors, peers, or companies in the same industry mentioned by the target. "
            "Ignore generic terms (e.g., 'local businesses', 'international firms'). "
            "Output ONLY a valid JSON array of strings, e.g. [\"Oracle\", \"Adobe\"]. "
            "Do not include markdown formatting or conversational text.\n\n"
            f"{concatenated}"
        )

        # -- BUG 1 FIXED: LLM Hardcoding Removed --
        # Ab hum directly Google Vertex AI (Gemini) call karte hain using environment variables.
        # Credentials backend me Litellm automatically 'deligenx.json' se fetch kar lega.
        model_name = os.environ.get("LLM_MODEL_NAME_TIER1", "vertex_ai/gemini-2.5-flash")
        try:
            response = completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = response.choices[0].message.content
            # parse_llm_json_response ek utility hai jo json block padhke python list me badal deti hai
            names = parse_llm_json_response(raw_text, default=[])
            if isinstance(names, list):
                return [n.strip() for n in names if isinstance(n, str) and n.strip()]
            return []
        except Exception as e:
            logger.error("LLM competitor extraction failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Step 1B (Fix M-4) — Verification against retrieved text
    # ------------------------------------------------------------------
    def _step1b_verify(self, raw_names: list[str]) -> list[str]:
        """Verify each name from List A actually appears in the retrieved
        ChromaDB chunk text. Also tries a shortened form with corporate
        suffixes removed.

        Returns:
            Verified subset of raw_names.
            
        # Is function me hum LLM ke diye hue naam ko verify karte hain ki wo original text me
        # mojud tha ya AI ne apni taraf se bana diya (hallucination roka jata hai yaha).
        """
        if not raw_names:
            return []

        chunk_text_lower = getattr(self, "_retrieved_chunk_text", "").lower()
        if not chunk_text_lower:
            # Agar text hi nahi hai compare karne ke liye toh skip karo
            return raw_names

        verified: list[str] = []
        for name in raw_names:
            name_lower = name.lower()
            # Agar exact string match mil gaya
            if name_lower in chunk_text_lower:
                verified.append(name)
                continue

            # Agar company ke naam ke peeche se 'Inc.' wagera hata ke match karein
            short = _CORP_SUFFIXES.sub("", name).strip()
            if short and short.lower() != name_lower and short.lower() in chunk_text_lower:
                verified.append(name)
                continue

            # Agar dono tariko se nahi mila, toh matlab LLM ne galat predict kiya, isliye drop kar diya.
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
        """Build List B from context.top_peers.

        Returns:
            List of dicts with keys: cik, entity_name, revenue.
            
        # Ye step Analysis Agent ke Sector benchmark ke output se companies nikalta hai.
        """
        if self.context.is_sector_benchmark_partial:
            logger.info("Sector benchmark is partial — proceeding with available peers.")

        peers = self.context.top_peers
        if not peers:
            return []

        # Pehle hum Target Company ki revenue dhoondhte hain taaki choti companies ko filter kiya ja sake.
        target_revenue: float | None = None
        for r_name in ["gross_margin", "operating_margin", "net_profit_margin", "ebitda_margin"]:
            ratio_obj = self.context.target_ratios.get(r_name)
            if isinstance(ratio_obj, dict):
                inputs = ratio_obj.get("inputs_used", {})
                if inputs and inputs.get("revenue"):
                    target_revenue = inputs.get("revenue")
                    break

        # CIK match karke khud (Target company) ko ignore karte hain.
        target_cik = self.context.cik.lstrip("0")
        filtered: list[dict] = []
        for p in peers:
            peer_cik = p.cik.lstrip("0")
            if peer_cik == target_cik:
                continue
            # Revenue floor: Agar peer ki revenue target ki 5% se kam hai toh ignore karo.
            if target_revenue and target_revenue > 0 and p.revenue < (target_revenue * 0.05):
                continue
            filtered.append({
                "cik": p.cik,
                "entity_name": p.entity_name,
                "revenue": p.revenue,
            })

        # Sabse zyaada revenue waali top 10 companies ko list me rakh lete hain.
        filtered.sort(key=lambda x: x["revenue"], reverse=True)
        return filtered[:10]

    # ------------------------------------------------------------------
    # Step 3 — Intelligent merge
    # ------------------------------------------------------------------
    def _resolve_tickers(self, names: list[str]) -> dict[str, dict]:
        """Resolve List A company names to tickers/CIKs via MCP
        get_company_tickers().

        Returns:
            Dict mapping original name → {ticker, cik, entity_name}
            for resolved names.
            
        # LLM ne humein sirf Companies ke naam diye the (jaise "Oracle"), ye tool
        # un naamo ko actual SEC tickers (jaise "ORCL") se match karne me help karta hai.
        """
        if not names:
            return {}

        try:
            # MCP ko call karke SEC ki master ticker file mangwate hain.
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

        # Dictionary banate hain search karne me aasani ho isliye
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

            # Pass 1: Pehle check karte hain exact name match ya exact ticker match hota hai kya.
            for ticker_key, entity_name, cik_str in entity_lookup:
                tk_lower = ticker_key.lower()
                ent_lower = entity_name.lower()
                if ent_lower == name_lower or ent_lower == short_name or tk_lower == name_lower or tk_lower == short_name:
                    best_match = (ticker_key, entity_name, cik_str)
                    break

            # Pass 2: Agar exact match nahi mila, toh substring check karte hain (Jaise "Oracle" inside "Oracle Corporation")
            if not best_match:
                for ticker_key, entity_name, cik_str in entity_lookup:
                    ent_lower = entity_name.lower()
                    if re.search(r'\b' + re.escape(name_lower) + r'\b', ent_lower):
                        best_match = (ticker_key, entity_name, cik_str)
                        break
                    if short_name and re.search(r'\b' + re.escape(short_name) + r'\b', ent_lower):
                        best_match = (ticker_key, entity_name, cik_str)
                        break

            # Jo match hua use resolved dictionary me save kar lete hain
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

    def _step3_merge(
        self,
        list_a: list[str],
        list_b: list[dict],
    ) -> list[dict]:
        """Intelligently merge List A (RAG) and List B (benchmark peers).

        Priority 1: In both A and B (matched by CIK)
        Priority 2: In A only (with resolved ticker)
        Priority 3: In B only

        Returns:
            Final list of competitor dicts for DB insertion (max 7).
            
        # Is step me hum Filing ke competitors aur Database (Industry) ke competitors
        # ko mila kar best 7 competitors choose karte hain based on priority.
        """
        # Step 1 waalo ka ticker resolve karte hain
        resolved_a = self._resolve_tickers(list_a)

        # Step 2 waalo ko CIK id ke basis pe dictionary me dalte hain
        list_b_by_cik: dict[str, dict] = {}
        for peer in list_b:
            cik_norm = peer["cik"].lstrip("0")
            list_b_by_cik[cik_norm] = peer

        priority_1: list[dict] = []  # Jo dono me mile
        priority_2: list[dict] = []  # Jo sirf RAG se mile
        priority_3: list[dict] = []  # Jo sirf Benchmark (SEC Sector) se mile

        # Dupes (duplicate companies) rokne ke liye ek set maintain karte hain
        used_ciks: set[str] = set()
        used_tickers: set[str] = set()

        # Pehle unhe process karte hain jo List A (Report) me mojud they
        for name in list_a:
            info = resolved_a.get(name)
            if not info:
                continue

            ticker = info["ticker"]
            if ticker.upper() == self.context.ticker.upper():
                continue  # Khud ki company ko competitors me mat dalo
            if ticker in used_tickers:
                continue

            # Dekhte hain kya ye competitor List B me bhi hai?
            matched_peer: dict | None = None
            for cik_key, peer in list_b_by_cik.items():
                peer_name_lower = peer["entity_name"].lower()
                resolved_name_lower = info["entity_name"].lower()
                if (
                    peer_name_lower == resolved_name_lower
                    or peer_name_lower in resolved_name_lower
                    or resolved_name_lower in peer_name_lower
                ):
                    matched_peer = peer
                    break

            if matched_peer:
                # Agar dono me mila, toh wo priority 1 me jayega (Highest Priority).
                cik_norm = matched_peer["cik"].lstrip("0")
                priority_1.append({
                    "ticker": ticker,
                    "company_name": info["entity_name"],
                    "cik": matched_peer["cik"],
                    "market_cap_usd": None,
                    "why_selected": "Mentioned in 10-K filings AND appears in sector benchmark peers.",
                    "selection_method": "PRIORITY_1_BOTH",
                })
                used_ciks.add(cik_norm)
                used_tickers.add(ticker)
            else:
                # Agar sirf report me mila, par List B me nahi
                priority_2.append({
                    "ticker": ticker,
                    "company_name": info["entity_name"],
                    "cik": info.get("cik", ""),
                    "market_cap_usd": None,
                    "why_selected": f"Mentioned as competitor in 10-K filings (originally: '{name}').",
                    "selection_method": "PRIORITY_2_RAG_ONLY",
                })
                used_tickers.add(ticker)

        # Ab jo List B (Sector) ki companies bach gayi unhe (Priority 3) me dalte hain
        for peer in list_b:
            cik_norm = peer["cik"].lstrip("0")
            if cik_norm in used_ciks:
                continue

            # Unka ticker pata karne ki koshish
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
                "selection_method": "PRIORITY_3_BENCHMARK_ONLY",
            })
            used_ciks.add(cik_norm)
            used_tickers.add(ticker)

        # Teeno priorities ko mila kar top 7 competitors ko filter kar lete hain
        final = priority_1 + priority_2 + priority_3
        final = final[:7]

        logger.info(
            "Merge result: P1=%d, P2=%d, P3=%d → final=%d competitors.",
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
        
        # --- BUG 2 FIXED: NEW AUDIT LOGGING STANDARD ---
        # Ab hum 'utils.audit_logger' ki wajah se 'STARTED' log standard tarike se bhejte hain.
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_1_NAMED_COMPETITORS",
            status="STARTED",
            summary="Beginning Named Competitor Identification (RAG + Benchmark Merge)."
        )

        # Step 1 — ChromaDB RAG extraction
        raw_list_a = self._step1_chromadb_extraction()
        logger.info("Step 1 raw List A: %d names extracted.", len(raw_list_a))

        # Step 1B — Verification (Fix M-4)
        verified_list_a = self._step1b_verify(raw_list_a)
        logger.info("Step 1B verified List A: %d names.", len(verified_list_a))

        # Step 2 — Sector benchmark peers (List B)
        list_b = self._step2_sector_peers()
        logger.info("Step 2 List B: %d sector peers.", len(list_b))

        # Step 3 — Intelligent merge
        final_competitors = self._step3_merge(verified_list_a, list_b)

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

        # Dekhte hain successful kitne competitors mile taaki descriptive log likha ja sake
        count = len(final_competitors)
        if count >= 5:
            status = "COMPLETED"
            summary = f"Identified {count} named competitors (target 5-7). Methods used: RAG + SEC Peers."
        elif count > 0:
            status = "COMPLETED"
            summary = (
                f"Identified only {count} competitors (target 5-7). "
                f"Fallback applied due to limited data. Sources: RAG ({len(verified_list_a)}), Peers ({len(list_b)})."
            )
        else:
            status = "COMPLETED"
            summary = "No competitors identified — both RAG (0) and SEC benchmark (0) sources yielded no results."

        self.db_manager.dispose()
        
        # 'COMPLETED' (ya PARTIAL) status same module name ke saath, taaki time calculate ho jaye
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_1_NAMED_COMPETITORS",
            status=status,
            summary=summary
        )
        logger.info("Module 1 finished: %s — %s", status, summary)
