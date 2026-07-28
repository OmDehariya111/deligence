"""Phase 5: Arithmetic Validation and Gap Filling."""
# Ye phase Ingestion system ka 'Quality Assurance (QA) Inspector' hai.
# Iska main kaam ye check karna hai ki kya SEC se nikale gaye numbers mathematical rules (jaise Assets = Liab + Equity) ko follow kar rahe hain ya nahi.
# Agar koi number chhut gaya ho, toh ye check karta hai ki kya use baaki numbers se derive kiya ja sakta hai (Gap Filling).
import logging
from pathlib import Path
from collections import defaultdict

from utils.audit_logger import log_audit_event
from schemas.pydantic_models import CompanyFinancialHistory, Phase5Result, MissingFieldLog

logger = logging.getLogger(__name__)

# Define criticality and impacts for all fields according to specs
FIELD_METADATA = {
    # Income Statement
    "revenue": {"criticality": "HIGH", "impact": "All margins and growth ratios cannot be computed."},
    "cost_of_revenue": {"criticality": "HIGH", "impact": "Gross margin cannot be computed."},
    "gross_profit": {"criticality": "HIGH", "impact": "Gross margin cannot be computed."},
    "sga_expense": {"criticality": "HIGH", "impact": "Beneish SGAI cannot be computed."},
    "rd_expense": {"criticality": "MEDIUM", "impact": "R&D margin cannot be computed. Treat as zero if appropriate."},
    "operating_income": {"criticality": "HIGH", "impact": "Operating margin and most profitability ratios cannot be computed."},
    "interest_expense": {"criticality": "HIGH", "impact": "Interest Coverage Ratio cannot be computed."},
    "income_before_tax": {"criticality": "HIGH", "impact": "Effective tax rate cannot be computed."},
    "income_tax_expense": {"criticality": "HIGH", "impact": "Effective tax rate cannot be computed."},
    "net_income": {"criticality": "HIGH", "impact": "All bottom-line ratios (ROE, ROA, P/E) cannot be computed."},
    "eps_basic": {"criticality": "HIGH", "impact": "EPS trend cannot be computed."},
    "eps_diluted": {"criticality": "HIGH", "impact": "EPS trend and validation cannot be computed."},
    "non_operating_income": {"criticality": "HIGH", "impact": "Quality of Earnings signal (Anomaly Detection) cannot be computed."},
    
    # Balance Sheet
    "total_assets": {"criticality": "HIGH", "impact": "ROA and Altman Z-Score cannot be computed."},
    "current_assets": {"criticality": "HIGH", "impact": "Liquidity ratios (Current Ratio) cannot be computed."},
    "cash_and_equivalents": {"criticality": "HIGH", "impact": "Cash Ratio and Net Debt cannot be computed."},
    "short_term_investments": {"criticality": "MEDIUM", "impact": "Used in liquidity if available."},
    "accounts_receivable": {"criticality": "HIGH", "impact": "DSO and Beneish DSRI cannot be computed."},
    "inventory": {"criticality": "HIGH", "impact": "CCC and Inventory Turnover cannot be computed."},
    "ppe_net": {"criticality": "HIGH", "impact": "Beneish AQI cannot be computed."},
    "goodwill": {"criticality": "HIGH", "impact": "Impairment risk cannot be computed."},
    "intangible_assets": {"criticality": "MEDIUM", "impact": "Used in total intangible analysis."},
    "total_liabilities": {"criticality": "HIGH", "impact": "Leverage and Altman X4 cannot be computed."},
    "current_liabilities": {"criticality": "HIGH", "impact": "Liquidity ratios and Working Capital cannot be computed."},
    "accounts_payable": {"criticality": "HIGH", "impact": "DPO and CCC cannot be computed."},
    "short_term_debt": {"criticality": "HIGH", "impact": "Net debt cannot be computed."},
    "long_term_debt": {"criticality": "HIGH", "impact": "Leverage ratios cannot be computed."},
    "total_equity": {"criticality": "HIGH", "impact": "ROE and D/E cannot be computed."},
    "retained_earnings": {"criticality": "HIGH", "impact": "Altman X2 cannot be computed."},
    "shares_outstanding": {"criticality": "HIGH", "impact": "Market Cap cannot be computed."},
    "weighted_avg_shares": {"criticality": "HIGH", "impact": "EPS validation cannot be computed."},
    
    # Cash Flow
    "operating_cash_flow": {"criticality": "HIGH", "impact": "FCF and OCF ratios cannot be computed."},
    "capital_expenditures": {"criticality": "HIGH", "impact": "FCF and CapEx ratios cannot be computed."},
    "depreciation_and_amortization": {"criticality": "HIGH", "impact": "EBITDA cannot be computed."},
    "free_cash_flow": {"criticality": "HIGH", "impact": "FCF ratios cannot be computed."},
    "investing_cash_flow": {"criticality": "MEDIUM", "impact": "Used in cash flow breakdown."},
    "financing_cash_flow": {"criticality": "MEDIUM", "impact": "Used in cash flow breakdown."},
    "dividends_paid": {"criticality": "MEDIUM", "impact": "Dividend yield/payout cannot be computed."},
    "stock_buybacks": {"criticality": "MEDIUM", "impact": "Shareholder yield cannot be computed."},
    
    # Derived & Market
    "ebitda": {"criticality": "HIGH", "impact": "Leverage ratios (Net Debt/EBITDA, EV/EBITDA) cannot be computed."},
    "net_debt": {"criticality": "HIGH", "impact": "Net leverage cannot be computed."},
    "working_capital": {"criticality": "HIGH", "impact": "Altman X1 cannot be computed."},
    "stock_price_fy_end": {"criticality": "HIGH", "impact": "Market Cap and valuation ratios cannot be computed."},
    "market_cap": {"criticality": "HIGH", "impact": "Altman X4 and valuation ratios cannot be computed."},
}

