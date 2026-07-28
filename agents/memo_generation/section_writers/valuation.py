"""
Module:  valuation.py
Agent:   Memo Generation Agent
Purpose: Generates Section 11 (Implied Valuation Analysis) for the investment memo.
Inputs:  data dictionary containing 'implied_valuation' and market data
Outputs: HTML string for the valuation section.
"""

import logging
from agents.memo_generation import chart_engine

logger = logging.getLogger(__name__)

class Section11Writer:
    def __init__(self, data: dict):
        self.data = data

    def generate(self) -> str:
        implied_val = self.data.get('market_intel_summary', {}).get('IMPLIED_VALUATION', {})
        comp_data = self.data.get('competitor_market_data', [])
        
        # Get target current price
        target_ticker = self.data.get('ticker', 'TARGET')
        current_price = 0.0
        for cd in comp_data:
            if cd.get('ticker') == target_ticker or cd.get('is_target'):
                current_price = cd.get('current_price', 0.0)
                break
        
        # If we couldn't find it in comp_data, we can estimate it from the first valuation method
        if current_price == 0.0 and implied_val:
            first_val = list(implied_val.values())[0]
            base = first_val.get('implied_ps_base', 0)
            pct = first_val.get('upside_downside_pct', 0) / 100.0
            if (1 + pct) != 0:
                current_price = base / (1 + pct)

        val_table_html = """
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Method</th>
                        <th class="num">Low Implied Price</th>
                        <th class="num">Base Implied Price</th>
                        <th class="num">High Implied Price</th>
                        <th class="num">Vs Current Price</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        methods = []
        vs_prices = []
        
        for method_name, row in implied_val.items():
            p_low = row.get('implied_ps_low', 0)
            p_base = row.get('implied_ps_base', 0)
            p_high = row.get('implied_ps_high', 0)
            vs_cur = row.get('upside_downside_pct', 0)
            
            methods.append({
                "name": method_name,
                "low": p_low,
                "base": p_base,
                "high": p_high
            })
            vs_prices.append(vs_cur)
            
            val_table_html += f"""
                <tr>
                    <td>{method_name}</td>
                    <td class="num">${p_low:,.2f}</td>
                    <td class="num">${p_base:,.2f}</td>
                    <td class="num">${p_high:,.2f}</td>
                    <td class="num">{vs_cur:+.1f}%</td>
                </tr>
            """
        val_table_html += "</tbody></table></div>"

        ff_html = chart_engine.football_field_chart(methods, current_price)
        
        avg_vs_price = sum(vs_prices) / len(vs_prices) if vs_prices else 0
        if avg_vs_price > 10:
            verdict = "Undervalued"
            v_class = "success"
        elif avg_vs_price < -10:
            verdict = "Overvalued"
            v_class = "danger"
        else:
            verdict = "Fairly Valued"
            v_class = "warning"

        html = f"""
        <div class="section" id="section-11">
            <div class="section-header">
                <span class="section-number">11</span>
                <h2>Implied Valuation Analysis</h2>
            </div>
            
            <div class="verdict-box {v_class}">
                <div class="verdict-label">Valuation Verdict</div>
                <div class="verdict-score">{verdict}</div>
                <p>Average implied price variance vs current price: {avg_vs_price:+.1f}%</p>
            </div>

            <h3>Valuation Methodology summary</h3>
            <p>This section outlines the valuation based on comparable company multiples. We utilize EV/EBITDA, EV/Revenue, and P/E to form a comprehensive football field valuation chart.</p>

            {val_table_html}

            <div class="card" style="margin-top: 16px;">
                {ff_html}
            </div>
        </div>
        """
        return html
