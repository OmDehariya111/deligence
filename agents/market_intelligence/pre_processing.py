"""
Module:  pre_processing.py
Agent:   Market Intelligence Agent
Purpose: Validates upstream inputs and constructs contextual base for market intelligence modules.
Inputs:  run_id, INGESTION_SUMMARY_PATH, RATIO_DB_PATH, SECTOR_BENCH_JSON, CHROMADB_DIR_PATH
Outputs: MarketIntelContext or halt exception.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.paths import get_run_paths
from schemas.pydantic_models import (
    IngestionSummary, 
    MarketIntelContext, 
    MarketIntelSummaryError,
    BenchmarkOutput,
    PeerInfo
)
from utils.audit_logger import log_audit_event


class PreProcessingError(Exception):
    """Controlled exception raised when Pre-Processing encounters a fatal condition.
    # Ye ek custom error hai jo hum tab raise karte hain jab agent ko koi aisi problem 
    # mile jisse wo aage kaam nahi kar sakta (jaise file gayab hona).
    """
    pass


class MarketIntelPreProcessor:
    """Handles the pre-processing checks and state setup for the Market Intelligence Agent.
    # Ye class Market Intel Agent start hone se pehle checking ka kaam karti hai.
    # Ye ensure karti hai ki pichle agents ne apna kaam theek se kiya hai,
    # aur aage ke modules ke liye zaroori data (context) taiyar karti hai.
    """

    def __init__(self, ticker: str, run_id: str):
        # Ticker ko uppercase aur clean karke save karte hain
        self.ticker = ticker.upper().strip()
        self.run_id = run_id
        # get_run_paths humein saari zaroori files ke paths ek dict me de deta hai
        self.paths = get_run_paths(self.ticker, self.run_id)

    def _write_fatal_error(self, reason: str, expected_path: str | None = None) -> None:
        """
        # Agar koi badi error aati hai (jaise file nahi mili), toh ye function
        # ek error file banata hai, log me 'FAILED' likhta hai, aur run rok deta hai.
        """
        error_obj = MarketIntelSummaryError(
            run_id=self.run_id,
            status="ERROR",
            reason=reason,
            expected_path=expected_path
        )
        self.paths["MI_SUMMARY_PATH"].parent.mkdir(parents=True, exist_ok=True)
        with open(self.paths["MI_SUMMARY_PATH"], "w", encoding="utf-8") as f:
            f.write(error_obj.model_dump_json(indent=2))
        
        # Naye standard ke according log_audit_event use kar rahe hain
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="PRE_PROCESSING",
            status="FAILED",
            summary=reason
        )
        raise PreProcessingError(reason)

    def run(self) -> MarketIntelContext:
        """
        Executes Steps 0A through Step 5.
        Returns a validated MarketIntelContext to be used by subsequent modules.
        # Ye is class ka main function hai jo ek ke baad ek checks run karta hai
        # aur aakhir me MarketIntelContext (data bag) return karta hai.
        """
        
        # Naye standard ke hisab se sabse pehle "STARTED" log likhna zaroori hai
        # taaki automatic duration (time track) sahi se ho.
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="PRE_PROCESSING",
            status="STARTED",
            summary="Starting Market Intelligence pre-processing and validation."
        )
        
        # Step 0C: Check Upstream Agent Status
        # Sabse pehle dekhte hain ki Ingestion Agent ki output file mojud hai ya nahi.
        if not self.paths["INGESTION_SUMMARY_PATH"].exists():
             self._write_fatal_error(
                 reason="Ingestion Agent output missing.",
                 expected_path=str(self.paths["INGESTION_SUMMARY_PATH"])
             )
        
        # Ingestion summary ko read karke JSON parse karte hain.
        try:
            with open(self.paths["INGESTION_SUMMARY_PATH"], "r", encoding="utf-8") as f:
                ingestion_data = json.load(f)
        except Exception as e:
            self._write_fatal_error(reason=f"Failed to read Ingestion Summary: {e}")
            
        # Agar Ingestion Agent fail hua tha, toh hum yahan kaam rok denge.
        if ingestion_data.get("status") == "ERROR":
            self._write_fatal_error(reason="Upstream Ingestion Agent failed: " + ingestion_data.get("reason", "Unknown"))
            
        # Check Analysis Agent propagation of Ingestion failure
        # Kabhi-kabhi Analysis Agent ingestion error ko catch karke apne output me "SKIPPED" likh deta hai,
        # hum usko yahan detect karke process halt karte hain.
        for p in [self.paths["RATIO_DB_PATH"], self.paths["SECTOR_BENCH_JSON"]]:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and data.get("status") == "SKIPPED" and "Ingestion Agent failed" in data.get("reason", ""):
                            self._write_fatal_error(reason="Upstream Ingestion Agent failed. (Propagated via Analysis Agent).")
                except json.JSONDecodeError:
                    pass

        # Agar RATIO_DB_PATH (Analysis agent ka main output) miss hai, toh error throw karo.
        if not self.paths["RATIO_DB_PATH"].exists():
             self._write_fatal_error(
                 reason="Analysis Agent Ratio Database missing. Module 1 failed.",
                 expected_path=str(self.paths["RATIO_DB_PATH"])
             )
        
        # Step 0D: Sector Benchmark Pre-Flight Guard
        # Sector Benchmark data zaroori hai. Agar file bilkul nahi hai toh error de do.
        if not self.paths["SECTOR_BENCH_JSON"].exists():
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="MarketIntelligenceAgent",
                module="PRE_FLIGHT_M1_GUARD",
                status="FAILED",
                summary="SECTOR_BENCH_JSON missing — halting run."
            )
            self._write_fatal_error(
                reason="Analysis Agent must complete fully before Market Intelligence Agent starts. Sector Benchmark file not found.",
                expected_path=str(self.paths["SECTOR_BENCH_JSON"])
            )

        # Determine degradation for Sector Benchmark
        # File hai, par check karna hai ki kitni successful hai (pura data hai ya aadha).
        try:
            with open(self.paths["SECTOR_BENCH_JSON"], "r", encoding="utf-8") as f:
                sector_data = json.load(f)
        except Exception as e:
            self._write_fatal_error(reason=f"Failed to parse Sector Benchmark: {e}")
            
        is_sector_benchmark_partial = False
        top_peers = []
        
        # --- BUG 2 FIXED HERE ---
        # Pehle try karte hain jo bhi data hai use load karne ka, taaki PARTIAL hone pe 
        # bhi jo peers (jaise 3 ya 4 peers) mile hain, wo discard na hon (data loss roko).
        try:
            bench_output = BenchmarkOutput.model_validate(sector_data)
            top_peers = bench_output.top_peers
        except Exception as e:
            pass # Agar parse nahi ho paya, toh exception aayega jo hum handle kar rahe hain

        # Agar status FAILED, PARTIAL hai, ya peers bilkul nahi mile, toh isko 
        # partial (degraded) mark karte hain taaki aage ke modules is fact ko dhyan me rakhein.
        if sector_data.get("status") in ["FAILED", "PARTIAL"] or sector_data.get("peer_count", 0) == 0:
            is_sector_benchmark_partial = True

        # 1. Load Ingestion Summary
        # Ingestion data ko object me convert aur validate karte hain (strict type check).
        try:
            ingestion_summary = IngestionSummary.model_validate(ingestion_data)
        except Exception as e:
            self._write_fatal_error(reason=f"Ingestion Summary validation failed: {e}")

        # 3. Load target ratios & Determine LTM Base Configuration
        # --- BUG 1 FIXED HERE ---
        try:
            with open(self.paths["RATIO_DB_PATH"], "r", encoding="utf-8") as f:
                target_ratios_data = json.load(f)
                
            # Pehle sabse latest saal (most_recent_fiscal_year) nikalte hain saare data se.
            most_recent_fiscal_year = max(
                [r.get("fiscal_year", 0) for r in target_ratios_data], 
                default=0
            )
            # User ke instruction ke anusaar, bug 3 (timezone default issue) fix nahi kiya hai.
            if most_recent_fiscal_year == 0:
                most_recent_fiscal_year = datetime.now().year - 1

            target_ratios = {}
            # Ab sirf us latest saal ke ratios ko dictionary me save karte hain,
            # jisse pichle saalo ka data mix nahi hoga aur overwrite issue solve ho jayega.
            for ratio in target_ratios_data:
                if ratio.get("fiscal_year") == most_recent_fiscal_year:
                    target_ratios[ratio["ratio_name"]] = ratio
                    
        except Exception as e:
             self._write_fatal_error(reason=f"Failed to load Ratio DB: {e}")

        # 4. Check ChromaDB
        # Dekhte hain ki vector database folder mojud hai ya nahi.
        is_chromadb_reachable = self.paths["CHROMADB_DIR_PATH"].exists()

        # Context Object banate hain jo final thela/bag hai jisme saara kaam ka data 
        # store karke return karenge.
        context = MarketIntelContext(
            run_id=self.run_id,
            ticker=self.ticker,
            company_name=ingestion_summary.company_identity.company_name,
            cik=ingestion_summary.company_identity.cik,
            sic_code=ingestion_summary.company_identity.sic_code,
            industry_name=ingestion_summary.company_identity.industry_name,
            fiscal_year_end_month=ingestion_summary.company_identity.fiscal_year_end_month,
            most_recent_fiscal_year=most_recent_fiscal_year,
            is_sector_benchmark_partial=is_sector_benchmark_partial,
            is_chromadb_reachable=is_chromadb_reachable,
            top_peers=top_peers,
            target_ratios=target_ratios
        )

        # Naye standard ke hisab se "COMPLETED" status aur descriptive summary log karte hain.
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="PRE_PROCESSING",
            status="COMPLETED",
            summary=f"Contextual base built successfully. ChromaDB reachable: {is_chromadb_reachable}, Benchmark partial: {is_sector_benchmark_partial}."
        )
        
        return context
