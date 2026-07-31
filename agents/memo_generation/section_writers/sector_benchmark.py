"""
Module:  sector_benchmark.py
Agent:   Memo Generation Agent
Purpose: Generates Section 8 (Sector Benchmarking) for the investment memo.
Inputs:  data dictionary containing 'sector_benchmark'
Outputs: HTML string for the sector benchmarking section.
"""

import logging
from agents.memo_generation import chart_engine

logger = logging.getLogger(__name__)

class Section8Writer:
    def __init__(self, data: dict):
        self.data = data
        self.benchmark_data = data.get('sector_benchmark', {})
        self.metrics = self.benchmark_data.get('metrics', {})
        self.top_peers = self.benchmark_data.get('top_peers', [])

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

    def get_color_class(self, pos: str) -> str:
        pos_upper = str(pos).upper()
        if pos_upper == "ABOVE_AVERAGE":
            return "badge-proceed"
        elif pos_upper == "AVERAGE":
            return "badge-medium"
        elif pos_upper == "BELOW_AVERAGE":
            return "badge-high"
        elif pos_upper == "SIGNIFICANTLY_BELOW":
            return "badge-critical"
        return "badge-neutral"

    def generate(self) -> str:
        # Peer group table
        peers_html = """
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Entity Name</th>
                        <th>CIK</th>
                        <th class="num">Revenue</th>
                    </tr>
                </thead>
                <tbody>
        """
        for peer in self.top_peers:
            rev = peer.get('revenue')
            rev_str = self.format_num(rev)
            
            p_name = peer.get('entity_name')
            p_name = p_name if p_name is not None else 'N/A'
            
            p_cik = peer.get('cik')
            p_cik = p_cik if p_cik is not None else 'N/A'
            
            peers_html += f"""
                <tr>
                    <td>{p_name}</td>
                    <td>{p_cik}</td>
                    <td class="num">{rev_str}</td>
                </tr>
            """
        peers_html += """
                </tbody>
            </table>
        </div>
        """

        # Metrics benchmark table
        metrics_html = """
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th class="num">Company Value</th>
                        <th class="num">Sector Median</th>
                        <th class="num">Sector Mean</th>
                        <th class="num">Percentile</th>
                        <th>Relative Position</th>
                    </tr>
                </thead>
                <tbody>
        """
        labels = []
        company_radars = []
        percentiles = []
        colors = []

        for m_name, m_data in self.metrics.items():
            c_val = m_data.get('company_value')
            s_med = m_data.get('sector_median')
            s_mean = m_data.get('sector_mean')
            pct = m_data.get('company_percentile')
            pos = m_data.get('relative_position')

            labels.append(m_name)
            company_radars.append(pct if pct is not None else 0)
            percentiles.append(pct if pct is not None else 0)
            
            c_class = self.get_color_class(pos)

            c_val_str = f"{c_val:,.2f}" if c_val is not None else "N/A"
            s_med_str = f"{s_med:,.2f}" if s_med is not None else "N/A"
            s_mean_str = f"{s_mean:,.2f}" if s_mean is not None else "N/A"
            pct_str = f"{pct:.1f}%" if pct is not None else "N/A"
            pos_str = pos if pos is not None else "N/A"

            metrics_html += f"""
                <tr>
                    <td>{m_name}</td>
                    <td class="num">{c_val_str}</td>
                    <td class="num">{s_med_str}</td>
                    <td class="num">{s_mean_str}</td>
                    <td class="num">{pct_str}</td>
                    <td><span class="badge {c_class}">{pos_str}</span></td>
                </tr>
            """
        metrics_html += """
                </tbody>
            </table>
        </div>
        """

        radar_html = chart_engine.radar_chart(
            labels=labels,
            datasets=[
                {"label": "Company (Percentile)", "data": company_radars, "color": chart_engine.COLORS["primary"]},
                {"label": "Median (50th)", "data": [50]*len(labels), "color": chart_engine.COLORS["slate"]}
            ],
            title="Company vs Sector Median (Percentile Scale)",
            height="500px"
        )

        bar_html = chart_engine.bar_chart(
            labels=labels,
            datasets=[
                {"label": "Percentile", "data": percentiles, "color": chart_engine.COLORS["accent"]}
            ],
            title="Metric Percentile Rank",
            horizontal=True,
            height="500px"
        )

        html = f"""
        <div class="section" id="section-8">
            <div class="section-header">
                <span class="section-number">8</span>
                <h2>Sector Benchmarking</h2>
            </div>
            
            <h3>Top Sector Peers</h3>
            {peers_html}

            <h3>12-Metric Benchmark</h3>
            {metrics_html}

            <div class="grid-2">
                <div class="card">
                    {radar_html}
                </div>
                <div class="card">
                    {bar_html}
                </div>
            </div>
        </div>
        """
        return html
