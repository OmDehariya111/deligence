"""
Module:  appendix.py
Agent:   Memo Generation Agent
Purpose: Generates Section 17: Appendix & Methodology — technical reference for deep-dive readers.
Inputs:  data dictionary with ratio formulas, risk methodology, anomaly rules.
Outputs: HTML string for the appendix section.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# All 36 ratio definitions with formulas
RATIO_DEFINITIONS = [
    # Profitability
    ("Gross Margin", "(Gross Profit / Revenue) × 100", "percent", "Profitability"),
    ("Operating Margin", "(Operating Income / Revenue) × 100", "percent", "Profitability"),
    ("Net Profit Margin", "(Net Income / Revenue) × 100", "percent", "Profitability"),
    ("EBITDA Margin", "(EBITDA / Revenue) × 100", "percent", "Profitability"),
    ("Return on Assets (ROA)", "(Net Income / Avg Total Assets) × 100", "percent", "Profitability"),
    ("Return on Equity (ROE)", "(Net Income / Avg Total Equity) × 100", "percent", "Profitability"),
    ("Return on Invested Capital (ROIC)", "(Operating Income / Invested Capital) × 100", "percent", "Profitability"),
    ("Effective Tax Rate", "(Tax Expense / Income Before Tax) × 100", "percent", "Profitability"),
    # Liquidity
    ("Current Ratio", "Current Assets / Current Liabilities", "multiple", "Liquidity"),
    ("Quick Ratio", "(Current Assets − Inventory) / Current Liabilities", "multiple", "Liquidity"),
    ("Cash Ratio", "Cash / Current Liabilities", "multiple", "Liquidity"),
    # Leverage
    ("Debt-to-Equity", "Total Liabilities / Total Equity", "multiple", "Leverage"),
    ("Debt-to-EBITDA", "Long-term Debt / EBITDA", "multiple", "Leverage"),
    ("Net Debt-to-EBITDA", "Net Debt / EBITDA", "multiple", "Leverage"),
    ("Interest Coverage", "Operating Income / Interest Expense", "multiple", "Leverage"),
    ("Debt-to-Assets", "Total Liabilities / Total Assets", "ratio", "Leverage"),
    # Efficiency
    ("Asset Turnover", "Revenue / Total Assets", "multiple", "Efficiency"),
    ("Inventory Turnover", "COGS / Average Inventory", "multiple", "Efficiency"),
    ("Days Sales Outstanding (DSO)", "(AR / Revenue) × 365", "days", "Efficiency"),
    ("Days Payable Outstanding (DPO)", "(AP / COGS) × 365", "days", "Efficiency"),
    ("Cash Conversion Cycle (CCC)", "DSO + DIO − DPO", "days", "Efficiency"),
    # Cash Flow Quality
    ("FCF Margin", "(FCF / Revenue) × 100", "percent", "Cash Flow"),
    ("FCF-to-Net Income", "FCF / Net Income", "ratio", "Cash Flow"),
    ("OCF-to-Revenue", "(Operating CF / Revenue) × 100", "percent", "Cash Flow"),
    ("CapEx-to-Revenue", "(CapEx / Revenue) × 100", "percent", "Cash Flow"),
    # Growth
    ("Revenue YoY Growth", "((Rev_t − Rev_t-1) / Rev_t-1) × 100", "percent", "Growth"),
    ("Gross Profit YoY Growth", "((GP_t − GP_t-1) / GP_t-1) × 100", "percent", "Growth"),
    ("Operating Income YoY Growth", "((OpInc_t − OpInc_t-1) / |OpInc_t-1|) × 100", "percent", "Growth"),
    ("Net Income YoY Growth", "((NI_t − NI_t-1) / |NI_t-1|) × 100", "percent", "Growth"),
    ("EPS YoY Growth", "((EPS_t − EPS_t-1) / |EPS_t-1|) × 100", "percent", "Growth"),
    ("FCF YoY Growth", "((FCF_t − FCF_t-1) / |FCF_t-1|) × 100", "percent", "Growth"),
    # Valuation
    ("P/E Ratio", "Market Cap / Net Income", "multiple", "Valuation"),
    ("Price-to-FCF", "Market Cap / FCF", "multiple", "Valuation"),
    ("EV/EBITDA", "Enterprise Value / EBITDA", "multiple", "Valuation"),
    # CAGR
    ("Revenue CAGR", "((Rev_latest / Rev_oldest)^(1/n) − 1) × 100", "percent", "CAGR"),
    ("Net Income CAGR", "((NI_latest / NI_oldest)^(1/n) − 1) × 100", "percent", "CAGR"),
]

ANOMALY_RULES = [
    ("AF-001", "Revenue-Cash Divergence", "Rev YoY >15% AND OCF YoY <0%", "HIGH"),
    ("AF-002", "Gross Margin Compression", "Single-year >5pp drop OR 3yr decline", "HIGH/MEDIUM"),
    ("AF-003", "Rapid Debt Accumulation", "Debt/EBITDA increased >1.5× in 2yr", "HIGH"),
    ("AF-004", "FCF Below Net Income", "FCF/NI < 0.8 for 2+ consecutive years", "MEDIUM/HIGH"),
    ("AF-005", "Interest Coverage Danger", "Interest Coverage < 1.5×", "CRITICAL/HIGH"),
    ("AF-006", "Current Ratio Below 1.0", "Current Ratio < 1.0", "HIGH"),
    ("AF-007", "High Goodwill Concentration", "Goodwill > 35% of Total Assets", "MEDIUM"),
    ("AF-008", "CapEx Sudden Change", "CapEx/Rev changed >30% relative", "LOW/MEDIUM"),
    ("AF-009", "SG&A Overhead Inflation", "SG&A/Rev rising 3+ yrs + rev growth slowing", "MEDIUM"),
    ("AF-010", "High Accruals (TATA)", "TATA > 5% (NI−OCF)/Assets", "MEDIUM"),
    ("AF-011", "Non-Op Income Dependency", "Non-op income >25% of NI (was <10%)", "MEDIUM"),
    ("AF-012", "Effective Tax Rate Anomaly", "ETR changed >10pp YoY", "MEDIUM"),
    ("AF-013", "Receivables Outpacing Revenue", "DSRI > 1.31 (Beneish threshold)", "MEDIUM"),
    ("AF-014", "Inventory Build-up", "Inventory growth > (Rev growth + 20%)", "MEDIUM"),
    ("AF-015", "Declining FCF Despite +NI", "NI growing + FCF negative/declining >20%", "HIGH"),
]


class Section17Writer:
    """Generates the Appendix & Methodology section."""

    def __init__(self, data: dict):
        self.data = data

    def generate(self) -> str:
        """Generate the complete appendix section HTML."""
        logger.info("Generating Section 17: Appendix & Methodology")

        run_id = self.data.get("run_id", "Unknown")
        timestamp = datetime.now().astimezone().isoformat()

        pipeline_overview = self._build_pipeline_overview()
        ratio_reference = self._build_ratio_reference()
        risk_methodology = self._build_risk_methodology()
        anomaly_reference = self._build_anomaly_reference()
        model_reference = self._build_model_reference()
        glossary = self._build_glossary()

        html = f"""
        <div class="section" id="section-17">
            <div class="section-header">
                <div class="section-number">17</div>
                <h2>Appendix & Methodology</h2>
            </div>

            {pipeline_overview}

            <div class="divider"></div>
            {ratio_reference}

            <div class="divider"></div>
            {risk_methodology}

            <div class="divider"></div>
            {anomaly_reference}

            <div class="divider"></div>
            {model_reference}

            <div class="divider"></div>
            {glossary}

            <div class="divider"></div>
            <h3>Report Generation Metadata</h3>
            <div class="callout callout-info">
                <p><strong>Run ID:</strong> <span class="text-mono">{run_id}</span></p>
                <p><strong>Report Generated:</strong> {timestamp}</p>
                <p><strong>Platform:</strong> DeligenX AI-Powered Due Diligence</p>
                <p><strong>Pipeline:</strong> 5-Agent Sequential (Ingestion → Analysis → Market Intelligence → Risk Assessment → Memo Generation)</p>
                <p><strong>Ingestion Duration:</strong> {self.data.get('ingestion_duration', 'N/A')}s</p>
                <p><strong>Data Source:</strong> SEC EDGAR (XBRL CompanyFacts, Filing Documents), Yahoo Finance (Market Data), NewsAPI (Sentiment), FRED (Macro Indicators)</p>
                <p><strong>LLM Models:</strong> Google Gemini 2.5 Pro (narratives), Gemini 2.5 Flash (extraction)</p>
            </div>
        </div>
        """
        return html

    def _build_pipeline_overview(self) -> str:
        """Build the 4-agent pipeline overview."""
        return """
        <h3>Methodology Overview: 5-Agent AI Pipeline</h3>
        <p>DeligenX uses a sequential multi-agent architecture where each agent builds on the outputs
        of its predecessors. All financial data is sourced from SEC EDGAR XBRL filings and validated
        using arithmetic cross-checks before any analysis begins.</p>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Agent</th>
                        <th>Role</th>
                        <th>Key Outputs</th>
                        <th>LLM Usage</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>1. Ingestion</strong></td>
                        <td>Data collection & validation</td>
                        <td>44 financial fields × 5 years, ChromaDB embeddings, XBRL provenance</td>
                        <td>None (pure data extraction)</td>
                    </tr>
                    <tr>
                        <td><strong>2. Analysis</strong></td>
                        <td>Quantitative financial analysis</td>
                        <td>36 ratios, trend analysis, Beneish/Altman, 15 anomaly rules, QoE score</td>
                        <td>None (deterministic math)</td>
                    </tr>
                    <tr>
                        <td><strong>3. Market Intelligence</strong></td>
                        <td>External market & competitive data</td>
                        <td>Competitors, comps table, valuation, news sentiment, moat, macro</td>
                        <td>4 calls (competitor extraction, sentiment, moat, verdict)</td>
                    </tr>
                    <tr>
                        <td><strong>4. Risk Assessment</strong></td>
                        <td>6-dimension risk scoring</td>
                        <td>Risk dimensions, evidence, deal breakers, mitigations, composite score</td>
                        <td>~20 calls (evidence extraction + analysis per dimension)</td>
                    </tr>
                    <tr>
                        <td><strong>5. Memo Generation</strong></td>
                        <td>Report compilation & verification</td>
                        <td>17-section HTML investment memo with charts & verification</td>
                        <td>6 calls (professional narrative paragraphs only)</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """

    def _build_ratio_reference(self) -> str:
        """Build the complete ratio definitions table."""
        rows = []
        current_category = ""
        for name, formula, unit, category in RATIO_DEFINITIONS:
            if category != current_category:
                rows.append(f'<tr><td colspan="4" style="background:#1B2A4A; color:white; font-weight:700; padding:8px 12px;">{category}</td></tr>')
                current_category = category
            rows.append(f"""
            <tr>
                <td>{name}</td>
                <td class="text-mono text-small">{formula}</td>
                <td>{unit}</td>
            </tr>
            """)

        return f"""
        <h3>Financial Ratio Definitions (All 36 Ratios)</h3>
        <div class="table-container">
            <table class="compact">
                <thead>
                    <tr>
                        <th>Ratio Name</th>
                        <th>Formula</th>
                        <th>Unit</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """

    def _build_risk_methodology(self) -> str:
        """Build the risk scoring methodology explanation."""
        return """
        <h3>Risk Scoring Methodology</h3>
        <p>The Risk Assessment Agent scores companies across 6 dimensions using a combination of
        deterministic rules, ChromaDB RAG extraction, and LLM-powered analysis.</p>

        <h4>Company Tier System</h4>
        <div class="table-container">
            <table class="compact">
                <thead><tr><th>Tier</th><th>Classification</th><th>Impact</th></tr></thead>
                <tbody>
                    <tr><td>MEGA</td><td>Market Cap ≥ $200B or Revenue ≥ $100B</td><td>Higher thresholds for risk triggers</td></tr>
                    <tr><td>LARGE</td><td>Market Cap ≥ $10B or Revenue ≥ $5B</td><td>Standard thresholds</td></tr>
                    <tr><td>MID</td><td>Market Cap ≥ $2B or Revenue ≥ $1B</td><td>Slightly lower thresholds</td></tr>
                    <tr><td>SMALL</td><td>Market Cap ≥ $300M or Revenue ≥ $200M</td><td>Lower thresholds, higher sensitivity</td></tr>
                    <tr><td>MICRO</td><td>Below SMALL thresholds</td><td>Most sensitive risk detection</td></tr>
                </tbody>
            </table>
        </div>

        <h4>6 Risk Dimensions & Weights</h4>
        <div class="table-container">
            <table class="compact">
                <thead><tr><th>Dimension</th><th>Default Weight</th><th>Sub-Dimensions Evaluated</th></tr></thead>
                <tbody>
                    <tr><td>Financial Risk</td><td>25%</td><td>Solvency, Liquidity, Profitability, Cash Flow, Capital Structure, Earnings Quality, Growth Sustainability</td></tr>
                    <tr><td>Market Risk</td><td>15%</td><td>Volatility, Analyst Sentiment, Short Interest, Earnings History, Sector Momentum</td></tr>
                    <tr><td>Operational Risk</td><td>20%</td><td>Supply Chain, Key Personnel, Technology, Regulatory, Customer Concentration</td></tr>
                    <tr><td>Legal & Regulatory</td><td>15%</td><td>Active Litigation, Regulatory Actions, Compliance, Tax Disputes, IP Disputes, Environmental</td></tr>
                    <tr><td>Management Quality</td><td>10%</td><td>Leadership Stability, Compensation Alignment, Board Independence, MD&A Credibility, Strategic Execution</td></tr>
                    <tr><td>ESG Risk</td><td>15%</td><td>Environmental, Social, Governance, ESG Momentum</td></tr>
                </tbody>
            </table>
        </div>

        <h4>8 Deal Breaker Conditions</h4>
        <p>Any of these conditions can override the composite score and escalate the investment stance:</p>
        <ol style="margin-left: 20px;">
            <li>Going Concern Opinion from auditors</li>
            <li>Altman Z-Score in DISTRESS_ZONE</li>
            <li>Beneish M-Score indicates LIKELY_MANIPULATOR</li>
            <li>Active SEC Investigation or Enforcement Action</li>
            <li>Material Weakness in Internal Controls</li>
            <li>Financial Restatement in last 2 years</li>
            <li>Auditor Change (red flag pattern)</li>
            <li>Interest Coverage below 1.0×</li>
        </ol>
        """

    def _build_anomaly_reference(self) -> str:
        """Build the anomaly detection rules reference table."""
        rows = []
        for rule_id, title, condition, severity in ANOMALY_RULES:
            rows.append(f"""
            <tr>
                <td class="text-mono">{rule_id}</td>
                <td>{title}</td>
                <td class="text-small">{condition}</td>
                <td><span class="badge badge-{severity.split('/')[0].lower()}">{severity}</span></td>
            </tr>
            """)

        return f"""
        <h3>Anomaly Detection Rules (All 15 Rules)</h3>
        <div class="table-container">
            <table class="compact">
                <thead>
                    <tr><th>Rule ID</th><th>Title</th><th>Trigger Condition</th><th>Severity</th></tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """

    def _build_model_reference(self) -> str:
        """Build the Beneish & Altman model reference."""
        return """
        <h3>Academic Financial Models</h3>

        <h4>Beneish M-Score (Earnings Manipulation Detection)</h4>
        <p class="text-mono text-small" style="background:#F1F5F9; padding:12px; border-radius:8px;">
            M = −4.840 + 0.920×DSRI + 0.528×GMI + 0.404×AQI + 0.892×SGI + 0.115×DEPI − 0.172×SGAI + 4.679×TATA − 0.327×LVGI
        </p>
        <p><strong>Thresholds:</strong> M > −1.78 = LIKELY MANIPULATOR | −2.22 ≤ M ≤ −1.78 = GREY ZONE | M < −2.22 = UNLIKELY MANIPULATOR</p>

        <h4>Altman Z-Score (Bankruptcy Risk)</h4>
        <p class="text-mono text-small" style="background:#F1F5F9; padding:12px; border-radius:8px;">
            Z'' = 6.56×(Working Capital/Assets) + 3.26×(Retained Earnings/Assets) + 6.72×(EBIT/Assets) + 1.05×(Market Cap/Liabilities)
        </p>
        <p><strong>Thresholds (Non-Mfg):</strong> Z'' > 2.60 = SAFE | 1.10 ≤ Z'' ≤ 2.60 = GREY | Z'' < 1.10 = DISTRESS</p>
        """

    def _build_glossary(self) -> str:
        """Build the financial terms glossary."""
        terms = [
            ("BLUF", "Bottom Line Up Front — executive summary style presenting conclusions first"),
            ("CAGR", "Compound Annual Growth Rate"),
            ("CIK", "Central Index Key — SEC's unique 10-digit company identifier"),
            ("DCF", "Discounted Cash Flow"),
            ("EBITDA", "Earnings Before Interest, Taxes, Depreciation & Amortization"),
            ("EV", "Enterprise Value — Market Cap + Net Debt"),
            ("FCF", "Free Cash Flow — Operating Cash Flow minus Capital Expenditures"),
            ("LTM", "Last Twelve Months — trailing 12-month financial figures"),
            ("MD&A", "Management's Discussion & Analysis (10-K Section 7)"),
            ("QoE", "Quality of Earnings — assessment of earnings sustainability"),
            ("RAG", "Retrieval-Augmented Generation — LLM technique using document context"),
            ("SIC", "Standard Industrial Classification — industry code system"),
            ("XBRL", "eXtensible Business Reporting Language — structured SEC filing format"),
        ]

        rows = "".join(f"<tr><td class='fw-semibold'>{term}</td><td>{defn}</td></tr>" for term, defn in terms)

        return f"""
        <h3>Glossary</h3>
        <div class="table-container">
            <table class="compact">
                <thead><tr><th>Term</th><th>Definition</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        """
