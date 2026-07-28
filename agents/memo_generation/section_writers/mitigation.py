"""
Module:  mitigation.py
Agent:   Memo Generation Agent
Purpose: Generates Section 15: Mitigation Recommendations.
Inputs:  data dictionary containing risk_mitigation_recommendations.
Outputs: HTML string for the section.
"""

import logging
from collections import Counter
from agents.memo_generation import chart_engine

logger = logging.getLogger(__name__)

class Section15Writer:
    def __init__(self, data: dict):
        self.data = data

    def generate(self) -> str:
        logger.info("Generating Section 15: Mitigation Recommendations")
        recs = self.data.get('risk_mitigation_recommendations', [])
        
        immediate = sum(1 for r in recs if r.get('priority') == 'IMMEDIATE')
        near_term = sum(1 for r in recs if r.get('priority') == 'NEAR_TERM')
        
        types = [r.get('condition_type', 'Unknown') for r in recs]
        type_counts = Counter(types)
        
        donut_html = chart_engine.doughnut_chart(
            labels=['Immediate', 'Near Term'],
            data=[immediate, near_term],
            title="Recommendations by Priority",
            colors=['#EF4444', '#F59E0B']
        )
        
        bar_html = chart_engine.bar_chart(
            labels=list(type_counts.keys()),
            datasets=[{"label": "Count", "data": list(type_counts.values()), "color": "#4A90D9"}],
            title="Recommendations by Type",
            horizontal=True
        )
        
        cards = []
        for r in recs:
            pri = r.get('priority', 'NEAR_TERM')
            badge_class = "badge-critical" if pri == 'IMMEDIATE' else "badge-warning"
            cards.append(f"""
            <div class="card" style="margin-bottom: 16px;">
                <div class="card-header">
                    <span class="badge {badge_class}">{pri}</span> {r.get('dimension', 'N/A')} > {r.get('sub_dimension', 'N/A')}
                </div>
                <p><strong>Finding:</strong> {r.get('finding_text', 'N/A')} (Severity: {r.get('severity', 'N/A')})</p>
                <p><strong>Recommendation:</strong> {r.get('recommendation_text', 'N/A')}</p>
            </div>
            """)
            
        html = f"""
        <div class="section" id="section-15">
            <div class="section-header">
                <div class="section-number">15</div>
                <h2>Mitigation Recommendations</h2>
            </div>
            
            <div class="grid-2">
                <div class="card">
                    <div class="card-header">Total Recommendations</div>
                    <div class="card-value">{len(recs)}</div>
                    <div class="card-footer">{immediate} Immediate | {near_term} Near Term</div>
                </div>
            </div>
            
            <div class="grid-2">
                {donut_html}
                {bar_html}
            </div>
            
            <h3>Prioritized Recommendations</h3>
            {''.join(cards)}
            
        </div>
        """
        return html
