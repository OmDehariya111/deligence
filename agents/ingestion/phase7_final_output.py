"""Phase 7: Final Output Package."""
# Ye phase Ingestion Agent ka 'Delivery Boy' aur 'Archiver' hai.
# Pichle 6 phases ne jitni bhi mehnat ki, un sab data ko ikhatta karke, SQLite database me hamesha ke liye save karna,
# aur DeligenX platform ko ek summary (receipt) JSON dena iska main kaam hai.
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, Table, Column, Integer, String, Float, text, JSON

from tools.sqlite_tools import DatabaseManager
from utils.audit_logger import log_audit_event
from schemas.pydantic_models import (
    Phase5Result,
    CompanyIdentity,
    IngestionSummary,
    FieldCoverageSummary,
    VectorDatabaseStats
)

logger = logging.getLogger(__name__)

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def run_phase7(
    run_id: str,
    company_identity: CompanyIdentity,
    vector_stats: VectorDatabaseStats,
    phase5_result: Phase5Result,
    paths: dict[str, Path],
    module_status: dict[str, str],
    start_time: float,
    errors: list[str] = None
) -> IngestionSummary:
    """Run Phase 7 final output generation and SQLite storage."""
    
    if errors is None:
        errors = []
        
    history = phase5_result.financial_history
    warnings = phase5_result.warnings
    missing_fields = phase5_result.missing_fields
    
    log_audit_event(
        paths["AUDIT_LOG_PATH"],
        agent="IngestionAgent",
        module="PHASE_7_FINAL_OUTPUT",
        status="STARTED",
        summary=f"Writing final outputs for {history.ticker}"
    )
    
    # 1. Write to SQLite
    db = DatabaseManager(paths["SQLITE_DB_PATH"])
    metadata = MetaData()
    
    # Define financial_data table
    columns = [
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker", String, nullable=False),
        Column("cik", String, nullable=False),
        Column("fiscal_year", Integer, nullable=False),
        Column("revenue", Float),
        Column("cost_of_revenue", Float),
        Column("gross_profit", Float),
        Column("sga_expense", Float),
        Column("rd_expense", Float),
        Column("operating_income", Float),
        Column("interest_expense", Float),
        Column("income_before_tax", Float),
        Column("income_tax_expense", Float),
        Column("net_income", Float),
        Column("eps_basic", Float),
        Column("eps_diluted", Float),
        Column("non_operating_income", Float),
        
        Column("total_assets", Float),
        Column("current_assets", Float),
        Column("cash_and_equivalents", Float),
        Column("short_term_investments", Float),
        Column("accounts_receivable", Float),
        Column("inventory", Float),
        Column("ppe_net", Float),
        Column("goodwill", Float),
        Column("intangible_assets", Float),
        
        Column("total_liabilities", Float),
        Column("current_liabilities", Float),
        Column("accounts_payable", Float),
        Column("short_term_debt", Float),
        Column("long_term_debt", Float),
        Column("total_equity", Float),
        Column("retained_earnings", Float),
        Column("shares_outstanding", Float),
        Column("weighted_avg_shares", Float),
        
        Column("operating_cash_flow", Float),
        Column("capital_expenditures", Float),
        Column("depreciation_and_amortization", Float),
        Column("free_cash_flow", Float),
        Column("investing_cash_flow", Float),
        Column("financing_cash_flow", Float),
        Column("dividends_paid", Float),
        Column("stock_buybacks", Float),
        
        Column("ebitda", Float),
        Column("net_debt", Float),
        Column("working_capital", Float),
        
        Column("stock_price_fy_end", Float),
        Column("market_cap", Float),
        
        Column("metadata", JSON)
    ]
    fin_table = Table("financial_data", metadata, *columns)
    
    # Define market_profile table
    profile_table = Table(
        "market_profile", metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker", String, nullable=False, unique=True),
        Column("company_name", String, nullable=False),
        Column("beta", Float)
    )
    
    # Create tables
    metadata.create_all(db.get_engine())
    
    # Insert data
    with db.get_engine().begin() as conn:
        # Market profile
        conn.execute(profile_table.delete().where(profile_table.c.ticker == history.ticker))
        conn.execute(profile_table.insert().values(
            ticker=history.ticker,
            company_name=history.company_name,
            beta=history.beta
        ))
        
        # Financial data
        conn.execute(fin_table.delete().where(fin_table.c.ticker == history.ticker))
        for fin in history.annual_data:
            row_dict = fin.model_dump(exclude_none=True)
            row_dict["ticker"] = history.ticker
            row_dict["cik"] = history.cik
            
            # Extract metadata for this specific year
            year = fin.fiscal_year
            year_meta = {}
            for field, field_meta_dict in history.field_metadata.items():
                if year in field_meta_dict:
                    meta_item = field_meta_dict[year]
                    if hasattr(meta_item, 'model_dump'):
                        year_meta[field] = meta_item.model_dump(exclude_none=True)
                    else:
                        year_meta[field] = meta_item
            row_dict["metadata"] = year_meta
            
            conn.execute(fin_table.insert().values(**row_dict))
            
    # 2. Compile Coverage Stats
    years = sorted([fin.fiscal_year for fin in history.annual_data])
    
    total_fields = 0
    fields_with_data = 0
    
    for fin in history.annual_data:
        data_dict = fin.model_dump(exclude={"fiscal_year"})
        for val in data_dict.values():
            total_fields += 1
            if val is not None:
                fields_with_data += 1
                
    # Bug Fix: fields_computed ko 0 hardcode karne ke bajaaye proper count karte hain
    fields_computed = 0
    for year_meta_dict in history.field_metadata.values():
        for meta in year_meta_dict.values():
            if isinstance(meta, dict) and meta.get("source") == "computed":
                fields_computed += 1
            elif hasattr(meta, 'source') and meta.source == "computed":
                fields_computed += 1
                
    field_coverage = FieldCoverageSummary(
        total_fields=total_fields,
        fields_with_data=fields_with_data,
        fields_missing=total_fields - fields_with_data,
        fields_computed=fields_computed
    )
    
    # 3. Create Summary JSON
    status = "COMPLETE"
    if errors:
        status = "ERROR"
    elif warnings or missing_fields:
        status = "COMPLETE_WITH_WARNINGS"
        
    duration = int(time.time() - start_time)
    
    summary = IngestionSummary(
        run_id=run_id,
        status=status,
        module_status=module_status,
        company_identity=company_identity,
        financial_data_coverage={"years_covered": years, "years_missing": []},
        field_coverage_summary=field_coverage,
        missing_critical_fields=missing_fields,
        vector_database_stats=vector_stats,
        field_metadata=history.field_metadata,
        warnings=warnings,
        errors=errors,
        ingestion_timestamp=_now_iso(),
        ingestion_duration_seconds=duration
    )
    
    out_path = paths["INGESTION_SUMMARY_PATH"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(summary.model_dump_json(indent=2))
    
    # Phase 7 ka apna independent completion log taaki uska duration bhi accurately aaye
    log_audit_event(
        paths["AUDIT_LOG_PATH"],
        agent="IngestionAgent",
        module="PHASE_7_FINAL_OUTPUT",
        status="COMPLETED" if status != "ERROR" else "FAILED",
        summary=f"Final output package successfully written to {paths['INGESTION_SUMMARY_PATH'].name}."
    )
    
    # Ye poore pipeline ka main End log hai, jiska module naam INGESTION_PIPELINE rakha gaya hai taaki total time nikal sake
    log_audit_event(
        paths["AUDIT_LOG_PATH"],
        agent="IngestionAgent",
        module="INGESTION_PIPELINE",
        status="COMPLETED" if status != "ERROR" else "FAILED",
        summary=f"Ingestion complete for {history.ticker}. {fields_with_data}/{total_fields} fields. Status={status}."
    )
    
    return summary
