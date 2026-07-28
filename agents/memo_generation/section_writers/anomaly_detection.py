"""
Module:  anomaly_detection.py
Agent:   Memo Generation Agent
Purpose: Generates Section 7: Anomaly Detection Results — 15 rule-based financial anomaly checks.
         Shows triggered flags with severity, category breakdown, and supporting evidence.
Inputs:  data dictionary containing 'anomaly_flags' from Analysis Agent.
Outputs: HTML string for the section.
"""

import logging
from typing import Any

from agents.memo_generation import chart_engine

logger = logging.getLogger(__name__)


def _safe_float(val: Any, decimals: int = 2) -> str:
    """Safely format a float for display."""
    if val is None:
        return "N/A"
    try:
        return f"{float(val):.{decimals}f}"
    except (ValueError, TypeError):
        return str(val) if val else "N/A"


class Section7Writer:
    """Generates the Anomaly Detection Results section."""

    def __init__(self, data: dict):
        self.data = data
        self.anomaly_flags = data.get("anomaly_flags", {})

    def generate(self) -> str:
        """Generate the complete anomaly detection section HTML."""
        logger.info("Generating Section 7: Anomaly Detection Results")

        total_flags = self.anomaly_flags.get("total_flags", 0)
        critical = self.anomaly_flags.get("critical", 0)
        high = self.anomaly_flags.get("high", 0)
        medium = self.anomaly_flags.get("medium", 0)
        low = self.anomaly_flags.get("low", 0)
        rules_skipped = self.anomaly_flags.get("rules_skipped_missing_data", [])
        flags = self.anomaly_flags.get("flags", [])

        # Determine overall status
        if total_flags == 0:
            overall_badge = "badge-safe"
            overall_text = "✅ CLEAN — No Anomalies Detected"
            callout_class = "callout-success"
        elif critical > 0:
            overall_badge = "badge-critical"
            overall_text = f"🔴 {total_flags} ANOMALIES DETECTED ({critical} Critical)"
            callout_class = "callout-danger"
        elif high > 0:
            overall_badge = "badge-high"
            overall_text = f"🟠 {total_flags} ANOMALIES DETECTED ({high} High)"
            callout_class = "callout-warning"
        else:
            overall_badge = "badge-medium"
            overall_text = f"🟡 {total_flags} ANOMALIES DETECTED"
            callout_class = "callout-warning"

        summary_cards = self._build_summary_cards(total_flags, critical, high, medium, low)
        severity_chart = self._build_severity_chart(critical, high, medium, low, total_flags)
        category_chart = self._build_category_chart(flags)
        flag_cards = self._build_flag_cards(flags)
        skipped_html = self._build_skipped_rules(rules_skipped)

        html = f"""
        <div class="section" id="section-7">
            <div class="section-header">
                <div class="section-number">7</div>
                <h2>Anomaly Detection Results</h2>
            </div>

            <p>The Analysis Agent evaluates 15 deterministic anomaly detection rules against the
            company's financial data. Each rule checks for specific red-flag conditions that may
            indicate financial irregularities, operational deterioration, or accounting concerns.</p>

            <div class="{callout_class} callout">
                <span class="badge badge-large {overall_badge}">{overall_text}</span>
            </div>

            {summary_cards}

            <div class="grid-2">
                {severity_chart}
                {category_chart}
            </div>

            {flag_cards}

            {skipped_html}
        </div>
        """
        return html

    def _build_summary_cards(self, total: int, critical: int, high: int,
                              medium: int, low: int) -> str:
        """Build the summary statistics cards."""
        passed = 15 - total - len(self.anomaly_flags.get("rules_skipped_missing_data", []))
        passed = max(0, passed)

        return f"""
        <div class="grid-4" style="margin: 24px 0;">
            <div class="card" style="border-left: 4px solid #EF4444;">
                <div class="card-header">Critical</div>
                <div class="card-value" style="color:#EF4444;">{critical}</div>
            </div>
            <div class="card" style="border-left: 4px solid #F97316;">
                <div class="card-header">High</div>
                <div class="card-value" style="color:#F97316;">{high}</div>
            </div>
            <div class="card" style="border-left: 4px solid #F59E0B;">
                <div class="card-header">Medium</div>
                <div class="card-value" style="color:#F59E0B;">{medium}</div>
            </div>
            <div class="card" style="border-left: 4px solid #10B981;">
                <div class="card-header">Passed</div>
                <div class="card-value" style="color:#10B981;">{passed}</div>
            </div>
        </div>
        """

    def _build_severity_chart(self, critical: int, high: int, medium: int,
                               low: int, total: int) -> str:
        """Build the severity distribution donut chart."""
        passed = max(0, 15 - total - len(self.anomaly_flags.get("rules_skipped_missing_data", [])))

        labels = []
        values = []
        colors = []

        if critical > 0:
            labels.append("Critical")
            values.append(critical)
            colors.append("#EF4444")
        if high > 0:
            labels.append("High")
            values.append(high)
            colors.append("#F97316")
        if medium > 0:
            labels.append("Medium")
            values.append(medium)
            colors.append("#F59E0B")
        if low > 0:
            labels.append("Low")
            values.append(low)
            colors.append("#3B82F6")
        if passed > 0:
            labels.append("Passed")
            values.append(passed)
            colors.append("#10B981")

        if not labels:
            labels = ["All Passed"]
            values = [15]
            colors = ["#10B981"]

        return chart_engine.doughnut_chart(
            labels=labels, data=values, title="Rule Severity Distribution",
            colors=colors, height="300px",
        )

    def _build_category_chart(self, flags: list) -> str:
        """Build the category breakdown bar chart."""
        categories: dict[str, int] = {}
        for f in flags:
            cat = f.get("category", "Other")
            categories[cat] = categories.get(cat, 0) + 1

        if not categories:
            return "<div class='card'><p class='text-muted text-center'>No anomalies to categorize.</p></div>"

        return chart_engine.bar_chart(
            labels=list(categories.keys()),
            datasets=[{"label": "Flags Triggered", "data": list(categories.values()), "color": "#F97316"}],
            title="Anomalies by Category",
            height="300px",
            show_legend=False,
        )

    def _build_flag_cards(self, flags: list) -> str:
        """Build individual anomaly flag cards with details."""
        if not flags:
            return """
            <div class="callout callout-success" style="margin-top: 24px;">
                <h4>✅ Clean Bill of Health</h4>
                <p>All 15 anomaly detection rules passed without triggering any flags.
                The company's financial data shows no red-flag conditions based on our
                rule-based analysis.</p>
            </div>
            """

        cards_html = '<h3>Triggered Anomaly Flags</h3>\n'

        for flag in flags:
            flag_id = flag.get("flag_id", "AF-???")
            title = flag.get("title", "Unknown Anomaly")
            severity = flag.get("severity", "MEDIUM").upper()
            category = flag.get("category", "N/A")
            description = flag.get("description", "No description available.")
            supporting_data = flag.get("supporting_data", {})

            # Severity badge styling
            if severity == "CRITICAL":
                badge_class = "badge-critical"
                border_color = "#EF4444"
            elif severity == "HIGH":
                badge_class = "badge-high"
                border_color = "#F97316"
            elif severity == "MEDIUM":
                badge_class = "badge-medium"
                border_color = "#F59E0B"
            else:
                badge_class = "badge-info"
                border_color = "#3B82F6"

            # Supporting data rows
            data_rows = ""
            if supporting_data and isinstance(supporting_data, dict):
                for key, val in supporting_data.items():
                    display_key = key.replace("_", " ").title()
                    data_rows += f"""
                    <tr>
                        <td class="fw-medium">{display_key}</td>
                        <td class="num">{_safe_float(val) if isinstance(val, (int, float)) else str(val)}</td>
                    </tr>
                    """

            supporting_table = ""
            if data_rows:
                supporting_table = f"""
                <div class="table-container" style="margin-top:12px;">
                    <table class="compact">
                        <thead><tr><th>Metric</th><th class="num">Value</th></tr></thead>
                        <tbody>{data_rows}</tbody>
                    </table>
                </div>
                """

            cards_html += f"""
            <div class="card" style="margin-bottom: 16px; border-left: 4px solid {border_color};">
                <div class="d-flex items-center justify-between" style="margin-bottom: 8px;">
                    <div>
                        <span class="text-mono fw-bold" style="color:{border_color};">{flag_id}</span>
                        <span class="fw-semibold" style="margin-left: 8px;">{title}</span>
                    </div>
                    <div>
                        <span class="badge {badge_class}">{severity}</span>
                        <span class="badge badge-neutral" style="margin-left:4px;">{category}</span>
                    </div>
                </div>
                <p style="margin-bottom:8px; color: var(--color-text-secondary);">{description}</p>
                {supporting_table}
            </div>
            """

        return cards_html

    def _build_skipped_rules(self, rules_skipped: list) -> str:
        """Build the skipped rules section."""
        if not rules_skipped:
            return ""

        items = "".join(f"<li>{rule}</li>" for rule in rules_skipped)
        return f"""
        <div class="callout callout-warning" style="margin-top: 24px;">
            <h4>⚠️ Rules Skipped Due to Missing Data</h4>
            <p>The following rules could not be evaluated because of insufficient financial data:</p>
            <ul style="margin-left: 20px; margin-bottom: 0;">
                {items}
            </ul>
        </div>
        """
