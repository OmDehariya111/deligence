"""
Module:  macro_context.py
Agent:   Memo Generation Agent
Purpose: Generates Section 13: Industry & Macroeconomic Context.
Inputs:  data dictionary containing industry_macro and market_intel_summary.
Outputs: HTML string for the section.
"""

import logging

logger = logging.getLogger(__name__)

class Section13Writer:
    def __init__(self, data: dict):
        self.data = data

    def generate(self) -> str:
        logger.info("Generating Section 13: Industry & Macroeconomic Context")
        macro = self.data.get('industry_macro', [])
        summary = self.data.get('market_intel_summary', {}).get('INDUSTRY_MACRO', {})
        
        sic_code = self.data.get('sic_code', 'N/A')
        industry_name = self.data.get('industry_name', 'N/A')
        
        rows = []
        for ind in macro:
            # Remove moat row from macro table
            if ind.get('indicator_name') == 'Competitive Moat Assessment':
                continue
                
            trend = ind.get('trend_direction', '')
            arrow = "→"
            if trend.upper() == 'UP': arrow = "↑"
            elif trend.upper() == 'DOWN': arrow = "↓"
            
            rows.append(f"""
            <tr>
                <td>{ind.get('indicator_name', 'N/A')}</td>
                <td class="num">{ind.get('current_value', 'N/A')}</td>
                <td class="num">{ind.get('value_1y_ago', 'N/A')}</td>
                <td class="num">{ind.get('value_3y_ago', 'N/A')}</td>
                <td>{arrow} {trend}</td>
                <td>{ind.get('relevance_note', 'N/A')}</td>
            </tr>
            """)
            
        html = f"""
        <div class="section" id="section-13">
            <div class="section-header">
                <div class="section-number">13</div>
                <h2>Industry & Macroeconomic Context</h2>
            </div>
            
            <div class="callout callout-info">
                <h4>Industry Classification</h4>
                <p><strong>SIC Code:</strong> {sic_code} | <strong>Industry:</strong> {industry_name}</p>
            </div>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Indicator</th>
                            <th class="num">Current</th>
                            <th class="num">1Y Ago</th>
                            <th class="num">3Y Ago</th>
                            <th>Trend</th>
                            <th>Relevance</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
        </div>
        """
        return html
