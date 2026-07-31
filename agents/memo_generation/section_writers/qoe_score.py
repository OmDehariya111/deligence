"""
Module:  qoe_score.py
Agent:   Memo Generation Agent
Purpose: Generates Section 9 (Earnings Quality Score) for the investment memo.
Inputs:  data dictionary containing 'qoe_summary'
Outputs: HTML string for the QoE section.
"""

import logging
from agents.memo_generation import chart_engine

logger = logging.getLogger(__name__)

class Section9Writer:
    def __init__(self, data: dict):
        self.data = data
        self.qoe_data = data.get('qoe_summary', {})

    def generate(self) -> str:
        score = self.qoe_data.get('earnings_quality_score', 0)
        label = self.qoe_data.get('earnings_quality_label', 'UNKNOWN')
        strengths = self.qoe_data.get('top_strengths', [])
        concerns = self.qoe_data.get('top_concerns', [])
        limitations = self.qoe_data.get('data_limitations', {})

        gauge_html = chart_engine.gauge_svg(score, 100, label)

        strengths_html = "<ul>"
        for s in strengths[:5]:
            item = str(s.get('item', s) if isinstance(s, dict) else s)
            strengths_html += f"<li>{item}</li>"
        strengths_html += "</ul>"
        if not strengths:
            strengths_html = "<p class='text-muted'>No particular strengths identified.</p>"

        concerns_html = "<ul>"
        for c in concerns[:5]:
            item = str(c.get('item', c) if isinstance(c, dict) else c)
            concerns_html += f"<li>{item}</li>"
        concerns_html += "</ul>"
        if not concerns:
            concerns_html = "<p class='text-muted'>No particular concerns identified.</p>"

        # Render Data Limitations - only show actual limitations
        allowed_limitation_keys = {'missing_fields', 'ratios_blocked'}
        if isinstance(limitations, dict):
            lim_html = "<ul>"
            for k, v in limitations.items():
                if k not in allowed_limitation_keys:
                    continue
                if v and (not isinstance(v, list) or len(v) > 0):
                    key_fmt = str(k).replace('_', ' ').title()
                    val_fmt = ", ".join(v) if isinstance(v, list) else str(v)
                    lim_html += f"<li><strong>{key_fmt}:</strong> {val_fmt}</li>"
            lim_html += "</ul>"
            if lim_html == "<ul></ul>":
                lim_html = "<p class='text-muted'>No significant data limitations.</p>"
        else:
            lim_html = f"<p>{limitations}</p>"

        html = f"""
        <div class="section" id="section-9">
            <div class="section-header">
                <span class="section-number">9</span>
                <h2>Earnings Quality Score (QoE)</h2>
            </div>
            
            <div class="grid-2">
                <div class="card text-center">
                    <h3>QoE Score</h3>
                    {gauge_html}
                </div>
                <div class="card">
                    <h3>QoE Assessment</h3>
                    <p>The Quality of Earnings (QoE) score provides an aggregated view of the company's financial reporting reliability and operating efficiency, based on automated quantitative metrics.</p>
                </div>
            </div>

            <div class="grid-2" style="margin-top: 16px;">
                <div class="card">
                    <h3>Top Strengths</h3>
                    {strengths_html}
                </div>
                <div class="card">
                    <h3>Top Concerns</h3>
                    {concerns_html}
                </div>
            </div>

            <div class="card" style="margin-top: 16px;">
                <h3>Data Limitations</h3>
                {lim_html}
            </div>
        </div>
        """
        return html
