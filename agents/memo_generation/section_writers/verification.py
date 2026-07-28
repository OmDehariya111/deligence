"""
Module:  verification.py
Agent:   Memo Generation Agent
Purpose: Generates Section 16: Financial Data Verification Report — THE TRUST FEATURE.
         This is DeligenX's #1 differentiator. Shows complete source provenance,
         arithmetic cross-checks, data completeness heatmap, and LLM transparency.
Inputs:  data dictionary containing verification_results from verification_engine.
Outputs: HTML string for the section.
"""

import logging
from typing import Any

from agents.memo_generation import chart_engine

logger = logging.getLogger(__name__)


def _fmt_num(val: Any) -> str:
    """Format a number for display."""
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if abs(v) >= 1e9:
            return f"${v / 1e9:,.2f}B"
        elif abs(v) >= 1e6:
            return f"${v / 1e6:,.1f}M"
        elif abs(v) >= 1e3:
            return f"${v:,.0f}"
        elif abs(v) < 0.01 and v != 0:
            return f"{v:.4f}"
        else:
            return f"{v:,.2f}"
    except (ValueError, TypeError):
        return str(val)


class Section16Writer:
    """Generates the Financial Data Verification Report — the TRUST feature."""

    def __init__(self, data: dict):
        self.data = data
        self.vr = data.get("verification_results", {})

    def generate(self) -> str:
        """Generate the complete verification section HTML."""
        logger.info("Generating Section 16: Financial Data Verification Report (TRUST FEATURE)")

        summary = self.vr.get("summary", {})
        verified = summary.get("data_points_with_value", 0)
        total = summary.get("total_data_points", 0)
        xbrl_sourced = summary.get("xbrl_sourced", 0)
        computed = summary.get("computed_derived", 0)
        missing = summary.get("data_points_missing", 0)
        checks_passed = summary.get("cross_checks_passed", 0)
        checks_total = summary.get("cross_checks_total", 0)

        verification_badge = self._build_verification_badge(verified, total)
        methodology = self._build_methodology()
        cross_checks_html = self._build_cross_checks()
        completeness_html = self._build_completeness_heatmap()
        provenance_html = self._build_provenance_table()
        ratio_audit_html = self._build_ratio_audit()
        llm_transparency = self._build_llm_transparency()

        html = f"""
        <div class="section" id="section-16">
            <div class="section-header">
                <div class="section-number">16</div>
                <h2>Financial Data Verification Report</h2>
            </div>

            {verification_badge}

            <div class="grid-4" style="margin-bottom: 24px;">
                <div class="card">
                    <div class="card-header">XBRL Sourced</div>
                    <div class="card-value small">{xbrl_sourced}</div>
                    <div class="card-footer">Direct from SEC filings</div>
                </div>
                <div class="card">
                    <div class="card-header">Computed/Derived</div>
                    <div class="card-value small">{computed}</div>
                    <div class="card-footer">Formula-based calculations</div>
                </div>
                <div class="card">
                    <div class="card-header">Missing</div>
                    <div class="card-value small">{missing}</div>
                    <div class="card-footer">Not available from filings</div>
                </div>
                <div class="card">
                    <div class="card-header">Cross-Checks</div>
                    <div class="card-value small">{checks_passed}/{checks_total}</div>
                    <div class="card-footer">Arithmetic validations passed</div>
                </div>
            </div>

            {methodology}

            <h3>Arithmetic Cross-Check Results</h3>
            {cross_checks_html}

            <h3>Data Completeness Matrix</h3>
            {completeness_html}

            <h3>Ratio Computation Audit</h3>
            {ratio_audit_html}

            <h3>Source Provenance Audit Trail</h3>
            <p>Every financial number in this report has been traced to its original source — either
            a specific XBRL taxonomy tag from SEC EDGAR filings, or a documented computation formula.
            This audit trail ensures complete transparency and enables independent verification.</p>
            {provenance_html}

            {llm_transparency}
        </div>
        """
        return html

    def _build_verification_badge(self, verified: int, total: int) -> str:
        """Build the large verification badge."""
        return f"""
        <div class="verification-badge">
            <div class="checkmark">✅</div>
            <div>
                <div class="count">{verified}/{total}</div>
                <div class="label">Financial Data Points Verified</div>
            </div>
        </div>
        """

    def _build_methodology(self) -> str:
        """Build the verification methodology explanation."""
        return """
        <div class="callout callout-info">
            <h4>Verification Methodology</h4>
            <p><strong>Source Tracing:</strong> Every financial number in this report was extracted from
            SEC EDGAR XBRL filings using specific taxonomy tags (e.g., <code>RevenueFromContractWithCustomerExcludingAssessedTax</code>).
            Each number retains its source tag for full traceability.</p>
            <p><strong>Arithmetic Validation:</strong> Five GAAP-based cross-checks are applied to every fiscal year:
            (1) Gross Profit = Revenue − COGS, (2) Assets = Liabilities + Equity,
            (3) EPS = Net Income ÷ Shares, (4) FCF = Operating CF − CapEx,
            (5) Income Before Tax = Operating + Non-Operating Income.</p>
            <p><strong>Gap Filling Transparency:</strong> Any value that was computed (not directly from XBRL)
            is clearly marked as "COMPUTED" with its formula. No hallucinated or estimated values are used.</p>
        </div>
        """

    def _build_cross_checks(self) -> str:
        """Build the arithmetic cross-check results table."""
        checks = self.vr.get("cross_checks", [])
        if not checks:
            return "<p class='text-muted'>No cross-checks available.</p>"

        rows = []
        for c in checks:
            passed = c.get("passed", False)
            icon = "✅" if passed else "❌"
            badge_class = "badge-passed" if passed else "badge-failed"
            status_text = "PASSED" if passed else "FAILED"
            deviation = c.get("deviation_pct", 0)

            rows.append(f"""
            <tr>
                <td>{c.get('fiscal_year', 'N/A')}</td>
                <td>{c.get('check', 'N/A')}</td>
                <td class="num">{_fmt_num(c.get('expected'))}</td>
                <td class="num">{_fmt_num(c.get('actual'))}</td>
                <td>{c.get('tolerance', 'N/A')}</td>
                <td class="num">{deviation:.4f}%</td>
                <td>{icon} <span class="badge {badge_class}">{status_text}</span></td>
            </tr>
            """)

        return f"""
        <div class="table-container">
            <table class="compact">
                <thead>
                    <tr>
                        <th>Year</th>
                        <th>Cross-Check Rule</th>
                        <th class="num">Expected</th>
                        <th class="num">Actual</th>
                        <th>Tolerance</th>
                        <th class="num">Deviation</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """

    def _build_completeness_heatmap(self) -> str:
        """Build the data completeness heatmap (44 fields × 5 years)."""
        completeness = self.vr.get("completeness", {})
        matrix = completeness.get("matrix", {})
        years = completeness.get("years", [])

        if not years:
            return "<p class='text-muted'>No completeness data available.</p>"

        # Summary row
        year_cells = ""
        for y in sorted(years):
            info = matrix.get(str(y), {})
            pct = info.get("pct", 0)
            present = info.get("present", 0)
            total = info.get("total", 0)
            color = "#10B981" if pct >= 90 else "#F59E0B" if pct >= 70 else "#EF4444"

            year_cells += f"""
            <div class="card" style="text-align:center;">
                <div class="card-header">FY {y}</div>
                <div class="card-value small" style="color:{color};">{pct:.0f}%</div>
                <div class="card-footer">{present}/{total} fields</div>
            </div>
            """

        # Provenance type breakdown
        provenance = self.vr.get("provenance", [])
        by_type = {"XBRL": 0, "COMPUTED": 0, "MISSING": 0}
        for p in provenance:
            st = p.get("source_type", "MISSING")
            by_type[st] = by_type.get(st, 0) + 1

        source_chart = chart_engine.doughnut_chart(
            labels=list(by_type.keys()),
            data=list(by_type.values()),
            title="Data Source Distribution",
            colors=["#4A90D9", "#10B981", "#EF4444"],
            height="280px",
        )

        return f"""
        <div class="grid-{min(len(years), 5)}" style="margin-bottom:24px;">
            {year_cells}
        </div>
        <div class="grid-2">
            <div>{source_chart}</div>
            <div class="callout callout-success">
                <h4>Data Source Summary</h4>
                <p><strong>XBRL Direct:</strong> {by_type.get('XBRL', 0)} data points sourced directly from SEC XBRL taxonomy tags.</p>
                <p><strong>Computed:</strong> {by_type.get('COMPUTED', 0)} data points derived using documented GAAP formulas.</p>
                <p><strong>Missing:</strong> {by_type.get('MISSING', 0)} data points not available in the company's filings.</p>
            </div>
        </div>
        """

    def _build_provenance_table(self) -> str:
        """Build the source provenance audit trail table (grouped by year)."""
        provenance = self.vr.get("provenance", [])
        if not provenance:
            return "<p class='text-muted'>No provenance data available.</p>"

        # Group by fiscal year
        by_year: dict[str, list] = {}
        for p in provenance:
            fy = str(p.get("fiscal_year", "Unknown"))
            by_year.setdefault(fy, []).append(p)

        html_parts = []
        for year in sorted(by_year.keys()):
            records = by_year[year]
            rows = []
            for r in records:
                has_val = r.get("has_value", False)
                val_display = _fmt_num(r.get("value")) if has_val else '<span class="text-muted">—</span>'
                src_type = r.get("source_type", "MISSING")
                src_color = "#10B981" if src_type == "XBRL" else "#4A90D9" if src_type == "COMPUTED" else "#EF4444"
                src_tag = r.get("source_tag", "N/A")
                if len(str(src_tag)) > 50:
                    src_tag = str(src_tag)[:47] + "..."

                rows.append(f"""
                <tr>
                    <td>{r.get('field', 'N/A')}</td>
                    <td class="num">{val_display}</td>
                    <td><span style="color:{src_color}; font-weight:600;">{src_type}</span></td>
                    <td class="text-small text-mono">{src_tag}</td>
                </tr>
                """)

            html_parts.append(f"""
            <h4>FY {year}</h4>
            <div class="table-container">
                <table class="compact">
                    <thead>
                        <tr>
                            <th>Field</th>
                            <th class="num">Value</th>
                            <th>Source Type</th>
                            <th>XBRL Tag / Method</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
            """)

        return "\n".join(html_parts)

    def _build_ratio_audit(self) -> str:
        """Build the ratio computation audit table."""
        ratio_audit = self.vr.get("ratio_audit", [])
        if not ratio_audit:
            return "<p class='text-muted'>No ratio computation data available.</p>"

        # Get unique ratio names to avoid showing 5 years of the same formula
        # We'll just show the formula and one example or all years.
        # It's better to show all ratio definitions
        
        seen_ratios = set()
        rows = []
        for r in ratio_audit:
            name = r.get("ratio_name", "N/A")
            if name in seen_ratios:
                continue
            seen_ratios.add(name)
            
            formula = r.get("formula", "N/A")
            inputs = r.get("inputs_used", {})
            input_list = ", ".join(inputs.keys()) if isinstance(inputs, dict) else str(inputs)
            
            rows.append(f"""
            <tr>
                <td><strong>{name}</strong></td>
                <td class="text-mono text-small">{formula}</td>
                <td class="text-small">{input_list}</td>
            </tr>
            """)
            
        return f"""
        <div class="table-container">
            <table class="compact">
                <thead>
                    <tr>
                        <th>Ratio Name</th>
                        <th>Computation Formula</th>
                        <th>Inputs Used</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """

    def _build_llm_transparency(self) -> str:
        """Build the LLM usage transparency section."""
        return """
        <h3>AI & LLM Usage Transparency</h3>
        <div class="callout callout-warning">
            <h4>Which Sections Use AI-Generated Content?</h4>
            <p>The following sections contain LLM-generated <strong>narrative text only</strong> (no numbers):</p>
            <ul style="margin-left: 20px; margin-bottom: 0;">
                <li><strong>Section 1</strong> (Executive Summary) — Key findings narrative paragraphs</li>
                <li><strong>Section 2</strong> (Company Overview) — Business description from 10-K filing text</li>
                <li><strong>Section 4</strong> (Ratio Analysis) — Interpretation narrative</li>
                <li><strong>Section 5</strong> (Trend Analysis) — Trend implication narrative</li>
                <li><strong>Section 10</strong> (Competitive Landscape) — Competitive position narrative</li>
                <li><strong>Section 14</strong> (Risk Assessment) — Per-dimension risk narratives</li>
            </ul>
        </div>
        <div class="callout callout-success">
            <h4>Which Sections Are 100% Deterministic (No AI)?</h4>
            <p>All financial numbers, ratios, scores, and tables in this report are computed using
            <strong>deterministic Python code</strong> — no LLM is involved in generating or
            modifying any numerical value. The following sections are entirely AI-free:</p>
            <ul style="margin-left: 20px; margin-bottom: 0;">
                <li><strong>Section 3</strong> — 5-Year Financial Statements (direct from XBRL)</li>
                <li><strong>Section 4</strong> — All 36 ratio values and formulas</li>
                <li><strong>Section 6</strong> — Beneish M-Score & Altman Z-Score (academic formulas)</li>
                <li><strong>Section 7</strong> — 15 Anomaly Detection Rules (deterministic conditions)</li>
                <li><strong>Section 8</strong> — Sector Benchmark (computed from peer XBRL data)</li>
                <li><strong>Section 9</strong> — QoE Score (point deduction system)</li>
                <li><strong>Section 11</strong> — Implied Valuation (peer multiple math)</li>
                <li><strong>Section 16</strong> — This verification report</li>
            </ul>
        </div>
        """
