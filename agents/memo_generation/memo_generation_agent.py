"""
Module:  memo_generation_agent.py
Agent:   Memo Generation Agent (Agent 5)
Purpose: Master orchestrator for the Memo Generation Agent — the crown jewel of DeligenX.
         Validates upstream outputs, loads all data, generates all 18 sections,
         assembles the final HTML report, and writes it to disk.
         Follows platform-standard audit logging with smart duration tracking.
Inputs:  ticker (str), run_id (str) — identifies the company and run to process.
Outputs: Single self-contained HTML investment memo at output/{RUN_ID}/memo/{RUN_ID}_investment_memo.html
"""

import json
import logging
import time
from pathlib import Path

from config.paths import get_run_paths, ensure_run_dirs
from utils.audit_logger import log_audit_event
from agents.memo_generation.pre_processing import run_pre_processing
from agents.memo_generation.chart_engine import reset_chart_counter
from agents.memo_generation.html_renderer import assemble_html

# Section Writers
from agents.memo_generation.section_writers.cover_page import Section0Writer
from agents.memo_generation.section_writers.executive_summary import Section1Writer
from agents.memo_generation.section_writers.company_overview import Section2Writer
from agents.memo_generation.section_writers.financial_statements import Section3Writer
from agents.memo_generation.section_writers.ratio_analysis import Section4Writer
from agents.memo_generation.section_writers.trend_analysis import Section5Writer
from agents.memo_generation.section_writers.fraud_distress import Section6Writer
from agents.memo_generation.section_writers.anomaly_detection import Section7Writer
from agents.memo_generation.section_writers.sector_benchmark import Section8Writer
from agents.memo_generation.section_writers.qoe_score import Section9Writer
from agents.memo_generation.section_writers.competitive_landscape import Section10Writer
from agents.memo_generation.section_writers.valuation import Section11Writer
from agents.memo_generation.section_writers.news_sentiment import Section12Writer
from agents.memo_generation.section_writers.macro_context import Section13Writer
from agents.memo_generation.section_writers.risk_assessment import Section14Writer
from agents.memo_generation.section_writers.mitigation import Section15Writer
from agents.memo_generation.section_writers.verification import Section16Writer
from agents.memo_generation.section_writers.appendix import Section17Writer

logger = logging.getLogger(__name__)

# Agent name for audit logging — consistent across all log entries
AGENT_NAME = "MemoGenerationAgent"
# Pipeline module name — SAME for STARTED and COMPLETED (per logging rules)
PIPELINE_MODULE = "MEMO_GENERATION_PIPELINE"


