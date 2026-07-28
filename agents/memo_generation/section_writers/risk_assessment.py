"""
Module:  risk_assessment.py
Agent:   Memo Generation Agent
Purpose: Generates Section 14: Comprehensive Risk Assessment.
Inputs:  data dictionary containing risk outputs.
Outputs: HTML string for the section.
"""

import logging
from agents.memo_generation import chart_engine

logger = logging.getLogger(__name__)

class Section14Writer:
    def __init__(self, data: dict):
        self.data = data

    def generate(self) -> str:
        logger.info("Generating Section 14: Comprehensive Risk Assessment")
        
        summary = self.data.get('risk_assessment_summary', {})
        composite = summary.get('COMPOSITE_RISK', {})
        dimensions = summary.get('DIMENSION_SCORES', {})
        deal_breakers = self.data.get('deal_breaker_flags', [])
        
        stance = composite.get('investment_stance', 'N/A')
        risk_score = composite.get('composite_score', 0)
        risk_level = composite.get('final_risk_level', 'LOW').lower()
        
        # Radar Chart
        radar_labels = []
        radar_values = []
        for d, vals in dimensions.items():
            radar_labels.append(d)
            radar_values.append(vals.get('raw_score', 0))
            
        radar_html = chart_engine.radar_chart(
            labels=radar_labels,
            datasets=[{"label": "Risk Score", "data": radar_values, "color": "#EF4444"}],
            title="Risk Radar (Higher = More Risk)"
        )
        
        # Build heatmap dims list from DIMENSION_SCORES dict
        heatmap_dims = [{'name': dim, 'score': vals.get('raw_score', 0), 'level': vals.get('risk_level', 'LOW')}
                        for dim, vals in dimensions.items()]
        heatmap_html = chart_engine.heatmap_risk(heatmap_dims)
        
        # Dimension Deep Dive
        dim_html = ""
        risk_evidence = self.data.get('risk_evidence', [])
        
        donut_labels = []
        donut_values = []
        for d, vals in dimensions.items():
            evidences = [e for e in risk_evidence if str(e.get('dimension', '')).upper() == str(d).upper()]
            donut_labels.append(d)
            donut_values.append(vals.get('weighted_score', 0))
            
            ev_rows = []
            for e in evidences:
                ev_rows.append(f"""
                <tr>
                    <td>{e.get('sub_dimension', 'N/A')}</td>
                    <td>{e.get('evidence_type', 'N/A')}</td>
                    <td>{e.get('evidence_text', 'N/A')}</td>
                    <td><span class="badge badge-{str(e.get('severity', 'low')).lower()}">{e.get('severity', 'N/A')}</span></td>
                    <td class="num">{e.get('points_added', 0)}</td>
                </tr>
                """)
                
            dim_html += f"""
            <div class="card" style="margin-bottom: 20px;">
                <h4>{d} <span class="badge badge-{str(vals.get('risk_level', 'low')).lower()}">{vals.get('risk_level', 'N/A')}</span></h4>
                <p>Weight: {vals.get('weight', 0):.2f} | Weighted Score: {vals.get('weighted_score', 0):.2f}</p>
                <div class="table-container">
                    <table class="compact">
                        <thead>
                            <tr>
                                <th>Sub-Dimension</th>
                                <th>Type</th>
                                <th>Evidence</th>
                                <th>Severity</th>
                                <th class="num">Points</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(ev_rows)}
                        </tbody>
                    </table>
                </div>
            </div>
            """
            
        donut_html = chart_engine.doughnut_chart(
            labels=donut_labels,
            data=donut_values,
            title="Weighted Risk Contribution",
            height="350px"
        )
            
        html = f"""
        <div class="section" id="section-14">
            <div class="section-header">
                <div class="section-number">14</div>
                <h2>Comprehensive Risk Assessment</h2>
            </div>
            
            <div class="verdict-box {composite.get('final_risk_level', 'medium').lower()}">
                <div class="verdict-label">Investment Stance</div>
                <div class="verdict-score">{stance}</div>
            </div>
            
            <h3>Deal Breaker Analysis</h3>
            <div class="traffic-lights">"""
        
        for db in deal_breakers:
            triggered = db.get('triggered', False)
            color = 'red' if triggered else 'green'
            label = db.get('flag_type', db.get('name', 'Unknown'))
            html += f"""
                <div class="traffic-light">
                    <div class="indicator {color}"></div>
                    <span>{str(label).replace('_', ' ').title()}</span>
                </div>"""
        
        html += f"""
            </div>
            
            <div class="verdict-box {risk_level}" style="margin-top:24px;">
                <div class="verdict-label">Investment Stance</div>
                <div class="verdict-score">{risk_score}/100</div>
                <div style="font-size:0.95rem; margin-top:8px;">{stance}</div>
            </div>
            
            <div class="grid-2">
                {radar_html}
                <div class="card">
                    {donut_html}
                </div>
            </div>

            <div class="card" style="margin-top: 24px; margin-bottom: 24px;">
                <h4>Risk Heat Map</h4>
                {heatmap_html}
            </div>
            
            <h3>Dimension Deep Dive</h3>
            {dim_html}
            
        </div>
        """
        return html
