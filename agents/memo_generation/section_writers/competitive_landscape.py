"""
Module:  competitive_landscape.py
Agent:   Memo Generation Agent
Purpose: Generates Section 10 (Competitive Landscape & Market Intelligence) for the investment memo.
Inputs:  data dictionary containing competitor data
Outputs: HTML string for the competitive landscape section.
"""

import logging
from agents.memo_generation import chart_engine
from agents.memo_generation import llm_narrator

logger = logging.getLogger(__name__)

class Section10Writer:
    def __init__(self, data: dict):
        self.data = data

    def format_num(self, val):
        if val is None:
            return "N/A"
        if isinstance(val, (int, float)):
            if val > 1_000_000_000:
                return f"${val/1_000_000_000:.1f}B"
            if val > 1_000_000:
                return f"${val/1_000_000:.1f}M"
            return f"{val:,.2f}"
        return val

    def generate(self) -> str:
        market_intel = self.data.get('market_intel_summary', {})
        named_competitors = market_intel.get('NAMED_COMPETITORS', [])
        trading_comps = self.data.get('trading_comps_table', [])
        
        comp_moat = market_intel.get('COMPETITIVE_MOAT', {})
        comp_position = market_intel.get('OVERALL_COMPETITIVE_POSITION', {})
        competitor_ltm = self.data.get('competitor_ltm_financials', [])
        competitor_market = self.data.get('competitor_market_data', [])
        named_competitors_db = self.data.get('named_competitors', [])
        db_lookup = {row.get('ticker'): row for row in named_competitors_db}

        # Construct narrator data with flattened keys from market_intel_summary
        narrator_data = {
            'company_name': self.data.get('company_name', 'N/A'),
            'ticker': self.data.get('ticker', 'N/A'),
            'competitors_text': ', '.join([c.get('company_name', c.get('ticker', '')) for c in named_competitors[:5]]),
            'moat_width': comp_moat.get('moat_width', 'N/A'),
            'moat_narrative': comp_moat.get('moat_narrative', 'N/A'),
            'competitive_verdict': comp_position.get('verdict', 'N/A'),
            'key_advantages': comp_position.get('key_advantages', []),
            'key_vulnerabilities': comp_position.get('key_vulnerabilities', []),
            'valuation_context': 'See Section 11 for implied valuation analysis',
        }
        narrative = llm_narrator.generate_competitive_landscape_narrative(narrator_data)

        # Named Competitors Table
        nc_html = """
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Company Name</th>
                        <th class="num">Market Cap</th>
                        <th>Selection Method</th>
                        <th>Why Selected</th>
                    </tr>
                </thead>
                <tbody>
        """
        for nc in named_competitors:
            mcap = nc.get('market_cap_bn', 0) * 1_000_000_000 if nc.get('market_cap_bn') else 0
            tck = nc.get('ticker', 'N/A')
            sel_method = db_lookup.get(tck, {}).get('selection_method', 'N/A')
            nc_html += f"""
                <tr>
                    <td>{tck}</td>
                    <td>{nc.get('company_name', 'N/A')}</td>
                    <td class="num">{self.format_num(mcap)}</td>
                    <td>{sel_method}</td>
                    <td>{nc.get('why_selected', 'N/A')}</td>
                </tr>
            """
        nc_html += "</tbody></table></div>"

        # IB-Style Trading Comps Table
        tc_html = """
        <div class="table-container">
            <table class="comps-table">
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th class="num">EV/Rev</th>
                        <th class="num">EV/EBITDA</th>
                        <th class="num">EV/EBIT</th>
                        <th class="num">P/E</th>
                        <th class="num">P/FCF</th>
                    </tr>
                </thead>
                <tbody>
        """
        for tc in trading_comps:
            cls = ""
            if tc.get('is_target'):
                cls = "target-row"
            elif tc.get('is_median'):
                cls = "median-row"
            
            def _sf(val):
                try: return float(val)
                except (ValueError, TypeError): return 0.0

            tc_html += f"""
                <tr class="{cls}">
                    <td>{tc.get('ticker', 'N/A')}</td>
                    <td class="num">{_sf(tc.get('ev_revenue')):.2f}x</td>
                    <td class="num">{_sf(tc.get('ev_ebitda')):.2f}x</td>
                    <td class="num">{_sf(tc.get('ev_ebit')):.2f}x</td>
                    <td class="num">{_sf(tc.get('p_e')):.2f}x</td>
                    <td class="num">{_sf(tc.get('p_fcf')):.2f}x</td>
                </tr>
            """
        tc_html += "</tbody></table></div>"

        # Charts setup
        tickers = [c.get('ticker', 'Unknown') for c in named_competitors]
        mcaps = [c.get('market_cap_bn', 0) * 1_000_000_000 for c in named_competitors]
        
        mcap_chart = chart_engine.bar_chart(
            labels=tickers,
            datasets=[{"label": "Market Cap", "data": mcaps}],
            title="Market Cap Comparison",
            currency_format=True
        )

        moat_width = comp_moat.get('moat_width', 'N/A')
        moat_narrative = comp_moat.get('moat_narrative', 'N/A')
        verdict = comp_position.get('verdict', 'N/A')

        def _format_list(items):
            if not items: return "N/A"
            if isinstance(items, list):
                return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"
            return str(items)

        html = f"""
        <div class="section" id="section-10">
            <div class="section-header">
                <span class="section-number">10</span>
                <h2>Competitive Landscape & Market Intelligence</h2>
            </div>
            
            <div class="card" style="margin-bottom: 16px;">
                <h3>Market Narrative</h3>
                <p>{narrative}</p>
            </div>

            <div class="grid-2" style="margin-bottom: 16px;">
                <div class="card">
                    <h3>Moat Assessment: <span class="badge badge-info">{moat_width}</span></h3>
                    <p>{moat_narrative}</p>
                </div>
                <div class="card">
                    <h3>Competitive Position</h3>
                    <p><strong>Verdict:</strong> {verdict}</p>
                    <p><strong>Key Advantages:</strong></p>
                    {_format_list(comp_position.get('key_advantages', []))}
                    <p><strong>Key Vulnerabilities:</strong></p>
                    {_format_list(comp_position.get('key_vulnerabilities', []))}
                </div>
            </div>

            <h3>Named Competitors</h3>
            {nc_html}

            <h3>Trading Comparables</h3>
            {tc_html}

            <div class="card" style="margin-top: 16px;">
                {mcap_chart}
            </div>
            
            <h3>LTM Financials</h3>
            <div class="table-container">
                <table class="compact">
                    <thead>
                        <tr>
                            <th>Ticker</th>
                            <th class="num">Revenue (LTM)</th>
                            <th class="num">EBITDA (LTM)</th>
                            <th class="num">EBIT (LTM)</th>
                            <th class="num">Gross Margin</th>
                            <th class="num">EBITDA Margin</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(f"<tr><td>{c.get('ticker', 'N/A')}</td><td class='num'>{self.format_num(c.get('ltm_revenue'))}</td><td class='num'>{self.format_num(c.get('ltm_ebitda'))}</td><td class='num'>{self.format_num(c.get('ltm_operating_inc'))}</td><td class='num'>{c.get('ltm_gross_margin', 'N/A')}{'%' if str(c.get('ltm_gross_margin', 'N/A')) != 'N/A' else ''}</td><td class='num'>{c.get('ltm_ebitda_margin', 'N/A')}{'%' if str(c.get('ltm_ebitda_margin', 'N/A')) != 'N/A' else ''}</td></tr>" for c in competitor_ltm) if competitor_ltm else "<tr><td colspan='6' class='text-center text-muted'>No LTM data available</td></tr>"}
                    </tbody>
                </table>
            </div>

            <h3>Live Market Data</h3>
            <div class="table-container">
                <table class="compact">
                    <thead>
                        <tr>
                            <th>Ticker</th>
                            <th class="num">Stock Price</th>
                            <th class="num">52W High</th>
                            <th class="num">52W Low</th>
                            <th class="num">YTD Return</th>
                            <th class="num">Analyst Target</th>
                            <th class="num">Analyst Rating</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(f"<tr><td>{c.get('ticker', 'N/A')}</td><td class='num'>${c.get('current_price', 0):.2f}</td><td class='num'>${c.get('fifty_two_week_high', 0):.2f}</td><td class='num'>${c.get('fifty_two_week_low', 0):.2f}</td><td class='num'>{c.get('ytd_return_pct', 0):.1f}%</td><td class='num'>${c.get('analyst_price_target', 0):.2f}</td><td class='num'>{c.get('analyst_consensus_rating', 'N/A')}</td></tr>" for c in competitor_market) if competitor_market else "<tr><td colspan='7' class='text-center text-muted'>No Live Market data available</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        """
        return html