class MemoGenerationAgent:
    """Orchestrator for the Memo Generation Agent.

    Executes the 8-step pipeline:
        Step 0: Pre-Processing (validate + load + verify)
        Step 1: Cover Page Generation
        Step 2: Section Generation (Sections 1-17)
        Step 3: HTML Assembly
        Step 4: Write Output
    """

    def __init__(self, ticker: str, run_id: str):
        """Initialize the Memo Generation Agent.

        Args:
            ticker: Company ticker symbol (e.g., 'MSFT').
            run_id: Run ID from config/paths.py (e.g., 'MSFT_20260718_104347').
        """
        self.ticker = ticker.upper().strip()
        self.run_id = run_id
        self.paths = get_run_paths(self.ticker, self.run_id)
        self.audit_log = self.paths["AUDIT_LOG_PATH"]

    def run(self) -> Path:
        """Execute the complete memo generation pipeline.

        Returns:
            Path to the generated HTML memo file.

        Raises:
            Exception: If any critical step fails.
        """
        # ═══════════════════════════════════════════════════════════════
        # PIPELINE START
        # ═══════════════════════════════════════════════════════════════
        log_audit_event(
            audit_log_path=self.audit_log,
            agent=AGENT_NAME,
            module=PIPELINE_MODULE,
            status="STARTED",
            summary=(
                f"Memo Generation Pipeline STARTED for {self.ticker} (run: {self.run_id}). "
                f"Will generate 17-section investment memo with 40+ visualizations, "
                f"financial verification report, and professional LLM narratives."
            ),
        )

        try:
            # ═══════════════════════════════════════════════════════════
            # STEP 0: PRE-PROCESSING
            # ═══════════════════════════════════════════════════════════
            log_audit_event(
                self.audit_log, AGENT_NAME, "STEP_0_PRE_PROCESSING", "STARTED",
                "Validating upstream agent outputs, loading all data from 9 JSON files "
                "+ 16 SQLite tables + ChromaDB, running Financial Data Verification Engine."
            )

            data = run_pre_processing(self.paths, self.ticker)

            collection = data.get("_collection_summary", {})
            verification = data.get("verification_results", {}).get("summary", {})

            log_audit_event(
                self.audit_log, AGENT_NAME, "STEP_0_PRE_PROCESSING", "COMPLETED",
                (
                    f"Pre-processing COMPLETE. "
                    f"Loaded {collection.get('json_files_loaded', 0)}/9 JSON files, "
                    f"{collection.get('total_sql_rows', 0)} SQLite rows across 16 tables, "
                    f"ChromaDB chunks loaded: {collection.get('chromadb_loaded', False)}. "
                    f"Verification: {verification.get('data_points_with_value', 0)}/"
                    f"{verification.get('total_data_points', 0)} data points verified, "
                    f"{verification.get('cross_checks_passed', 0)}/"
                    f"{verification.get('cross_checks_total', 0)} arithmetic cross-checks passed."
                ),
            )

            # Ensure output directory exists
            ensure_run_dirs(self.paths)
            self.paths["MEMO_OUTPUT_DIR"].mkdir(parents=True, exist_ok=True)

            # Reset chart counter for unique IDs
            reset_chart_counter()

            # ═══════════════════════════════════════════════════════════
            # STEP 1: GENERATE COVER PAGE
            # ═══════════════════════════════════════════════════════════
            log_audit_event(
                self.audit_log, AGENT_NAME, "STEP_1_COVER_PAGE", "STARTED",
                "Generating cover page with company branding, report metadata, and confidentiality notice."
            )

            cover_html = Section0Writer(data).generate()

            log_audit_event(
                self.audit_log, AGENT_NAME, "STEP_1_COVER_PAGE", "COMPLETED",
                f"Cover page generated for {data.get('company_name', self.ticker)}."
            )

            # ═══════════════════════════════════════════════════════════
            # STEP 2: GENERATE ALL 17 SECTIONS
            # ═══════════════════════════════════════════════════════════
            log_audit_event(
                self.audit_log, AGENT_NAME, "STEP_2_SECTIONS", "STARTED",
                "Generating all 17 report sections: Executive Summary, Company Overview, "
                "Financial Statements, Ratio Analysis, Trend Analysis, Fraud & Distress, "
                "Anomaly Detection, Sector Benchmarking, QoE Score, Competitive Landscape, "
                "Valuation, News Sentiment, Macro Context, Risk Assessment, Mitigation, "
                "Verification Report, Appendix."
            )

            section_writers = [
                ("Section 1: Executive Summary", Section1Writer),
                ("Section 2: Company Overview", Section2Writer),
                ("Section 3: Financial Statements", Section3Writer),
                ("Section 4: Ratio Analysis", Section4Writer),
                ("Section 5: Trend Analysis", Section5Writer),
                ("Section 6: Fraud & Distress", Section6Writer),
                ("Section 7: Anomaly Detection", Section7Writer),
                ("Section 8: Sector Benchmarking", Section8Writer),
                ("Section 9: QoE Score", Section9Writer),
                ("Section 10: Competitive Landscape", Section10Writer),
                ("Section 11: Implied Valuation", Section11Writer),
                ("Section 12: News Sentiment", Section12Writer),
                ("Section 13: Macro Context", Section13Writer),
                ("Section 14: Risk Assessment", Section14Writer),
                ("Section 15: Mitigation", Section15Writer),
                ("Section 16: Verification Report", Section16Writer),
                ("Section 17: Appendix", Section17Writer),
            ]

            section_htmls = []
            sections_completed = 0
            sections_failed = 0

            for section_name, writer_class in section_writers:
                try:
                    logger.info(f"Generating {section_name}...")
                    html = writer_class(data).generate()
                    section_htmls.append(html)
                    sections_completed += 1
                    logger.info(f"✅ {section_name} generated ({len(html):,} chars)")
                except Exception as e:
                    sections_failed += 1
                    logger.error(f"❌ {section_name} FAILED: {e}", exc_info=True)
                    # Add error placeholder so the report structure is maintained
                    section_htmls.append(
                        f'<div class="section"><div class="callout callout-danger">'
                        f'<h4>{section_name} — Generation Failed</h4>'
                        f'<p>Error: {type(e).__name__}: {e}</p></div></div>'
                    )

            log_audit_event(
                self.audit_log, AGENT_NAME, "STEP_2_SECTIONS", "COMPLETED",
                (
                    f"Section generation COMPLETE. "
                    f"{sections_completed}/17 sections generated successfully, "
                    f"{sections_failed} sections failed (error placeholders inserted). "
                    f"Total HTML content: {sum(len(h) for h in section_htmls):,} characters."
                ),
            )

            # ═══════════════════════════════════════════════════════════
            # STEP 3: HTML ASSEMBLY
            # ═══════════════════════════════════════════════════════════
            log_audit_event(
                self.audit_log, AGENT_NAME, "STEP_3_HTML_ASSEMBLY", "STARTED",
                "Assembling final HTML document with CSS design system, Chart.js library, "
                "Table of Contents, cover page, all 17 sections, and footer."
            )

            final_html = assemble_html(
                company_name=data.get("company_name", self.ticker),
                ticker=self.ticker,
                cover_html=cover_html,
                section_htmls=section_htmls,
                run_id=self.run_id,
            )

            log_audit_event(
                self.audit_log, AGENT_NAME, "STEP_3_HTML_ASSEMBLY", "COMPLETED",
                f"HTML assembled: {len(final_html):,} characters total document size."
            )

            # ═══════════════════════════════════════════════════════════
            # STEP 4: WRITE OUTPUT
            # ═══════════════════════════════════════════════════════════
            log_audit_event(
                self.audit_log, AGENT_NAME, "STEP_4_WRITE_OUTPUT", "STARTED",
                f"Writing final HTML memo to {self.paths['MEMO_HTML_PATH']}"
            )

            output_path = self.paths["MEMO_HTML_PATH"]
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(final_html)

            file_size_kb = output_path.stat().st_size / 1024

            # Also write data integrity certificate JSON
            cert_path = self.paths["MEMO_JSON_CERT_PATH"]
            cert_data = {
                "run_id": self.run_id,
                "ticker": self.ticker,
                "company_name": data.get("company_name", "N/A"),
                "memo_html_path": str(output_path),
                "memo_html_size_kb": round(file_size_kb, 1),
                "sections_generated": sections_completed,
                "sections_failed": sections_failed,
                "verification_summary": verification,
                "data_collection_summary": collection,
            }
            with open(cert_path, "w", encoding="utf-8") as f:
                json.dump(cert_data, f, indent=2, default=str)

            log_audit_event(
                self.audit_log, AGENT_NAME, "STEP_4_WRITE_OUTPUT", "COMPLETED",
                (
                    f"Output written successfully. "
                    f"HTML memo: {output_path.name} ({file_size_kb:.1f} KB). "
                    f"Data integrity certificate: {cert_path.name}. "
                    f"Output directory: {output_path.parent}"
                ),
            )

            # ═══════════════════════════════════════════════════════════
            # PIPELINE COMPLETE
            # ═══════════════════════════════════════════════════════════
            log_audit_event(
                self.audit_log, AGENT_NAME, PIPELINE_MODULE, "COMPLETED",
                (
                    f"Memo Generation Pipeline COMPLETED for {self.ticker}. "
                    f"Generated {sections_completed}/17 sections ({sections_failed} failed). "
                    f"Final report: {output_path.name} ({file_size_kb:.1f} KB). "
                    f"Verification: {verification.get('data_points_with_value', 0)}/"
                    f"{verification.get('total_data_points', 0)} data points verified, "
                    f"{verification.get('cross_checks_passed', 0)}/"
                    f"{verification.get('cross_checks_total', 0)} cross-checks passed. "
                    f"Data integrity certificate written."
                ),
            )

            logger.info(f"🎉 Investment Memo Generated: {output_path}")
            return output_path

        except Exception as e:
            log_audit_event(
                self.audit_log, AGENT_NAME, PIPELINE_MODULE, "FAILED",
                f"Memo Generation Pipeline FAILED: {type(e).__name__}: {e}",
            )
            raise


def run_memo_agent(ticker: str, run_id: str) -> Path:
    """Convenience function to run the Memo Generation Agent.

    Args:
        ticker: Company ticker symbol.
        run_id: Run ID from a previous pipeline run.

    Returns:
        Path to the generated HTML memo.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-40s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    agent = MemoGenerationAgent(ticker=ticker, run_id=run_id)
    return agent.run()


# ═══════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m agents.memo_generation.memo_generation_agent <TICKER> <RUN_ID>")
        print("Example: python -m agents.memo_generation.memo_generation_agent MSFT MSFT_20260718_104347")
        sys.exit(1)

    ticker_arg = sys.argv[1]
    run_id_arg = sys.argv[2]

    result_path = run_memo_agent(ticker_arg, run_id_arg)
    print(f"\n[SUCCESS] Investment Memo Generated: {result_path}")
