"""
Module:  trend_analysis.py
Agent:   Memo Generation Agent
Purpose: Generates Section 5: Trend Analysis & Sudden Changes
Inputs:  data dictionary containing 'trend_analysis'
Outputs: HTML string for the section.
"""
import logging
from agents.memo_generation import llm_narrator

logger = logging.getLogger(__name__)

class Section5Writer:
    def __init__(self, data: dict):
        self.data = data
        self.trend_analysis = data.get('trend_analysis', [])

    def get_trend_badge(self, direction: str) -> str:
        d = direction.upper() if direction else "STABLE"
        if d == "IMPROVING":
            return "<span class='badge bg-success'>IMPROVING</span>"
        elif d == "DECLINING":
            return "<span class='badge bg-danger'>DECLINING</span>"
        elif d == "STABLE":
            return "<span class='badge bg-slate'>STABLE</span>"
        elif d == "VOLATILE":
            return "<span class='badge bg-warning'>VOLATILE</span>"
        return f"<span class='badge bg-slate'>{d}</span>"

    def get_trend_arrow(self, direction: str) -> str:
        d = direction.upper() if direction else ""
        if d == "IMPROVING":
            return "<div class='trend-arrow text-success' style='font-size:24px;'>↑</div>"
        elif d == "DECLINING":
            return "<div class='trend-arrow text-danger' style='font-size:24px;'>↓</div>"
        elif d == "STABLE":
            return "<div class='trend-arrow text-slate' style='font-size:24px;'>→</div>"
        elif d == "VOLATILE":
            return "<div class='trend-arrow text-warning' style='font-size:24px;'>↕</div>"
        return "<div class='trend-arrow text-slate' style='font-size:24px;'>→</div>"

    def generate(self) -> str:
        # Counters for LLM
        improving_count = 0
        declining_count = 0
        stable_count = 0
        volatile_count = 0
        
        improving_details = []
        declining_details = []
        sudden_changes_details = []
        
        # Build Dashboard and Tables
        dashboard_html = '<div class="trend-dashboard" style="display:flex; flex-wrap:wrap; gap:15px; margin-bottom:20px;">'
        
        table_html = """
        <table class="data-table">
            <thead>
                <tr>
                    <th>Ratio Name</th>
                    <th>Trend Direction</th>
                    <th>Momentum</th>
                    <th>Sudden Changes</th>
                </tr>
            </thead>
            <tbody>
        """
        
        alert_table_html = """
        <table class="data-table">
            <thead>
                <tr>
                    <th>Ratio Name</th>
                    <th>Year</th>
                    <th>Magnitude</th>
                    <th>Direction</th>
                </tr>
            </thead>
            <tbody>
        """
        
        has_alerts = False
        
        for t in self.trend_analysis:
            r_name = t.get('ratio_name', '').replace('_', ' ').title()
            direction = t.get('trend_direction', 'STABLE').upper()
            momentum = t.get('momentum', 'N/A')
            sudden_changes = t.get('sudden_changes', [])
            
            # Counts
            if direction == "IMPROVING":
                improving_count += 1
                improving_details.append(r_name)
            elif direction == "DECLINING":
                declining_count += 1
                declining_details.append(r_name)
            elif direction == "STABLE":
                stable_count += 1
            elif direction == "VOLATILE":
                volatile_count += 1
                
            # Dashboard grid item
            dashboard_html += f"""
            <div class="trend-card" style="border:1px solid #E2E8F0; padding:10px; border-radius:8px; text-align:center; min-width:120px;">
                <div class="text-small text-muted">{r_name}</div>
                {self.get_trend_arrow(direction)}
            </div>
            """
            
            # Summary Table Row
            sc_count = len(sudden_changes)
            sc_text = f"{sc_count} alert(s)" if sc_count > 0 else "None"
            table_html += f"""
            <tr>
                <td>{r_name}</td>
                <td>{self.get_trend_badge(direction)}</td>
                <td>{momentum}</td>
                <td>{sc_text}</td>
            </tr>
            """
            
            # Alerts Table Rows
            for sc in sudden_changes:
                has_alerts = True
                sc_year = sc.get('year', 'N/A')
                sc_mag = sc.get('magnitude', 'N/A')
                sc_dir = sc.get('classification', sc.get('direction', 'N/A'))
                sudden_changes_details.append(f"{r_name} in {sc_year}")
                alert_table_html += f"""
                <tr>
                    <td>{r_name}</td>
                    <td>{sc_year}</td>
                    <td>{sc_mag}</td>
                    <td>{sc_dir}</td>
                </tr>
                """
                
        dashboard_html += '</div>'
        table_html += "</tbody></table>"
        
        if has_alerts:
            alert_table_html += "</tbody></table>"
        else:
            alert_table_html = "<p class='text-muted'>No sudden changes detected across the analyzed ratios.</p>"

        # Generate LLM Narrative
        narrative_data = {
            'company_name': self.data.get('company_info', {}).get('company_name', 'The Company'),
            'total_ratios': len(self.trend_analysis),
            'improving_count': improving_count,
            'declining_count': declining_count,
            'stable_count': stable_count,
            'volatile_count': volatile_count,
            'improving_details': ", ".join(improving_details[:5]) + ("..." if len(improving_details) > 5 else ""),
            'declining_details': ", ".join(declining_details[:5]) + ("..." if len(declining_details) > 5 else ""),
            'sudden_changes_details': ", ".join(sudden_changes_details[:5]) + ("..." if len(sudden_changes_details) > 5 else "")
        }
        narrative = llm_narrator.generate_trend_narrative(narrative_data)

        html = f"""
        <div class="section-container">
            <h2>5. Trend Analysis & Sudden Changes</h2>
            
            <div class="narrative-box">
                {narrative}
            </div>
            
            <h3>Trend Direction Dashboard</h3>
            {dashboard_html}
            
            <h3>Trend Summary</h3>
            <div class="table-responsive">
                {table_html}
            </div>
            
            <h3>Sudden Changes Alerts</h3>
            <div class="table-responsive">
                {alert_table_html}
            </div>
        </div>
        """
        return html
