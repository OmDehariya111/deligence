"""
Module:  anomaly_engine.py
Agent:   Analysis Agent
Purpose: Evaluates deterministic anomaly rules based on financial ratios and data.
         # Is module ka main kaam 15 alag-alag rules (AF-001 to AF-015) chala kar 
         # company ke data me koi 'red flag' ya ajeeb (anomaly) chiz dhoondna hai.
"""

from typing import Any
from schemas.pydantic_models import (
    RatioRecord, RatioTrend, FraudDistressOutput, AnomalyFlag, AnomalyOutput
)

class AnomalyEngine:
    def __init__(
        self,
        ratios: list[RatioRecord],
        trends: list[RatioTrend],
        fraud_data: FraudDistressOutput | None,
        raw_data: dict[int, dict[str, Any]]
    ):
        self.ratios = ratios
        self.trends = {t.ratio_name: t for t in trends}
        self.fraud_data = fraud_data
        self.raw_data = raw_data
        
        # Build quick lookups
        self.ratios_by_year_name = {}
        for r in ratios:
            if r.fiscal_year not in self.ratios_by_year_name:
                self.ratios_by_year_name[r.fiscal_year] = {}
            self.ratios_by_year_name[r.fiscal_year][r.ratio_name] = r

        self.available_years = sorted(self.raw_data.keys())
        self.skipped_rules = [] # Jo rules data na milne ki wajah se run nahi ho paaye wo isme jayenge
        self.flags = [] # Jo anomalies detect hui (warnings) wo isme jayengi

    def _get_ratio(self, year: int, name: str) -> float | None:
        r = self.ratios_by_year_name.get(year, {}).get(name)
        if not r:
            return None
        if r.status in ["COMPUTED", "EXTREME_VALUE"]:
            return r.value
        return None

    def _get_raw(self, year: int, name: str) -> float | None:
        return self.raw_data.get(year, {}).get(name)

    def _safe_div(self, num: float | None, den: float | None) -> float | None:
        if num is None or den is None or den == 0:
            return None
        return num / den

    def run(self) -> AnomalyOutput:
        if not self.available_years:
            return AnomalyOutput(
                total_flags=0, critical=0, high=0, medium=0, low=0,
                rules_skipped_missing_data=["No financial data available."],
                flags=[]
            )
            
        current_year = self.available_years[-1]

        # Rule evaluation: Sabhi 15 anomaly rules ko latest saal (current_year) par test kar rahe hain
        self._eval_af001(current_year)
        self._eval_af002(current_year)
        self._eval_af003(current_year)
        self._eval_af004(current_year)
        self._eval_af005(current_year)
        self._eval_af006(current_year)
        self._eval_af007(current_year)
        self._eval_af008(current_year)
        self._eval_af009(current_year)
        self._eval_af010(current_year)
        self._eval_af011(current_year)
        self._eval_af012(current_year)
        self._eval_af013(current_year)
        self._eval_af014(current_year)
        self._eval_af015(current_year)

        # Aggregate counts (Total kitni CRITICAL, HIGH, MEDIUM, LOW flags mile)
        c = sum(1 for f in self.flags if f.severity == "CRITICAL")
        h = sum(1 for f in self.flags if f.severity == "HIGH")
        m = sum(1 for f in self.flags if f.severity == "MEDIUM")
        l = sum(1 for f in self.flags if f.severity == "LOW")

        # Sort severity CRITICAL -> HIGH -> MEDIUM -> LOW
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        self.flags.sort(key=lambda f: severity_order.get(f.severity, 4))

        return AnomalyOutput(
            total_flags=len(self.flags),
            critical=c,
            high=h,
            medium=m,
            low=l,
            rules_skipped_missing_data=self.skipped_rules,
            flags=self.flags
        )

    def _eval_af001(self, year: int):
        # AF-001 — Revenue-Cash Divergence: Rev YoY > 15% AND OCF YoY < 0%
        rev_yoy = self._get_ratio(year, "revenue_yoy")
        ocf_c = self._get_raw(year, "operating_cash_flow")
        ocf_p = self._get_raw(year - 1, "operating_cash_flow")
        
        if rev_yoy is None or ocf_c is None or ocf_p is None:
            self.skipped_rules.append(f"AF-001 (revenue_yoy or operating_cash_flow missing, FY{year})")
            return
            
        ocf_yoy = ((ocf_c - ocf_p) / abs(ocf_p) * 100) if ocf_p != 0 else None
        
        if ocf_yoy is not None and rev_yoy > 15.0 and ocf_yoy < 0.0:
            self.flags.append(AnomalyFlag(
                flag_id="AF-001",
                severity="HIGH",
                category="Quality of Earnings",
                title="Revenue-Cash Divergence",
                description="Revenue is growing strongly (>15%) but operating cash flow is declining.",
                supporting_data={"revenue_growth": round(rev_yoy, 2), "ocf_growth": round(ocf_yoy, 2)}
            ))

    def _eval_af002(self, year: int):
        # AF-002 — Gross Margin Compression
        gm_trend = self.trends.get("gross_margin")
        if not gm_trend or gm_trend.data_years < 2:
            self.skipped_rules.append(f"AF-002 (gross_margin trend missing, FY{year})")
            return
            
        # Check single year 5+ pp drop
        is_sudden_drop = False
        for sc in gm_trend.sudden_changes:
            if sc.year == year and sc.classification == "SUDDEN_DETERIORATION" and sc.magnitude > 5.0:
                is_sudden_drop = True
                break
                
        # Check 3 consecutive years decline
        is_3yr_decline = False
        if gm_trend.data_years >= 4:
            years = sorted([int(y) for y in gm_trend.year_values.keys()])
            if year in years:
                idx = years.index(year)
                if idx >= 3:
                    y0, y1, y2, y3 = years[idx-3], years[idx-2], years[idx-1], years[idx]
                    v0 = gm_trend.year_values[str(y0)]
                    v1 = gm_trend.year_values[str(y1)]
                    v2 = gm_trend.year_values[str(y2)]
                    v3 = gm_trend.year_values[str(y3)]
                    if v3 < v2 < v1 < v0:
                        is_3yr_decline = True
                        
        if is_sudden_drop or is_3yr_decline:
            self.flags.append(AnomalyFlag(
                flag_id="AF-002",
                severity="HIGH" if is_sudden_drop else "MEDIUM",
                category="Profitability",
                title="Gross Margin Compression",
                description="Sustained or sudden significant decline in gross margin.",
                supporting_data={"sudden_drop": is_sudden_drop, "multi_year_decline": is_3yr_decline}
            ))

    def _eval_af003(self, year: int):
        # AF-003 — Debt Accumulation (Rapid Leverage Increase)
        # Debt/EBITDA > 1.5x in 2 years OR Net Debt/EBITDA > 2.0x in 2 years
        de_c = self._get_ratio(year, "debt_to_ebitda")
        de_p2 = self._get_ratio(year - 2, "debt_to_ebitda")
        nde_c = self._get_ratio(year, "net_debt_to_ebitda")
        nde_p2 = self._get_ratio(year - 2, "net_debt_to_ebitda")
        
        if (de_c is None or de_p2 is None) and (nde_c is None or nde_p2 is None):
            self.skipped_rules.append(f"AF-003 (leverage ratios missing, FY{year})")
            return
            
        triggered = False
        if de_c is not None and de_p2 is not None and de_p2 > 0:
            if (de_c / de_p2) > 1.5:
                triggered = True
        if nde_c is not None and nde_p2 is not None and nde_p2 > 0:
            if (nde_c / nde_p2) > 2.0:
                triggered = True
                
        if triggered:
            self.flags.append(AnomalyFlag(
                flag_id="AF-003",
                severity="HIGH",
                category="Solvency",
                title="Rapid Debt Accumulation",
                description="Leverage ratios have increased dangerously rapidly over a 2-year period.",
                supporting_data={"debt_to_ebitda_y0": de_p2, "debt_to_ebitda_y2": de_c}
            ))

    def _eval_af004(self, year: int):
        # AF-004 — Earnings Quality Warning (FCF Below Net Income) < 0.8 for 2+ consecutive years
        fcf_ni_c = self._get_ratio(year, "fcf_to_net_income")
        fcf_ni_p = self._get_ratio(year - 1, "fcf_to_net_income")
        
        if fcf_ni_c is None or fcf_ni_p is None:
            self.skipped_rules.append(f"AF-004 (fcf_to_net_income missing, FY{year})")
            return
            
        if fcf_ni_c < 0.8 and fcf_ni_p < 0.8:
            # Check 3 years for HIGH severity
            fcf_ni_p2 = self._get_ratio(year - 2, "fcf_to_net_income")
            severity = "HIGH" if fcf_ni_p2 is not None and fcf_ni_p2 < 0.8 else "MEDIUM"
            
            self.flags.append(AnomalyFlag(
                flag_id="AF-004",
                severity=severity,
                category="Quality of Earnings",
                title="FCF Consistently Below Net Income",
                description="Reported profits consistently exceed actual free cash flow generated.",
                supporting_data={"current": round(fcf_ni_c, 2), "prior": round(fcf_ni_p, 2)}
            ))

    def _eval_af005(self, year: int):
        # AF-005 — Interest Coverage Danger < 1.5x
        ic = self._get_ratio(year, "interest_coverage")
        if ic is None:
            self.skipped_rules.append(f"AF-005 (interest_coverage missing/NOT_APPLICABLE, FY{year})")
            return
            
        if ic < 1.5:
            self.flags.append(AnomalyFlag(
                flag_id="AF-005",
                severity="CRITICAL" if ic < 1.0 else "HIGH",
                category="Solvency",
                title="Interest Coverage Ratio Critically Low",
                description=f"Interest coverage has fallen to {round(ic, 2)}x.",
                supporting_data={"interest_coverage": round(ic, 2), "threshold": 1.5}
            ))

    def _eval_af006(self, year: int):
        # AF-006 — Current Ratio Below Safety Level < 1.0
        cr = self._get_ratio(year, "current_ratio")
        if cr is None:
            self.skipped_rules.append(f"AF-006 (current_ratio missing, FY{year})")
            return
            
        if cr < 1.0:
            self.flags.append(AnomalyFlag(
                flag_id="AF-006",
                severity="HIGH",
                category="Liquidity",
                title="Current Ratio Below 1.0",
                description="Short-term obligations exceed short-term assets.",
                supporting_data={"current_ratio": round(cr, 2)}
            ))

    def _eval_af007(self, year: int):
        # AF-007 — Goodwill Impairment Risk > 35%
        # Bug Fix: Agar goodwill naturally missing hai (jaise organic growth company me) to use 0 maan lenge, false skip nahi dikhayenge
        gw = self._get_raw(year, "goodwill") or 0
        ta = self._get_raw(year, "total_assets")
        gw_ta = self._safe_div(gw, ta)
        
        if gw_ta is None:
            self.skipped_rules.append(f"AF-007 (total_assets missing, FY{year})")
            return
            
        if gw_ta > 0.35:
            self.flags.append(AnomalyFlag(
                flag_id="AF-007",
                severity="MEDIUM",
                category="Balance Sheet Quality",
                title="High Goodwill Concentration",
                description=f"Goodwill is {round(gw_ta*100, 1)}% of total assets, increasing impairment risk.",
                supporting_data={"goodwill_to_assets_ratio": round(gw_ta, 3)}
            ))

    def _eval_af008(self, year: int):
        # AF-008 — CapEx Sudden Change > 30% relative AND > 2% absolute change
        # Bug Fix: CapEx zero hone par false skip hataya gaya, aur absolute > 0.02 condition add ki gayi taaki chhote changes par false alarm na baje
        cx_c = self._get_raw(year, "capital_expenditures") or 0
        rev_c = self._get_raw(year, "revenue")
        cx_p = self._get_raw(year - 1, "capital_expenditures") or 0
        rev_p = self._get_raw(year - 1, "revenue")
        
        cx_rev_c = self._safe_div(cx_c, rev_c)
        cx_rev_p = self._safe_div(cx_p, rev_p)
        
        if cx_rev_c is None or cx_rev_p is None:
            self.skipped_rules.append(f"AF-008 (revenue missing, FY{year})")
            return
            
        if cx_rev_p != 0 and abs((cx_rev_c - cx_rev_p) / cx_rev_p) > 0.30 and abs(cx_rev_c - cx_rev_p) > 0.02:
            # Check if accompanied by debt increase for MEDIUM
            ltd_c = self._get_raw(year, "long_term_debt") or 0
            ltd_p = self._get_raw(year - 1, "long_term_debt") or 0
            severity = "MEDIUM" if ltd_c > ltd_p else "LOW"
            
            self.flags.append(AnomalyFlag(
                flag_id="AF-008",
                severity=severity,
                category="Capital Allocation",
                title="CapEx Sudden Change",
                description="CapEx as a percentage of revenue changed dramatically year-over-year.",
                supporting_data={"capex_to_revenue_curr": round(cx_rev_c, 3), "capex_to_revenue_prev": round(cx_rev_p, 3)}
            ))

    def _eval_af009(self, year: int):
        # AF-009 — SG&A Overhead Inflation
        sga_c = self._get_raw(year, "selling_general_and_administrative_expense") or self._get_raw(year, "sga_expense")
        if sga_c is None:
            self.skipped_rules.append(f"AF-009 (SG&A missing, FY{year})")
            return
            
        rev_yoy_c = self._get_ratio(year, "revenue_yoy")
        rev_yoy_p = self._get_ratio(year - 1, "revenue_yoy")
        
        if rev_yoy_c is None or rev_yoy_p is None:
            self.skipped_rules.append(f"AF-009 (revenue_yoy missing, FY{year})")
            return
            
        # Check SG&A / Revenue increased 3+ consecutive years
        sga_rev_vals = []
        for y in range(year - 3, year + 1):
            sga = self._get_raw(y, "selling_general_and_administrative_expense") or self._get_raw(y, "sga_expense")
            rev = self._get_raw(y, "revenue")
            v = self._safe_div(sga, rev)
            if v is None:
                break
            sga_rev_vals.append(v)
            
        if len(sga_rev_vals) == 4:
            if sga_rev_vals[3] > sga_rev_vals[2] > sga_rev_vals[1] > sga_rev_vals[0]:
                if rev_yoy_c < rev_yoy_p:
                    self.flags.append(AnomalyFlag(
                        flag_id="AF-009",
                        severity="MEDIUM",
                        category="Operating Efficiency",
                        title="SG&A Overhead Inflation",
                        description="SG&A as a percentage of revenue is rising while revenue growth is decelerating.",
                        supporting_data={"revenue_yoy_curr": round(rev_yoy_c, 2), "revenue_yoy_prev": round(rev_yoy_p, 2)}
                    ))
        else:
            self.skipped_rules.append(f"AF-009 (insufficient historical SG&A, FY{year})")

    def _eval_af010(self, year: int):
        # AF-010 — High Accruals (TATA) > 5%
        ni = self._get_raw(year, "net_income")
        ocf = self._get_raw(year, "operating_cash_flow")
        ta = self._get_raw(year, "total_assets")
        
        tata = None
        if ni is not None and ocf is not None and ta is not None and ta != 0:
            tata = (ni - ocf) / ta
            
        if tata is None:
            self.skipped_rules.append(f"AF-010 (TATA components missing, FY{year})")
            return
            
        if tata > 0.05:
            self.flags.append(AnomalyFlag(
                flag_id="AF-010",
                severity="MEDIUM",
                category="Quality of Earnings",
                title="High Accruals Ratio",
                description="A large portion of net income is not backed by cash.",
                supporting_data={"tata": round(tata, 3)}
            ))

    def _eval_af011(self, year: int):
        # AF-011 — Non-Operating Income Dependency
        ni_c = self._get_raw(year, "net_income")
        op_c = self._get_raw(year, "operating_income")
        ni_p = self._get_raw(year - 1, "net_income")
        op_p = self._get_raw(year - 1, "operating_income")
        
        if ni_c is None or op_c is None or ni_p is None or op_p is None:
            self.skipped_rules.append(f"AF-011 (Net Income or Operating Income missing, FY{year})")
            return
            
        if ni_c <= 0 or ni_p <= 0:
            self.skipped_rules.append(f"AF-011 (Net Income <= 0, skipped due to meaningless ratio, FY{year})")
            return
            
        non_op_c = ni_c - op_c
        non_op_p = ni_p - op_p
        
        if (non_op_c / ni_c) > 0.25 and (non_op_p / ni_p) < 0.10:
            self.flags.append(AnomalyFlag(
                flag_id="AF-011",
                severity="MEDIUM",
                category="Quality of Earnings",
                title="Non-Operating Income Dependency",
                description="Sudden large reliance on non-operating income to drive net income.",
                supporting_data={"non_op_ratio_curr": round(non_op_c/ni_c, 3), "non_op_ratio_prev": round(non_op_p/ni_p, 3)}
            ))

    def _eval_af012(self, year: int):
        # AF-012 — Effective Tax Rate Anomaly
        te_c = self._get_raw(year, "income_tax_expense")
        pi_c = self._get_raw(year, "income_before_tax")
        te_p = self._get_raw(year - 1, "income_tax_expense")
        pi_p = self._get_raw(year - 1, "income_before_tax")
        
        etr_c = self._safe_div(te_c, pi_c)
        etr_p = self._safe_div(te_p, pi_p)
        
        if etr_c is None or etr_p is None:
            self.skipped_rules.append(f"AF-012 (tax components missing, FY{year})")
            return
            
        if abs(etr_c - etr_p) > 0.10:
            self.flags.append(AnomalyFlag(
                flag_id="AF-012",
                severity="MEDIUM",
                category="Quality of Earnings",
                title="Effective Tax Rate Anomaly",
                description="Effective tax rate changed by more than 10 percentage points.",
                supporting_data={"tax_rate_curr": round(etr_c, 3), "tax_rate_prev": round(etr_p, 3)}
            ))

    def _eval_af013(self, year: int):
        # AF-013 — Receivables Growth Outpacing Revenue
        if not self.fraud_data or not self.fraud_data.beneish_scores:
            self.skipped_rules.append(f"AF-013 (Beneish scores missing, FY{year})")
            return
            
        # Find Beneish score ending in current year
        b_score = None
        for s in self.fraud_data.beneish_scores:
            if s.fiscal_year_pair and str(year) in s.fiscal_year_pair:
                b_score = s
                break
                
        if not b_score or not b_score.variables or "DSRI" not in b_score.variables:
            self.skipped_rules.append(f"AF-013 (DSRI not available in Beneish, FY{year})")
            return
            
        dsri_val = b_score.variables["DSRI"].value
        if dsri_val is not None and dsri_val > 1.31:
            self.flags.append(AnomalyFlag(
                flag_id="AF-013",
                severity="MEDIUM",
                category="Revenue Quality",
                title="Receivables Growth Outpacing Revenue",
                description="DSRI > 1.31 indicates accounts receivable growing much faster than sales.",
                supporting_data={"DSRI": round(dsri_val, 3)}
            ))

    def _eval_af014(self, year: int):
        # AF-014 — Inventory Build-up
        # Bug Fix: Agar company software/services type ki hai aur unki inventory zero/missing hai, to ise silently ignore kiya jayega
        inv_c = self._get_raw(year, "inventory") or 0
        inv_p = self._get_raw(year - 1, "inventory") or 0
        rev_yoy = self._get_ratio(year, "revenue_yoy")
        
        if rev_yoy is None:
            self.skipped_rules.append(f"AF-014 (revenue_yoy missing, FY{year})")
            return
            
        if inv_p == 0:
            return
            
        inv_yoy = ((inv_c - inv_p) / inv_p) * 100
        
        if inv_yoy > (rev_yoy + 20.0):
            self.flags.append(AnomalyFlag(
                flag_id="AF-014",
                severity="MEDIUM",
                category="Operational Efficiency",
                title="Inventory Build-up",
                description="Inventory is growing significantly faster than revenue.",
                supporting_data={"inventory_growth": round(inv_yoy, 2), "revenue_growth": round(rev_yoy, 2)}
            ))

    def _eval_af015(self, year: int):
        # AF-015 — Declining FCF Despite Positive Net Income
        ni_c = self._get_raw(year, "net_income")
        ni_yoy = self._get_ratio(year, "net_income_yoy")
        fcf_c = self._get_raw(year, "free_cash_flow")
        fcf_p = self._get_raw(year - 1, "free_cash_flow")
        
        if ni_c is None or ni_yoy is None or fcf_c is None or fcf_p is None:
            self.skipped_rules.append(f"AF-015 (NI or FCF missing, FY{year})")
            return
            
        if ni_c > 0 and ni_yoy > 0:
            is_fcf_declining = fcf_c < 0 or (fcf_p != 0 and ((fcf_c - fcf_p)/abs(fcf_p)) < -0.20)
            if is_fcf_declining:
                self.flags.append(AnomalyFlag(
                    flag_id="AF-015",
                    severity="HIGH",
                    category="Quality of Earnings",
                    title="Declining FCF Despite Positive Net Income",
                    description="Net income is growing but free cash flow is negative or significantly declining.",
                    supporting_data={"net_income": ni_c, "fcf_curr": fcf_c, "fcf_prev": fcf_p}
                ))