def run_phase5(history: CompanyFinancialHistory, paths: dict[str, Path]) -> Phase5Result:
    """Run Phase 5 arithmetic validation and gap filling."""
    
    log_audit_event(
        paths["AUDIT_LOG_PATH"],
        agent="IngestionAgent",
        module="PHASE_5_VALIDATION",
        status="STARTED",
        summary=f"Validating financial data for {history.ticker}"
    )
    
    warnings = []
    
    # 1. GAAP Arithmetic Cross-Checks
    for fin in history.annual_data:
        year = fin.fiscal_year
        
        # Cross-Check 1: Income Statement Consistency
        if fin.revenue is not None and fin.cost_of_revenue is not None:
            implied_gross_profit = fin.revenue - fin.cost_of_revenue
            if fin.gross_profit is not None:
                if fin.revenue != 0 and abs(implied_gross_profit - fin.gross_profit) / abs(fin.revenue) > 0.005:
                    warnings.append(f"FY{year}: Gross Profit inconsistency. Implied {implied_gross_profit} vs Stored {fin.gross_profit}")
            else:
                fin.gross_profit = implied_gross_profit
                if "gross_profit" not in history.field_metadata:
                    history.field_metadata["gross_profit"] = {}
                history.field_metadata["gross_profit"][year] = {
                    "source": "computed",
                    "computation_method": "revenue - cost_of_revenue"
                }
                
        # Cross-Check 2: Balance Sheet Equation
        if fin.total_liabilities is not None and fin.total_equity is not None and fin.total_assets is not None:
            implied_assets = fin.total_liabilities + fin.total_equity
            if fin.total_assets != 0 and abs(implied_assets - fin.total_assets) / abs(fin.total_assets) > 0.005:
                warnings.append(f"FY{year}: Balance Sheet does not balance. Assets {fin.total_assets} != Liab+Eq {implied_assets}")
                
        # Cross-Check 3: EPS Validation
        if fin.net_income is not None and fin.weighted_avg_shares is not None and fin.eps_diluted is not None:
            if fin.weighted_avg_shares != 0:
                implied_eps = fin.net_income / fin.weighted_avg_shares
                if fin.eps_diluted != 0 and abs(implied_eps - fin.eps_diluted) / abs(fin.eps_diluted) > 0.05:
                    warnings.append(f"FY{year}: EPS mismatch. Implied {implied_eps} vs Stored {fin.eps_diluted}")
                    
        # Cross-Check 4: FCF Verification
        if fin.operating_cash_flow is not None:
            # Bug Fix: CapEx agar None hai toh use 0.0 maan kar check karenge (Jaisa Phase 4 me theek kiya tha)
            implied_fcf = fin.operating_cash_flow - (fin.capital_expenditures or 0.0)
            if fin.free_cash_flow is not None:
                # Agar FCF pehle se hai, toh check karo ki kya dono match karte hain?
                if abs(implied_fcf - fin.free_cash_flow) > 1000: # 1000 ki choti error margin rakhi hai
                    warnings.append(f"FY{year}: Free Cash Flow inconsistency. Implied {implied_fcf} vs Stored {fin.free_cash_flow}")
            else:
                # Agar FCF nahi hai, tab isse gap-fill (compute) karo
                fin.free_cash_flow = implied_fcf
                if "free_cash_flow" not in history.field_metadata:
                    history.field_metadata["free_cash_flow"] = {}
                history.field_metadata["free_cash_flow"][year] = {
                    "source": "computed",
                    "computation_method": "operating_cash_flow - (capital_expenditures or 0)"
                }
            
        # Cross-Check 5: Income Before Tax Derivation
        if fin.income_before_tax is None and fin.net_income is not None and fin.income_tax_expense is not None:
            fin.income_before_tax = fin.net_income + fin.income_tax_expense
            if "income_before_tax" not in history.field_metadata:
                history.field_metadata["income_before_tax"] = {}
            history.field_metadata["income_before_tax"][year] = {
                "source": "computed",
                "computation_method": "net_income + income_tax_expense"
            }
            
    # 2. Compile MISSING Fields Log
    missing_by_field = defaultdict(list)
    for fin in history.annual_data:
        data_dict = fin.model_dump()
        for field, value in data_dict.items():
            if field == "fiscal_year":
                continue
            if value is None:
                missing_by_field[field].append(fin.fiscal_year)
                
    missing_fields = []
    for field, years in missing_by_field.items():
        meta = FIELD_METADATA.get(field, {"criticality": "MEDIUM", "impact": "Unknown impact"})
        criticality = "HIGH" if meta["criticality"] in ("HIGH", "YES") else "MEDIUM"
        reason = "Company did not report this field or uses non-standard XBRL tags."
        
        if field == "interest_expense":
            reason = "Company may report interest net of income, or has no debt."
        elif field == "inventory":
            reason = "Company may be a services/technology firm carrying minimal inventory."
        elif field == "stock_price_fy_end" or field == "market_cap":
            reason = "yfinance returned no historical price data for this ticker/date."
            
        missing_fields.append(MissingFieldLog(
            field=field,
            years=sorted(years),
            impact=meta["impact"],
            criticality=criticality,
            reason=reason
        ))
        
    result = Phase5Result(
        financial_history=history,
        warnings=warnings,
        missing_fields=missing_fields
    )
    
    log_audit_event(
        paths["AUDIT_LOG_PATH"],
        agent="IngestionAgent",
        module="PHASE_5_VALIDATION",
        status="COMPLETED",
        summary=f"Validation completed. {len(warnings)} warnings, {len(missing_fields)} fields with missing data."
    )
    
    return result
