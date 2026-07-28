"""
Module:  analysis_agent.py
Agent:   Analysis Agent
Purpose: Main orchestrator for the Analysis Agent. Executes the PRE-PROCESSING 
         steps per new_analysis_workflow.md.
         # Ye file Agent ka 'Manager' hai. Ye khud math nahi karta, balki baaki 
         # saare 6 modules ko step-by-step chalata hai aur errors handle karta hai.
Inputs:  ticker, run_id
Outputs: Pre-processed state ready for Module 1.
"""

import json
import logging
from pathlib import Path
from sqlalchemy import text

from config.paths import get_run_paths, ensure_run_dirs
from tools.sqlite_tools import DatabaseManager
from utils.audit_logger import log_audit_event
from utils.analysis_utils import write_skipped_outputs

logger = logging.getLogger(__name__)

class AnalysisAgent:
    """The Analysis Agent orchestrator."""

    def __init__(self, ticker: str, run_id: str):
        self.ticker = ticker.upper().strip()
        self.run_id = run_id
        # Step 0B: Load Shared File Path Constants
        self.paths = get_run_paths(ticker, run_id)
        
        # Ensure the run directories exist
        ensure_run_dirs(self.paths)
        
        # Internal state initialized during pre-processing
        self.financial_data_by_year = {}
        self.current_year = None
        self.prior_year = None
        self.data_depth_mode = None
        self.n_years = 0
        self.missing_fields = []
        self.sic_code = "Unknown"
        self.industry_name = "Unknown"
        
    def run(self) -> None:
        """Run the Analysis Agent's PRE-PROCESSING module."""
        # Main function jo analysis workflow start karta hai
        
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="Analysis Agent",
            module="ANALYSIS_PIPELINE",
            status="STARTED",
            summary=f"Starting Analysis Pipeline for {self.ticker} (Run: {self.run_id})"
        )
        
        # Step 0C: Check Ingestion Summary Status Before Proceeding
        # Sabse pehle check karta hai ki Ingestion Agent (jisne raw data laya tha) fail to nahi hua tha
        ingestion_summary_path = self.paths.get("INGESTION_SUMMARY_PATH")
        qoe_summary_path = self.paths.get("QOE_SUMMARY_PATH")
        
        if not ingestion_summary_path or not ingestion_summary_path.exists():
            error_reason = "Ingestion Summary not found."
            self._handle_critical_error(error_reason)
            return
            
        try:
            with open(ingestion_summary_path, "r", encoding="utf-8") as f:
                self.ingestion_summary = json.load(f)
        except json.JSONDecodeError:
            error_reason = "Ingestion Summary is not valid JSON."
            self._handle_critical_error(error_reason)
            return

        if self.ingestion_summary.get("status") == "ERROR":
            error_reason = "Upstream Ingestion Agent failed: " + str(self.ingestion_summary.get("reason", "Unknown"))
            self._handle_critical_error(error_reason, original_ticker=self.ingestion_summary.get("company_identity", {}).get("ticker"))
            return
            
        self.missing_fields = self.ingestion_summary.get("missing_critical_fields", [])
        
        company_identity = self.ingestion_summary.get("company_identity", {})
        self.sic_code = company_identity.get("sic_code", "Unknown")
        self.industry_name = company_identity.get("industry", "Unknown")
        self.company_name = company_identity.get("name", self.ticker)
            
        # Step 0D: Write Audit Log Entry: Analysis Agent STARTED
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="Analysis Agent",
            module="PRE_PROCESSING",
            status="STARTED",
            summary="Ingestion Summary validated (status=COMPLETE). Beginning ratio computation."
        )

        try:
            self._execute_preprocessing_steps()
            
            # Audit Log Completed for Pre-processing
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="PRE_PROCESSING",
                status="COMPLETED",
                summary=f"Pre-processing completed. Found {self.n_years} years of data. Mode: {self.data_depth_mode}"
            )
            
            # Module 1 (Har module individually call hota hai)
            self._execute_module_1()
            
            # Module 2
            self._execute_module_2()
            
            # Module 3
            self._execute_module_3()
            
            # Module 4
            self._execute_module_4()
            
            # Module 5
            self._execute_module_5()
            
            # Module 6
            self._execute_module_6()
            
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="ANALYSIS_PIPELINE",
                status="COMPLETED",
                summary=f"Analysis Pipeline complete for {self.ticker}. All modules executed successfully."
            )
            
        except Exception as e:
            logger.error(f"Analysis Pipeline failed: {e}")
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="ANALYSIS_PIPELINE",
                status="FAILED",
                summary=f"Analysis Pipeline encountered a fatal error: {e}"
            )
            self._handle_critical_error(f"Analysis Pipeline exception: {e}")

    def _handle_critical_error(self, reason: str, original_ticker: str = None) -> None:
        """Handle a critical failure by writing the ERROR status and SKIPPED placeholders."""
        error_status = {
            "status": "ERROR",
            "reason": reason,
            "ticker": original_ticker or self.ticker
        }
        
        qoe_path = self.paths.get("QOE_SUMMARY_PATH")
        if qoe_path:
            qoe_path.parent.mkdir(parents=True, exist_ok=True)
            with open(qoe_path, "w", encoding="utf-8") as f:
                json.dump(error_status, f, indent=2)
                
        write_skipped_outputs(self.paths, reason="Upstream Ingestion Agent failed.")
        
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="Analysis Agent",
            module="PRE_PROCESSING",
            status="FAILED",
            summary=reason
        )

    def _execute_preprocessing_steps(self) -> None:
        """Executes Steps 1-6 of PRE-PROCESSING."""
        # Raw SQLite database se company ka pichle 5 saalo ka financial data nikal kar memory me load karta hai
        
        # Step 1: Read the complete financial database
        db = DatabaseManager(self.paths["SQLITE_DB_PATH"])
        
        query = text("SELECT * FROM financial_data WHERE ticker = :ticker ORDER BY fiscal_year DESC")
        result = db.execute(query, {"ticker": self.ticker})
        
        rows = result.fetchall()
        
        # Step 3: Build internal data structure (Har saal ke data ko dictionary me store karte hain)
        self.financial_data_by_year = {}
        for row in rows:
            row_dict = row._mapping
            fy = row_dict["fiscal_year"]
            self.financial_data_by_year[fy] = dict(row_dict)
            
        available_years = sorted(self.financial_data_by_year.keys())
        self.n_years = len(available_years)
        
        if self.n_years == 0:
            raise ValueError(f"No financial data found in SQLite for {self.ticker}")

        # Step 4: Identify current and prior year
        self.current_year = available_years[-1]
        self.prior_year = available_years[-2] if self.n_years >= 2 else None
        
        # Step 5: Log which modules can run (Conceptual at this point)
        logger.info(f"Loaded {self.n_years} years. Current Year: {self.current_year}, Prior Year: {self.prior_year}")
        logger.info(f"Missing fields blocking some calculations: {self.missing_fields}")
        
        # Step 6: Set DATA_DEPTH_MODE
        if self.n_years >= 5:
            self.data_depth_mode = "FULL"
        elif self.n_years in [3, 4]:
            self.data_depth_mode = "REDUCED"
        elif self.n_years in [1, 2]:
            self.data_depth_mode = "MINIMAL"
        else:
            self.data_depth_mode = "ERROR"
            
        logger.info(f"DATA_DEPTH_MODE assigned: {self.data_depth_mode}")

    def _execute_module_1(self) -> None:
        from agents.analysis.module1_ratio_engine import RatioEngine
        from sqlalchemy import MetaData, Table, Column, Integer, String, Float
        
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="Analysis Agent",
            module="MODULE_1_RATIO_ENGINE",
            status="STARTED",
            summary="Starting ratio computation."
        )
        
        try:
            engine = RatioEngine(self.financial_data_by_year, self.data_depth_mode, self.n_years)
            ratios = engine.run()
            
            # Save to JSON
            ratio_db_path = self.paths["RATIO_DB_PATH"]
            ratio_db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(ratio_db_path, "w", encoding="utf-8") as f:
                json.dump([r.model_dump() for r in ratios], f, indent=2)
                
            # Save to SQLite
            db = DatabaseManager(self.paths["SQLITE_DB_PATH"])
            metadata = MetaData()
            ratios_table = Table(
                "financial_ratios", metadata,
                Column("id", Integer, primary_key=True, autoincrement=True),
                Column("ticker", String, nullable=False),
                Column("ratio_name", String, nullable=False),
                Column("fiscal_year", Integer, nullable=False),
                Column("value", Float),
                Column("unit", String),
                Column("formula", String),
                Column("inputs_used", String),
                Column("status", String),
                Column("reason", String)
            )
            
            with db.get_connection() as conn:
                ratios_table.create(conn.engine, checkfirst=True)
                # Clear existing for this ticker
                conn.execute(ratios_table.delete().where(ratios_table.c.ticker == self.ticker))
                
                for r in ratios:
                    row = r.model_dump()
                    row["ticker"] = self.ticker
                    row["inputs_used"] = json.dumps(row["inputs_used"])
                    conn.execute(ratios_table.insert().values(**row))
                
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="MODULE_1_RATIO_ENGINE",
                status="COMPLETED",
                summary=f"Computed {len(ratios)} financial ratios covering Profitability, Liquidity, Leverage, Efficiency, Valuation, and Growth."
            )
            
        except Exception as e:
            logger.error(f"Module 1 failed: {e}")
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="MODULE_1_RATIO_ENGINE",
                status="FAILED",
                summary=f"Module 1 failed: {e}"
            )
            self._handle_critical_error(f"Module 1 exception: {e}")

    def _execute_module_2(self) -> None:
        import json
        from agents.analysis.module2_trend_analysis import TrendEngine
        from schemas.pydantic_models import RatioRecord
        
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="Analysis Agent",
            module="MODULE_2_TREND_ANALYSIS",
            status="STARTED",
            summary="Starting trend analysis computation."
        )
        
        trend_path = self.paths["TREND_ANALYSIS_PATH"]
        trend_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.data_depth_mode == "MINIMAL":
            payload = {
                "status": "SKIPPED",
                "reason": "Fewer than 3 fiscal years of data available — trend classification requires at least 3 data points."
            }
            with open(trend_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="MODULE_2_TREND_ANALYSIS",
                status="COMPLETED",
                summary="Skipped due to MINIMAL data depth mode."
            )
            return
            
        try:
            # Read back from Module 1's output
            ratio_db_path = self.paths["RATIO_DB_PATH"]
            with open(ratio_db_path, "r", encoding="utf-8") as f:
                ratios_data = json.load(f)
                
            if isinstance(ratios_data, dict) and ratios_data.get("status"):
                raise ValueError("Upstream Module 1 did not produce a valid list of ratios.")
                
            ratios = [RatioRecord(**r) for r in ratios_data]
            engine = TrendEngine(ratios)
            trends = engine.run()
            
            with open(trend_path, "w", encoding="utf-8") as f:
                json.dump([t.model_dump() for t in trends], f, indent=2)
                
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="MODULE_2_TREND_ANALYSIS",
                status="COMPLETED",
                summary=f"Computed trends for {len(trends)} ratios."
            )
            
        except Exception as e:
            logger.error(f"Module 2 failed: {e}")
            payload = {
                "status": "FAILED",
                "reason": f"Unexpected error during trend analysis: {str(e)}"
            }
            with open(trend_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                
            # Error aane par pipeline crash nahi hoti, ye try/except gracefully error log karke agle module pe chala jata hai
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="MODULE_2_TREND_ANALYSIS",
                status="FAILED",
                summary=f"Module 2 failed: {e}. Recoverable; continuing."
            )

    def _execute_module_3(self) -> None:
        import json
        from agents.analysis.module3_fraud_distress import FraudDistressEngine
        
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="Analysis Agent",
            module="MODULE_3_FRAUD_DISTRESS",
            status="STARTED",
            summary="Starting fraud and distress detection."
        )
        
        fraud_path = self.paths["FRAUD_DISTRESS_PATH"]
        fraud_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            engine = FraudDistressEngine(
                self.financial_data_by_year, 
                self.sic_code, 
                self.data_depth_mode, 
                self.industry_name
            )
            output = engine.run()
            
            with open(fraud_path, "w", encoding="utf-8") as f:
                json.dump(output.model_dump(), f, indent=2)
                
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="MODULE_3_FRAUD_DISTRESS",
                status="COMPLETED",
                summary="Fraud and distress detection complete. Generated Beneish M-Score and Altman Z-Score."
            )
            
        except Exception as e:
            logger.error(f"Module 3 failed: {e}")
            payload = {
                "status": "FAILED",
                "reason": f"Unexpected error during fraud and distress analysis: {str(e)}"
            }
            with open(fraud_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="MODULE_3_FRAUD_DISTRESS",
                status="FAILED",
                summary=f"Module 3 failed: {e}. Recoverable; continuing."
            )

    def _execute_module_4(self) -> None:
        import json
        from agents.analysis.module4_anomaly_detection import AnomalyEngine
        from schemas.pydantic_models import RatioRecord, RatioTrend, FraudDistressOutput
        
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="Analysis Agent",
            module="MODULE_4_ANOMALY_DETECTION",
            status="STARTED",
            summary="Starting anomaly detection engine."
        )
        
        anomaly_path = self.paths["ANOMALY_FLAGS_PATH"]
        anomaly_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            ratios = []
            if self.paths["RATIO_DB_PATH"].exists():
                with open(self.paths["RATIO_DB_PATH"], "r", encoding="utf-8") as f:
                    ratios_data = json.load(f)
                    if isinstance(ratios_data, list):
                        ratios = [RatioRecord(**r) for r in ratios_data]
                    
            trends = []
            if self.paths["TREND_ANALYSIS_PATH"].exists():
                with open(self.paths["TREND_ANALYSIS_PATH"], "r", encoding="utf-8") as f:
                    trends_data = json.load(f)
                    # Ignore skipped/failed payloads when loading list
                    if isinstance(trends_data, list):
                        trends = [RatioTrend(**t) for t in trends_data]
                        
            fraud = None
            if self.paths["FRAUD_DISTRESS_PATH"].exists():
                with open(self.paths["FRAUD_DISTRESS_PATH"], "r", encoding="utf-8") as f:
                    fraud_data = json.load(f)
                    if "status" not in fraud_data: # not a FAILED payload
                        fraud = FraudDistressOutput(**fraud_data)
            
            engine = AnomalyEngine(
                ratios,
                trends,
                fraud,
                self.financial_data_by_year
            )
            output = engine.run()
            
            with open(anomaly_path, "w", encoding="utf-8") as f:
                json.dump(output.model_dump(), f, indent=2)
                
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="MODULE_4_ANOMALY_DETECTION",
                status="COMPLETED",
                summary=f"Anomaly detection complete. Found {output.total_flags} flags across critical, high, medium, and low severity levels."
            )
            
        except Exception as e:
            logger.error(f"Module 4 failed: {e}")
            payload = {
                "status": "FAILED",
                "reason": f"Unexpected error during anomaly detection: {str(e)}"
            }
            with open(anomaly_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="MODULE_4_ANOMALY_DETECTION",
                status="FAILED",
                summary=f"Module 4 failed: {e}. Recoverable; continuing."
            )

    def _execute_module_5(self) -> None:
        import json
        from agents.analysis.module5_sector_benchmark import SectorBenchmarkEngine
        from schemas.pydantic_models import RatioRecord
        
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="Analysis Agent",
            module="MODULE_5_SECTOR_BENCHMARK",
            status="STARTED",
            summary="Starting sector peer benchmarking engine."
        )
        
        bench_path = self.paths["SECTOR_BENCH_JSON"]
        bench_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            ratios = []
            if self.paths["RATIO_DB_PATH"].exists():
                with open(self.paths["RATIO_DB_PATH"], "r", encoding="utf-8") as f:
                    ratios_data = json.load(f)
                    if isinstance(ratios_data, list):
                        ratios = [RatioRecord(**r) for r in ratios_data]
            
            benchmark_year = self.current_year
            if benchmark_year is None:
                raise ValueError("current_year is not set")
                
            engine = SectorBenchmarkEngine(
                ticker=self.ticker,
                sic_code=self.sic_code,
                industry=self.industry_name,
                benchmark_year=benchmark_year,
                target_ratios=ratios
            )
            
            output = engine.run()
            
            with open(bench_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2)
                
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="MODULE_5_SECTOR_BENCHMARK",
                status="COMPLETED",
                summary=f"Sector benchmarking completed with status {output.get('status', 'OK')} against top 20 peers. Computed sector medians and percentiles."
            )
            
        except Exception as e:
            logger.error(f"Module 5 failed: {e}")
            with open(bench_path, "w", encoding="utf-8") as f:
                json.dump({"status": "FAILED", "reason": str(e)}, f, indent=2)
                
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="MODULE_5_SECTOR_BENCHMARK",
                status="FAILED",
                summary=f"Module 5 failed: {e}. Recoverable; continuing."
            )

    def _execute_module_6(self) -> None:
        import json
        import os
        from agents.analysis.module6_qoe_summary import QOESummaryEngine
        from schemas.pydantic_models import RatioRecord, RatioTrend, FraudDistressOutput, AnomalyOutput, BenchmarkOutput
        
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="Analysis Agent",
            module="MODULE_6_QOE_SUMMARY",
            status="STARTED",
            summary="Starting quality of earnings summary engine."
        )
        
        qoe_path = self.paths["QOE_SUMMARY_PATH"]
        qoe_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Load upstream outputs
            ratios = []
            if self.paths["RATIO_DB_PATH"].exists():
                with open(self.paths["RATIO_DB_PATH"], "r", encoding="utf-8") as f:
                    ratios_data = json.load(f)
                    if isinstance(ratios_data, list):
                        ratios = [RatioRecord(**r) for r in ratios_data]
                    
            trends = []
            if self.paths["TREND_ANALYSIS_PATH"].exists():
                with open(self.paths["TREND_ANALYSIS_PATH"], "r", encoding="utf-8") as f:
                    trends_data = json.load(f)
                    if isinstance(trends_data, list):
                        trends = [RatioTrend(**t) for t in trends_data]
                        
            fraud = None
            if self.paths["FRAUD_DISTRESS_PATH"].exists():
                with open(self.paths["FRAUD_DISTRESS_PATH"], "r", encoding="utf-8") as f:
                    f_data = json.load(f)
                    if "status" not in f_data:
                        fraud = FraudDistressOutput(**f_data)
                        
            anomaly = None
            if self.paths["ANOMALY_FLAGS_PATH"].exists():
                with open(self.paths["ANOMALY_FLAGS_PATH"], "r", encoding="utf-8") as f:
                    a_data = json.load(f)
                    if "status" not in a_data:
                        anomaly = AnomalyOutput(**a_data)
                        
            benchmark = None
            if self.paths["SECTOR_BENCH_JSON"].exists():
                with open(self.paths["SECTOR_BENCH_JSON"], "r", encoding="utf-8") as f:
                    b_data = json.load(f)
                    if "status" not in b_data:
                        benchmark = BenchmarkOutput(**b_data)
                        
            # Determine module statuses based on file existence/content
            module_statuses = {}
            for path, name in [
                (self.paths["RATIO_DB_PATH"], "MODULE_1_RATIO_ENGINE"),
                (self.paths["TREND_ANALYSIS_PATH"], "MODULE_2_TREND_ANALYSIS"),
                (self.paths["FRAUD_DISTRESS_PATH"], "MODULE_3_FRAUD_DISTRESS"),
                (self.paths["ANOMALY_FLAGS_PATH"], "MODULE_4_ANOMALY_DETECTION"),
                (self.paths["SECTOR_BENCH_JSON"], "MODULE_5_SECTOR_BENCHMARK")
            ]:
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and data.get("status") in ["SKIPPED", "FAILED", "PARTIAL"]:
                            module_statuses[name] = data["status"]
                        else:
                            module_statuses[name] = "COMPLETE"
                else:
                    module_statuses[name] = "FAILED"
                    
            engine = QOESummaryEngine(
                ticker=self.ticker,
                company_name=self.company_name or self.ticker,
                run_id=self.run_id,
                n_years=self.n_years,
                data_depth_mode=self.data_depth_mode,
                ingestion_summary=self.ingestion_summary,
                ratios=ratios,
                trends=trends,
                fraud=fraud,
                anomaly=anomaly,
                benchmark=benchmark,
                module_statuses=module_statuses
            )
            
            output = engine.run()
            
            with open(qoe_path, "w", encoding="utf-8") as f:
                json.dump(output.model_dump(), f, indent=2)
                
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="Analysis Agent",
                module="MODULE_6_QOE_SUMMARY",
                status="COMPLETED",
                summary=f"Quality of earnings summary generated (Score: {output.earnings_quality_score}, Label: {output.earnings_quality_label})."
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._handle_critical_error(f"Module 6 failed (critical): {e}")

if __name__ == "__main__":
    pass
