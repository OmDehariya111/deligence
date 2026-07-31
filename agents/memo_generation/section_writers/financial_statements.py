"""
Module: financial_statements.py
Agent: Memo Generation Agent
Purpose: Generates the 5-Year Financial Statements (Section 3) of the investment memo.
Inputs: Data dictionary containing structured financial statement data.
Outputs: HTML string for the financial statements section including tables and charts.
"""
import logging
from typing import Any
from agents.memo_generation import chart_engine

logger = logging.getLogger(__name__)

def format_number(val, is_currency=False, is_percent=False):
    if val is None:
        return "N/A"
    try:
        val = float(val)
    except (ValueError, TypeError):
        return str(val)
        
    prefix = "$" if is_currency else ""
    suffix = ""
    if is_percent:
        return f"{val:.1f}%"
        
    abs_val = abs(val)
    if abs_val >= 1e9:
        num = val / 1e9
        suffix = "B"
    elif abs_val >= 1e6:
        num = val / 1e6
        suffix = "M"
    else:
        num = val
        if is_currency:
            return f"${val:,.2f}" if val >= 0 else f"(${abs_val:,.2f})"
        else:
            return f"{val:,.2f}"

    if val < 0:
        return f"({prefix}{abs(num):.1f}{suffix})"
    return f"{prefix}{num:.1f}{suffix}"

