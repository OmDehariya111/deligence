"""
Module:  fraud_distress.py
Agent:   Memo Generation Agent
Purpose: Generates Section 6: Fraud & Distress Detection — Beneish M-Score and Altman Z-Score.
         Shows manipulation probability (M-Score) and bankruptcy risk (Z-Score) with
         component-level breakdown, gauges, radar charts, and historical trends.
Inputs:  data dictionary containing 'fraud_distress' from Analysis Agent.
Outputs: HTML string for the section.
"""

import logging
from typing import Any

from agents.memo_generation import chart_engine

logger = logging.getLogger(__name__)


def _safe_float(val: Any, decimals: int = 2) -> str:
    """Safely format a float value."""
    if val is None:
        return "N/A"
    try:
        return f"{float(val):.{decimals}f}"
    except (ValueError, TypeError):
        return "N/A"


def _safe_num(val: Any) -> float:
    """Safely convert to float, returning 0 on failure."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


class Section6Writer:
    """Generates the Fraud & Distress Detection section."""

    def __init__(self, data: dict):
        self.data = data
        self.fraud_distress = data.get("fraud_distress", {})

    def generate(self) -> str:
        """Generate the complete fraud & distress section HTML."""
        logger.info("Generating Section 6: Fraud & Distress Detection")

        beneish_html = self._build_beneish_section()
        altman_html = self._build_altman_section()

        html = f"""
        <div class="section" id="section-6">
            <div class="section-header">
                <div class="section-number">6</div>
                <h2>Fraud & Distress Detection</h2>
            </div>

            <p>This section applies two well-established academic models to detect potential earnings
            manipulation (Beneish M-Score) and bankruptcy risk (Altman Z-Score). These models use
            only verified financial data — no AI estimation is involved.</p>

            {beneish_html}

            <div class="divider"></div>

            {altman_html}
        </div>
        """
        return html

    def _build_beneish_section(self) -> str:
        """Build the Beneish M-Score analysis section."""
        beneish_scores = self.fraud_distress.get("beneish_scores", [])

        if not beneish_scores:
            return """
            <h3>Beneish M-Score (Earnings Manipulation Detection)</h3>
            <div class="callout callout-warning">
                <p>Beneish M-Score could not be calculated due to insufficient financial data
                (requires 2+ consecutive years of complete data).</p>
            </div>
            """

        # Use the latest score
        latest = beneish_scores[-1] if beneish_scores else {}
        m_score = _safe_num(latest.get("m_score"))
        verdict = latest.get("verdict", "N/A")
        variables = latest.get("variables", {})
        fiscal_years = latest.get("fiscal_year_pair", latest.get("fiscal_years", "N/A"))
        missing_vars = latest.get("missing_variables", [])

        # Determine verdict styling
        if verdict == "LIKELY_MANIPULATOR":
            badge_class = "badge-critical"
            verdict_display = "⚠️ LIKELY MANIPULATOR"
            callout_class = "callout-danger"
        elif verdict == "GREY_ZONE":
            badge_class = "badge-medium"
            verdict_display = "⚡ GREY ZONE"
            callout_class = "callout-warning"
        else:
            badge_class = "badge-safe"
            verdict_display = "✅ UNLIKELY MANIPULATOR"
            callout_class = "callout-success"

        # Gauge: Map M-Score to 0-100 scale for visualization
        # M-Score range: typically -4 to +2. Lower is better.
        # -4 → 100 (safe), -1.78 → 50 (boundary), +2 → 0 (danger)
        gauge_score = max(0, min(100, ((-m_score + 2) / 6) * 100))
        gauge_html = chart_engine.gauge_svg(
            score=gauge_score, max_score=100, label=f"M-Score: {m_score:.2f}",
            thresholds={70: "#10B981", 40: "#F59E0B", 0: "#EF4444"}
        )

        # 8-Variable breakdown table
        beneish_vars = []
        beneish_var_defs = [
            # (abbrev, display_name, actual_Beneish_threshold, description)
            # Thresholds from Beneish (1999) — "The Detection of Earnings Manipulation"
            ("DSRI", "Days Sales in Receivables Index", 1.31,  "Receivables growing disproportionately faster than revenue (potential revenue inflation)"),
            ("GMI",  "Gross Margin Index",              1.19,  "Gross margin deterioration — creates pressure to manipulate earnings"),
            ("AQI",  "Asset Quality Index",             1.25,  "Rising proportion of intangible/non-current assets — signals cost capitalization"),
            ("SGI",  "Sales Growth Index",              1.607, "Revenue growth rate — NOTE: 1.607 is the mean SGI of manipulators in Beneish's sample, not an absolute fraud threshold. High SGI alone in cash-backed growth companies is a known false positive."),
            ("DEPI", "Depreciation Index",              1.00,  "Slowing depreciation rate — suggests useful life extension to boost reported earnings"),
            ("SGAI", "SG&A Expense Index",              1.00,  "SG&A expenses growing faster than revenue — overhead inflation signal"),
            ("LVGI", "Leverage Index",                  1.00,  "Total leverage increasing relative to assets — rising debt pressure"),
            ("TATA", "Total Accruals to Total Assets",  0.05,  "(Net Income − Operating Cash Flow) / Total Assets — the strongest single manipulation signal. Negative TATA means CFO exceeds Net Income (cash-backed earnings)."),
        ]
        
        for abbrev, name, default_threshold, description in beneish_var_defs:
            var_data = variables.get(abbrev, {})
            # Handle both dict format {value, threshold, flag} and raw float format
            if isinstance(var_data, dict):
                value = var_data.get('value')
                threshold = var_data.get('threshold', default_threshold)
                flag = var_data.get('flag', False)
            else:
                value = var_data if var_data is not None else None
                threshold = default_threshold
                flag = _safe_num(value) > threshold if value is not None else False
            beneish_vars.append((abbrev, name, value, threshold, description, flag))

        var_rows = []
        radar_labels = []
        radar_values = []
        radar_thresholds = []

        for abbrev, name, value, threshold, description, flag in beneish_vars:
            val = _safe_num(value)
            flag_icon = "🔴" if flag else "🟢"
            badge = "badge-critical" if flag else "badge-safe"

            var_rows.append(f"""
            <tr>
                <td class="fw-semibold">{abbrev}</td>
                <td>{name}</td>
                <td class="num">{_safe_float(value, 3)}</td>
                <td class="num">{threshold}</td>
                <td>{flag_icon} <span class="badge {badge}">{"FLAGGED" if flag else "OK"}</span></td>
                <td class="text-small text-secondary">{description}</td>
            </tr>
            """)

            if value is not None:
                radar_labels.append(abbrev)
                # Normalize: ratio of value to threshold (1.0 = at threshold)
                radar_values.append(round(val / threshold, 2) if threshold != 0 else 0)
                radar_thresholds.append(1.0)

        # Radar chart: Company values vs thresholds
        radar_html = ""
        if radar_labels:
            radar_html = chart_engine.radar_chart(
                labels=radar_labels,
                datasets=[
                    {"label": f"{self.data.get('ticker', 'Company')}", "data": radar_values, "color": "#EF4444"},
                    {"label": "Threshold", "data": radar_thresholds, "color": "#94A3B8"},
                ],
                title="Beneish 8-Variable Spider Chart (Value/Threshold Ratio)",
                height="380px",
            )

        # Historical M-Score trend (if multiple years)
        history_html = ""
        if len(beneish_scores) > 1:
            years = []
            scores = []
            for bs in beneish_scores:
                fy = bs.get("fiscal_year_pair", bs.get("fiscal_years", ""))
                ms = _safe_num(bs.get("m_score"))
                years.append(str(fy))
                scores.append(ms)

            history_html = chart_engine.line_chart(
                labels=years,
                datasets=[
                    {"label": "M-Score", "data": scores, "color": "#EF4444"},
                    {"label": "High-Risk Threshold (-1.78)", "data": [-1.78] * len(years), "color": "#F97316"},
                    {"label": "Warning Threshold (-2.22)", "data": [-2.22] * len(years), "color": "#94A3B8"},
                ],
                title="Beneish M-Score Historical Trend",
                y_label="M-Score (lower = safer)",
                height="300px",
            )

        # Build note/warning box (hypergrowth false-positive, persistence)
        note_text = latest.get("note", "")
        note_html = ""
        if note_text:
            is_fp = "HYPERGROWTH FALSE-POSITIVE WARNING" in note_text
            is_persistent = "PERSISTENT:" in note_text or "RECURRING:" in note_text
            if is_fp:
                # Extract the FP note
                fp_start = note_text.find("HYPERGROWTH FALSE-POSITIVE WARNING")
                fp_msg = note_text[fp_start:].split("|")[0].strip()
                note_html = f"""
                <div class="callout callout-warning" style="margin-top:12px; border-left: 4px solid #F97316;">
                    <p><strong>⚡ Hypergrowth False-Positive Detected</strong></p>
                    <p>{fp_msg}</p>
                    <p class="text-small text-secondary">Per Beneish (1999) research: when SGI drives the M-Score but TATA is negative (CFO &gt; Net Income), the manipulation signal is very likely a false positive from genuine revenue acceleration rather than accounting fraud.</p>
                </div>
                """
            elif is_persistent:
                persist_start = note_text.rfind("| ") + 2
                persist_msg = note_text[persist_start:].strip() if persist_start > 1 else ""
                if persist_msg:
                    note_html = f"""
                    <div class="callout callout-danger" style="margin-top:12px;">
                        <p><strong>🔁 Multi-Year Persistence Alert</strong></p>
                        <p>{persist_msg}</p>
                        <p class="text-small text-secondary">Academic best practice: sustained LIKELY_MANIPULATOR verdicts across 3+ year-pairs are a stronger signal than any single year.</p>
                    </div>
                    """

        return f"""
        <h3>Beneish M-Score (Earnings Manipulation Detection)</h3>

        <div class="grid-2">
            <div>
                {gauge_html}
            </div>
            <div class="card">
                <div class="card-header">M-Score Verdict</div>
                <div class="card-value" style="font-size:1.5rem;">{m_score:.2f}</div>
                <div style="margin-top:8px;">
                    <span class="badge badge-large {badge_class}">{verdict_display}</span>
                </div>
                <div class="card-footer">Fiscal Years: {fiscal_years}</div>
                {"<div class='card-footer text-muted'>Missing variables: " + ", ".join(missing_vars) + "</div>" if missing_vars else ""}
            </div>
        </div>

        <div class="{callout_class} callout" style="margin-top:16px;">
            <p><strong>Interpretation:</strong>
            {"An M-Score above −1.78 (8-variable model, Beneish 1999) suggests a statistically elevated probability of earnings manipulation. The grey zone is −2.22 to −1.78; scores above −1.78 represent the high-risk threshold. Further investigation into accounting practices is strongly recommended." if verdict == "LIKELY_MANIPULATOR" else
             "The M-Score falls in the grey zone (between −2.22 and −1.78 per Beneish 1999 8-variable model). This is an ambiguous result — some financial metrics warrant additional scrutiny, but the signal is not definitive." if verdict == "GREY_ZONE" else
             "The M-Score is well below −2.22 (the 8-variable model's primary threshold from Beneish 1999), indicating a low statistical probability of earnings manipulation."}
            </p>
        </div>

        {note_html}

        <h4>8-Variable Component Breakdown</h4>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Variable</th>
                        <th>Description</th>
                        <th class="num">Value</th>
                        <th class="num">Threshold</th>
                        <th>Status</th>
                        <th>What It Measures</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(var_rows)}
                </tbody>
            </table>
        </div>

        <div class="grid-2">
            <div>{radar_html}</div>
            <div>{history_html}</div>
        </div>
        """

    def _build_altman_section(self) -> str:
        """Build the Altman Z-Score analysis section."""
        altman_scores = self.fraud_distress.get("altman_scores", [])

        if not altman_scores:
            return """
            <h3>Altman Z-Score (Bankruptcy Risk)</h3>
            <div class="callout callout-warning">
                <p>Altman Z-Score could not be calculated due to insufficient financial data.</p>
            </div>
            """

        # Use the latest score
        latest = altman_scores[-1] if altman_scores else {}
        z_score = _safe_num(latest.get("z_score"))
        verdict = latest.get("verdict", "N/A")
        variables = latest.get("variables", {})
        fiscal_year = latest.get("fiscal_year", "N/A")
        formula_used = latest.get("version", latest.get("formula_used", "N/A"))

        # Determine verdict styling
        if verdict == "DISTRESS_ZONE":
            badge_class = "badge-critical"
            verdict_display = "🔴 DISTRESS ZONE"
            callout_class = "callout-danger"
        elif verdict == "GREY_ZONE":
            badge_class = "badge-medium"
            verdict_display = "🟡 GREY ZONE"
            callout_class = "callout-warning"
        else:
            badge_class = "badge-safe"
            verdict_display = "🟢 SAFE ZONE"
            callout_class = "callout-success"

        # Gauge: Z-Score typically ranges 0-5. Map to 0-100.
        gauge_score = max(0, min(100, (z_score / 5) * 100))
        gauge_html = chart_engine.gauge_svg(
            score=gauge_score, max_score=100, label=f"Z-Score: {z_score:.2f}",
            thresholds={60: "#10B981", 30: "#F59E0B", 0: "#EF4444"}
        )

        # Component variables table — handle actual key format like X1_working_capital_to_assets
        z_var_defs = [
            ("X1", "Working Capital / Total Assets", "X1_working_capital_to_assets", "Liquidity"),
            ("X2", "Retained Earnings / Total Assets", "X2_retained_earnings_to_assets", "Cumulative Profitability"),
            ("X3", "EBIT / Total Assets", "X3_ebit_to_assets", "Operating Efficiency"),
            ("X4", "Market Cap / Total Liabilities", "X4_market_cap_to_liabilities", "Market Solvency"),
            ("X5", "Revenue / Total Assets", "X5_sales_to_assets", "Asset Utilization"),
        ]

        var_rows = []
        for label, formula, actual_key, meaning in z_var_defs:
            # Try actual key first, then short key (X1, X2, etc.)
            value = variables.get(actual_key, variables.get(label))
            var_rows.append(f"""
            <tr>
                <td class="fw-semibold">{label}</td>
                <td>{formula}</td>
                <td class="num">{_safe_float(value, 4)}</td>
                <td class="text-secondary">{meaning}</td>
            </tr>
            """)

        # Historical Z-Score trend
        history_html = ""
        if len(altman_scores) > 1:
            years = []
            scores = []
            for az in altman_scores:
                years.append(str(az.get("fiscal_year", "")))
                scores.append(_safe_num(az.get("z_score")))

            # Determine thresholds based on formula
            safe_line = 2.99 if "original" in str(formula_used).lower() else 2.60
            distress_line = 1.81 if "original" in str(formula_used).lower() else 1.10

            history_html = chart_engine.line_chart(
                labels=years,
                datasets=[
                    {"label": "Z-Score", "data": scores, "color": "#4A90D9"},
                    {"label": f"Safe Zone (>{safe_line})", "data": [safe_line] * len(years), "color": "#10B981"},
                    {"label": f"Distress (<{distress_line})", "data": [distress_line] * len(years), "color": "#EF4444"},
                ],
                title="Altman Z-Score Historical Trend",
                y_label="Z-Score (higher = safer)",
                height="300px",
            )
        
        # Z-Score bar chart for components (contribution visual)
        component_chart = ""
        comp_labels = []
        comp_values = []
        is_non_mfg = "non" in str(formula_used).lower() or "prime" in str(formula_used).lower()
        comp_weights = [6.56, 3.26, 6.72, 1.05, 0] if is_non_mfg else [1.2, 1.4, 3.3, 0.6, 0.999]
        
        for i, (label, formula, actual_key, meaning) in enumerate(z_var_defs):
            value = variables.get(actual_key, variables.get(label))
            val = _safe_num(value)
            weight = comp_weights[i] if i < len(comp_weights) else 1.0
            contribution = val * weight
            comp_labels.append(label)
            comp_values.append(round(contribution, 3))
        
        if comp_labels:
            component_chart = chart_engine.bar_chart(
                labels=comp_labels,
                datasets=[{"label": "Weighted Contribution to Z-Score", "data": comp_values, "color": "#4A90D9"}],
                title="Z-Score Component Contributions",
                y_label="Weighted Value",
                height="280px",
            )

        return f"""
        <h3>Altman Z-Score (Bankruptcy Risk)</h3>

        <div class="grid-2">
            <div>
                {gauge_html}
            </div>
            <div class="card">
                <div class="card-header">Z-Score Verdict</div>
                <div class="card-value" style="font-size:1.5rem;">{z_score:.2f}</div>
                <div style="margin-top:8px;">
                    <span class="badge badge-large {badge_class}">{verdict_display}</span>
                </div>
                <div class="card-footer">Fiscal Year: {fiscal_year} | Formula: {formula_used}</div>
            </div>
        </div>

        <div class="{callout_class} callout" style="margin-top:16px;">
            <p><strong>Interpretation:</strong>
            {"The Z-Score falls in the distress zone, indicating a statistically significant probability of financial distress or bankruptcy within the next 2 years. This is a DEAL BREAKER condition." if verdict == "DISTRESS_ZONE" else
             "The Z-Score falls in the grey zone, indicating moderate financial risk. The company's financial stability should be monitored closely." if verdict == "GREY_ZONE" else
             "The Z-Score is in the safe zone, indicating a low statistical probability of bankruptcy based on the model's financial indicators."}
            </p>
        </div>

        <h4>Z-Score Component Variables</h4>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Component</th>
                        <th>Formula</th>
                        <th class="num">Value</th>
                        <th>What It Measures</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(var_rows)}
                </tbody>
            </table>
        </div>

        <div class="grid-2">
            <div>{component_chart}</div>
            <div>{history_html}</div>
        </div>
        """
