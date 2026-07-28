"""
Module: executive_summary.py
Agent: Memo Generation Agent
Purpose: Generates the Executive Summary (Section 1) of the investment memo.
Inputs: Data dictionary containing summaries from upstream agents.
Outputs: HTML string for the executive summary section.
"""
import logging
from typing import Any
from agents.memo_generation import chart_engine
from agents.memo_generation import llm_narrator

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

class Section1Writer:
    def __init__(self, data: dict):
        self.data = data
        
    def generate(self) -> str:
        # Data extraction
        risk = self.data.get('risk_assessment_summary', {})
        comp_risk = risk.get('COMPOSITE_RISK', {})
        risk_score = comp_risk.get('composite_score', 0)
        risk_stance = comp_risk.get('investment_stance', 'UNKNOWN')
        deal_breaker = "YES" if comp_risk.get('deal_breaker') else "NO"
        
        qoe = self.data.get('qoe_summary', {})
        qoe_score = qoe.get('earnings_quality_score', 0)
        qoe_label = qoe.get('earnings_quality_label', 'UNKNOWN')
        
        market = self.data.get('market_intel_summary', {})
        comp_position = market.get('competitive_position_verdict', 'UNKNOWN')
        
        # Risk color
        if risk_score >= 80:
            box_class = "critical"
        elif risk_score >= 60:
            box_class = "high"
        elif risk_score >= 40:
            box_class = "medium"
        else:
            box_class = "low"
            
        # Target market data
        ticker = self.data.get('ticker', '')
        comp_data = self.data.get('competitor_market_data', [])
        target_data = next((row for row in comp_data if row.get('ticker') == ticker), {})
        
        # Market Data Formatting
        price = format_number(target_data.get('current_price'), is_currency=True)
        mcap = format_number(target_data.get('market_cap'), is_currency=True)
        ev = format_number(target_data.get('enterprise_value'), is_currency=True)
        beta = target_data.get('beta', 'N/A')
        beta_str = f"{beta:.2f}" if isinstance(beta, (int, float)) else beta
        ytd = format_number(target_data.get('ytd_return_pct'), is_percent=True)
        
        low_52 = target_data.get('fifty_two_week_low')
        high_52 = target_data.get('fifty_two_week_high')
        if low_52 is not None and high_52 is not None:
            wk52 = f"${low_52:.2f} - ${high_52:.2f}"
        else:
            wk52 = "N/A"
            
        consensus_val = target_data.get('analyst_consensus_rating')
        if consensus_val is not None:
            consensus = f"{consensus_val:.1f}/5.0"
        else:
            consensus = "N/A"
            
        target_price = format_number(target_data.get('analyst_price_target'), is_currency=True)
        
        c_name = self.data.get('company_name', 'N/A')
        cik = self.data.get('cik', 'N/A')
        sic = self.data.get('sic_code', 'N/A')
        exchange = self.data.get('exchange', 'N/A')
        fye = self.data.get('fiscal_year_end', 'N/A')

        # Construct narrator data with flattened keys
        # Handle top_strengths/top_concerns: can be list of strings OR list of dicts
        raw_strengths = qoe.get('top_strengths', [])
        raw_concerns = qoe.get('top_concerns', [])
        strengths_text = ', '.join([
            s.get('item', '') if isinstance(s, dict) else str(s)
            for s in raw_strengths[:3]
        ])
        concerns_text = ', '.join([
            c.get('item', '') if isinstance(c, dict) else str(c)
            for c in raw_concerns[:3]
        ])
        
        # Handle key_advantages/key_vulnerabilities: can be list or string
        moat_data = market.get('COMPETITIVE_MOAT', {})
        ocp_data = market.get('OVERALL_COMPETITIVE_POSITION', {})
        raw_adv = ocp_data.get('key_advantages', market.get('key_advantages', []))
        raw_vul = ocp_data.get('key_vulnerabilities', market.get('key_vulnerabilities', []))
        adv_text = ', '.join(raw_adv[:3]) if isinstance(raw_adv, list) else str(raw_adv)
        vul_text = ', '.join(raw_vul[:3]) if isinstance(raw_vul, list) else str(raw_vul)
        
        narrator_data = {
            'company_name': c_name, 'ticker': ticker,
            'industry_name': self.data.get('industry_name', 'N/A'),
            'qoe_score': qoe_score, 'qoe_label': qoe_label,
            'risk_score': risk_score, 'risk_level': comp_risk.get('final_risk_level', 'N/A'),
            'investment_stance': risk_stance, 'deal_breakers_triggered': 1 if comp_risk.get('deal_breaker') else 0,
            'competitive_position': comp_position,
            'moat_width': moat_data.get('moat_width', 'N/A') if isinstance(moat_data, dict) else 'N/A',
            'current_price': target_data.get('price', 'N/A'),
            'market_cap_display': mcap,
            'top_strengths': strengths_text,
            'top_concerns': concerns_text,
            'key_advantages': adv_text,
            'key_vulnerabilities': vul_text,
        }
        narrative = llm_narrator.generate_executive_summary_narrative(narrator_data)
        
        # Build heatmap from DIMENSION_SCORES dict
        dim_scores = risk.get('DIMENSION_SCORES', {})
        heatmap_dims = [{'name': dim, 'score': vals.get('raw_score', 0), 'level': vals.get('risk_level', 'LOW')}
                        for dim, vals in dim_scores.items()] if isinstance(dim_scores, dict) else []
        heatmap_html = chart_engine.heatmap_risk(heatmap_dims)
        
        html = f"""
        <div class="section" id="section-1">
            <div class="section-header">
                <span class="section-number">1</span>
                <h2>Executive Summary</h2>
            </div>
            
            <div class="verdict-box {box_class}">
                <div class="verdict-label">Composite Risk Score</div>
                <div class="verdict-score">{risk_score}/100</div>
                <div style="font-weight: bold; margin-bottom: 10px;">Investment Stance: {risk_stance}</div>
                <div style="font-size: 0.9rem;">
                    Deal Breaker: {deal_breaker} | QoE Score: {qoe_score}/100 ({qoe_label}) | Competitive Position: {comp_position}
                </div>
            </div>
            
            <div class="grid-2">
                <div class="card">
                    <div class="card-header">Company Snapshot</div>
                    <table class="compact">
                        <tbody>
                            <tr><td><strong>Name</strong></td><td>{c_name}</td></tr>
                            <tr><td><strong>Ticker</strong></td><td>{ticker}</td></tr>
                            <tr><td><strong>Exchange</strong></td><td>{exchange}</td></tr>
                            <tr><td><strong>CIK</strong></td><td>{cik}</td></tr>
                            <tr><td><strong>SIC</strong></td><td>{sic}</td></tr>
                            <tr><td><strong>FYE</strong></td><td>{fye}</td></tr>
                        </tbody>
                    </table>
                </div>
                
                <div class="card">
                    <div class="card-header">Market Data</div>
                    <table class="compact">
                        <tbody>
                            <tr><td><strong>Price</strong></td><td class="num">{price}</td></tr>
                            <tr><td><strong>Market Cap</strong></td><td class="num">{mcap}</td></tr>
                            <tr><td><strong>Enterprise Value</strong></td><td class="num">{ev}</td></tr>
                            <tr><td><strong>Beta</strong></td><td class="num">{beta_str}</td></tr>
                            <tr><td><strong>YTD Return</strong></td><td class="num">{ytd}</td></tr>
                            <tr><td><strong>52 Wk Range</strong></td><td class="num">{wk52}</td></tr>
                            <tr><td><strong>Consensus</strong></td><td>{consensus}</td></tr>
                            <tr><td><strong>Price Target</strong></td><td class="num">{target_price}</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div class="card" style="margin-top: 1rem;">
                <div class="card-header">Risk Heat Map</div>
                {heatmap_html}
            </div>
            
            <div class="card" style="margin-top: 1rem;">
                <div class="card-header">Investment Thesis & Narrative</div>
                <div class="narrative-content">
                    {narrative}
                </div>
            </div>
        </div>
        """
        return html