class Section3Writer:
    def __init__(self, data: dict):
        self.data = data
        
    def generate(self) -> str:
        financials = self.data.get('financial_data', [])
        financials = sorted(financials, key=lambda x: str(x.get('fiscal_year', '0')))
        years = [str(f.get('fiscal_year', 'N/A')) for f in financials]
        
        def build_row(label, field, is_currency=True):
            cells = [f"<td><strong>{label}</strong></td>"]
            for f_data in financials:
                val = f_data.get(field)
                fmt_val = format_number(val, is_currency=is_currency)
                cls = "num negative" if val is not None and isinstance(val, (int, float)) and val < 0 else "num positive" if val is not None and isinstance(val, (int, float)) and val > 0 else "num"
                cells.append(f"<td class='{cls}'>{fmt_val}</td>")
            return f"<tr>{''.join(cells)}</tr>"

        th_years = "".join([f"<th class='num'>{y}</th>" for y in years])
        
        is_html = f"""
        <table class="compact">
            <thead><tr><th>Income Statement</th>{th_years}</tr></thead>
            <tbody>
                {build_row('Revenue', 'revenue')}
                {build_row('Cost of Revenue', 'cost_of_revenue')}
                {build_row('Gross Profit', 'gross_profit')}
                {build_row('SG&A Expense', 'sga_expense')}
                {build_row('R&D Expense', 'rd_expense')}
                {build_row('Operating Income', 'operating_income')}
                {build_row('Interest Expense', 'interest_expense')}
                {build_row('Income Before Tax', 'income_before_tax')}
                {build_row('Income Tax Expense', 'income_tax_expense')}
                {build_row('Net Income', 'net_income')}
                {build_row('EPS (Diluted)', 'eps_diluted', is_currency=True)}
            </tbody>
        </table>
        """
        
        bs_html = f"""
        <table class="compact">
            <thead><tr><th>Balance Sheet</th>{th_years}</tr></thead>
            <tbody>
                {build_row('Total Assets', 'total_assets')}
                {build_row('Current Assets', 'current_assets')}
                {build_row('Cash & Equivalents', 'cash_and_equivalents')}
                {build_row('Accounts Receivable', 'accounts_receivable')}
                {build_row('Inventory', 'inventory')}
                {build_row('PP&E (Net)', 'ppe_net')}
                {build_row('Goodwill', 'goodwill')}
                {build_row('Total Liabilities', 'total_liabilities')}
                {build_row('Current Liabilities', 'current_liabilities')}
                {build_row('Long-Term Debt', 'long_term_debt')}
                {build_row('Total Equity', 'total_equity')}
                {build_row('Retained Earnings', 'retained_earnings')}
            </tbody>
        </table>
        """
        
        cf_html = f"""
        <table class="compact">
            <thead><tr><th>Cash Flow Statement</th>{th_years}</tr></thead>
            <tbody>
                {build_row('Operating Cash Flow', 'operating_cash_flow')}
                {build_row('Capital Expenditures', 'capital_expenditures')}
                {build_row('Free Cash Flow', 'free_cash_flow')}
                {build_row('Investing Cash Flow', 'investing_cash_flow')}
                {build_row('Financing Cash Flow', 'financing_cash_flow')}
                {build_row('D&A', 'depreciation_and_amortization')}
                {build_row('Dividends Paid', 'dividends_paid')}
                {build_row('Share Buybacks', 'stock_buybacks')}
            </tbody>
        </table>
        """
        
        derived_html = f"""
        <table class="compact">
            <thead><tr><th>Derived Metrics</th>{th_years}</tr></thead>
            <tbody>
                {build_row('EBITDA', 'ebitda')}
                {build_row('Net Debt', 'net_debt')}
                {build_row('Working Capital', 'working_capital')}
            </tbody>
        </table>
        """
        
        rev_data = [f.get('revenue', 0) or 0 for f in financials]
        ni_data = [f.get('net_income', 0) or 0 for f in financials]
        
        combo = chart_engine.combo_chart(
            labels=years,
            bar_datasets=[{"label": "Revenue", "data": rev_data, "color": "#1B2A4A"}],
            line_datasets=[{"label": "Net Income", "data": ni_data, "color": "#10B981"}],
            title="Revenue vs Net Income",
            y_label="Revenue ($)",
            y2_label="Net Income ($)",
            currency_format=True
        )
        
        asset_data = [f.get('total_assets', 0) or 0 for f in financials]
        liab_data = [f.get('total_liabilities', 0) or 0 for f in financials]
        equity_data = [f.get('total_equity', 0) or 0 for f in financials]
        
        bs_chart = chart_engine.bar_chart(
            labels=years,
            datasets=[
                {"label": "Liabilities", "data": liab_data, "color": "#EF4444"},
                {"label": "Equity", "data": equity_data, "color": "#10B981"},
            ],
            title="Balance Sheet Composition",
            stacked=True,
            currency_format=True
        )
        
        ocf_data = [(f.get('operating_cash_flow', 0) or 0) / 1e9 for f in financials]
        cf_waterfall = chart_engine.bar_chart(
            labels=years,
            datasets=[
                {"label": "Operating Cash Flow", "data": ocf_data, "color": "#4A90D9"}
            ],
            title="Cash Flow Waterfall",
            stacked=False,
            y_label="$ Billions"
        )
        
        html = f"""
        <div class="section" id="financial-statements">
            <div class="section-header">
                <span class="section-number">3</span>
                <h2>5-Year Financial Statements</h2>
            </div>
            
            <div class="grid-2" style="margin-bottom: 1rem;">
                <div class="card">{combo}</div>
                <div class="card">{bs_chart}</div>
                <div class="card" style="grid-column: span 2;">{cf_waterfall}</div>
            </div>
            
            <div class="card" style="margin-bottom: 1rem;">
                <div class="card-header">Income Statement</div>
                <div class="table-container">{is_html}</div>
            </div>
            
            <div class="card" style="margin-bottom: 1rem;">
                <div class="card-header">Balance Sheet</div>
                <div class="table-container">{bs_html}</div>
            </div>
            
            <div class="card" style="margin-bottom: 1rem;">
                <div class="card-header">Cash Flow Statement</div>
                <div class="table-container">{cf_html}</div>
            </div>
            
            <div class="card" style="margin-bottom: 1rem;">
                <div class="card-header">Derived Metrics</div>
                <div class="table-container">{derived_html}</div>
            </div>
        </div>
        """
        return html
