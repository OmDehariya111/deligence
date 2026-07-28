"""
Module:  ratio_analysis.py
Agent:   Memo Generation Agent
Purpose: Generates Section 4: Financial Ratio Analysis
Inputs:  data dictionary containing 'ratio_database', 'trend_analysis', 'qoe_summary'
Outputs: HTML string for the section.
"""
import logging
from collections import defaultdict
from typing import Any

from agents.memo_generation import chart_engine
from agents.memo_generation import llm_narrator

logger = logging.getLogger(__name__)

class Section4Writer:
    def __init__(self, data: dict):
        self.data = data
        self.ratio_db = data.get('ratio_database', [])
        self.trend_analysis = data.get('trend_analysis', [])
        
        # Determine trends
        self.trends = {}
        for t in self.trend_analysis:
            self.trends[t.get('ratio_name')] = t

    def format_value(self, val: Any, unit: str) -> str:
        if val is None:
            return "N/A"
        try:
            v = float(val)
            if unit == 'percentage':
                return f"{v:.1f}%"
            elif unit == 'multiple':
                return f"{v:.2f}x"
            elif unit == 'days':
                return f"{v:.0f}"
            else:
                return f"{v:,.2f}"
        except (ValueError, TypeError):
            return "N/A"

    def get_trend_arrow(self, direction: str) -> str:
        d = direction.upper() if direction else ""
        if d == "IMPROVING":
            return "<span class='text-success'>↑</span>"
        elif d == "DECLINING":
            return "<span class='text-danger'>↓</span>"
        elif d == "STABLE":
            return "<span class='text-slate'>→</span>"
        elif d == "VOLATILE":
            return "<span class='text-warning'>↕</span>"
        return "→"

    def extract_time_series(self, metric_names: list, category_db: list) -> tuple:
        """Extract labels (years) and datasets for charts."""
        # Find all years
        years = set()
        for r in category_db:
            if r.get('ratio_name') in metric_names:
                years.add(str(r.get('fiscal_year')))
        years_list = sorted(list(years))
        
        datasets = []
        for name in metric_names:
            data = []
            for y in years_list:
                val = next((r.get('value') for r in category_db if r.get('ratio_name') == name and str(r.get('fiscal_year')) == y), None)
                data.append(val if val is not None else 0)
            datasets.append({"label": name.replace('_', ' ').title(), "data": data})
            
        return years_list, datasets

    def generate(self) -> str:
        # Group by category, then ratio name, then fiscal year
        categories = defaultdict(lambda: defaultdict(dict))
        
        for r in self.ratio_db:
            # We assume category is in ratio record or we infer it
            cat = r.get('category')
            if not cat:
                name = r.get('ratio_name', '').lower()
                if 'margin' in name or 'ro' in name:
                    cat = 'Profitability'
                elif 'ratio' in name and ('current' in name or 'quick' in name or 'cash' in name):
                    cat = 'Liquidity'
                elif 'debt' in name or 'coverage' in name:
                    cat = 'Leverage'
                elif 'turnover' in name or 'days' in name:
                    cat = 'Efficiency'
                elif 'fcf' in name or 'ocf' in name or 'capex' in name:
                    cat = 'Cash Flow Quality'
                elif 'yoy' in name:
                    cat = 'Growth YoY'
                elif 'cagr' in name:
                    cat = 'CAGR'
                elif 'pe_' in name or 'ps_' in name or 'ev_' in name:
                    cat = 'Valuation'
                else:
                    cat = 'Other'
            
            categories[cat][r.get('ratio_name')][str(r.get('fiscal_year'))] = r
            
        all_years = set()
        for r in self.ratio_db:
            if r.get('fiscal_year'):
                all_years.add(str(r.get('fiscal_year')))
        sorted_years = sorted(list(all_years))[-5:] # last 5 years
        
        # Build Table
        table_html = f"""
        <table class="data-table">
            <thead>
                <tr>
                    <th>Category / Ratio</th>
                    {"".join(f"<th>{y}</th>" for y in sorted_years)}
                    <th>Trend</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for cat, ratios in sorted(categories.items()):
            table_html += f"<tr class='section-row'><td colspan='{len(sorted_years) + 2}'><strong>{cat}</strong></td></tr>"
            for r_name, years_data in sorted(ratios.items()):
                row_html = f"<tr><td>{r_name.replace('_', ' ').title()}</td>"
                unit = None
                for y in sorted_years:
                    r_data = years_data.get(y)
                    if r_data:
                        unit = r_data.get('unit', '')
                        val = r_data.get('value')
                        row_html += f"<td>{self.format_value(val, unit)}</td>"
                    else:
                        row_html += "<td>N/A</td>"
                
                trend = self.trends.get(r_name, {})
                direction = trend.get('trend_direction', '')
                arrow = self.get_trend_arrow(direction)
                
                row_html += f"<td style='text-align:center;'>{arrow}</td></tr>"
                table_html += row_html
                
        table_html += "</tbody></table>"

        # Generate LLM Narrative
        narrative_data = {
            'company_name': self.data.get('company_info', {}).get('company_name', 'The Company'),
            'ticker': self.data.get('company_info', {}).get('ticker', 'N/A'),
            'key_ratios_text': f"Total Ratios: {len(self.ratio_db)}",
            'improving_trends': sum(1 for t in self.trend_analysis if t.get('trend_direction') == 'IMPROVING'),
            'declining_trends': sum(1 for t in self.trend_analysis if t.get('trend_direction') == 'DECLINING'),
            'sudden_changes': sum(1 for t in self.trend_analysis if t.get('sudden_changes')),
            'benchmark_text': 'N/A'
        }
        narrative = llm_narrator.generate_ratio_analysis_narrative(narrative_data)

        # Generate Charts
        # Profitability
        prof_years, prof_data = self.extract_time_series(['gross_margin', 'operating_margin', 'net_profit_margin', 'ebitda_margin'], self.ratio_db)
        prof_chart = chart_engine.line_chart(prof_years, prof_data, title="Profitability Margin Trends", y_label="Margin (%)")
        
        # Liquidity
        liq_years, liq_data = self.extract_time_series(['current_ratio', 'quick_ratio', 'cash_ratio'], self.ratio_db)
        liq_chart = chart_engine.bar_chart(liq_years, liq_data, title="Liquidity Ratios", y_label="Multiple (x)")
        
        # Leverage Combo
        lev_years, lev_data_bar = self.extract_time_series(['net_debt_to_ebitda'], self.ratio_db)
        _, lev_data_line = self.extract_time_series(['interest_coverage'], self.ratio_db)
        lev_chart = chart_engine.combo_chart(lev_years, lev_data_bar, lev_data_line, title="Leverage & Coverage", y_label="Net Debt / EBITDA (x)", y2_label="Interest Coverage (x)")
        
        # Cash Flow
        cf_years, cf_data = self.extract_time_series(['fcf_margin', 'ocf_to_revenue', 'capex_to_revenue'], self.ratio_db)
        cf_chart = chart_engine.bar_chart(cf_years, cf_data, title="Cash Flow Quality", y_label="Margin (%)")
        
        # Growth
        gr_years, gr_data = self.extract_time_series(['revenue_yoy', 'net_income_yoy', 'eps_diluted_yoy', 'fcf_yoy'], self.ratio_db)
        gr_chart = chart_engine.bar_chart(gr_years, gr_data, title="YoY Growth Metrics", y_label="Growth (%)")

        html = f"""
        <div class="section-container">
            <h2>4. Financial Ratio Analysis</h2>
            
            <div class="narrative-box">
                {narrative}
            </div>
            
            <h3>5-Year Ratio Summary</h3>
            <div class="table-responsive">
                {table_html}
            </div>
            
            <h3>Key Financial Trends</h3>
            <div class="charts-grid">
                <div class="chart-wrapper">{prof_chart}</div>
                <div class="chart-wrapper">{liq_chart}</div>
                <div class="chart-wrapper">{lev_chart}</div>
                <div class="chart-wrapper">{cf_chart}</div>
                <div class="chart-wrapper">{gr_chart}</div>
            </div>
        </div>
        """
        return html
