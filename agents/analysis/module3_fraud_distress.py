"""
Module:  fraud_distress_engine.py
Agent:   Analysis Agent
Purpose: Computes Beneish M-Score and Altman Z-Score models.
         # Is module ka kaam company ke numbers ko analyze karke Fraud (hera-pheri) aur 
         # Distress (diwaliya ya bankruptcy) ke risks detect karna hai.
"""

from typing import Any
from schemas.pydantic_models import (
    FraudDistressOutput, BeneishScore, AltmanScore, BeneishVariable
)

class FraudDistressEngine:
    def __init__(self, financial_data_by_year: dict[int, dict[str, Any]], sic_code: str, data_depth_mode: str, industry_name: str = "Unknown"):
        # Yahan input data ko store karte hain jisme raw financials, industry code (SIC) aur depth mode aata hai
        self.data_by_year = financial_data_by_year
        self.sic_code = sic_code
        self.industry_name = industry_name
        self.data_depth_mode = data_depth_mode
        # Saalo ko oldest se newest me sort kar rahe hain kyunki calculations ko previous year data chahiye
        self.available_years = sorted(self.data_by_year.keys())

    def run(self) -> FraudDistressOutput:
        # Ye main function hai jo dono models (Beneish aur Altman) ko call karke result return karta hai
        beneish_scores = self._compute_beneish()
        altman_scores = self._compute_altman()
        return FraudDistressOutput(
            beneish_scores=beneish_scores,
            altman_scores=altman_scores
        )

    def _safe_div(self, num: float | None, den: float | None) -> float | None:
        if num is None or den is None or den == 0:
            return None
        return num / den

    def _compute_beneish(self) -> list[BeneishScore]:
        # Beneish M-Score nikalne ke liye kam se kam 2 lagatar (consecutive) saalo ka data hona zaroori hai
        if self.data_depth_mode == "MINIMAL" or len(self.available_years) < 2:
            return [BeneishScore(
                verdict="NOT_COMPUTABLE",
                reason="At least 2 consecutive fiscal years required."
            )]

        results = []
        for i in range(1, len(self.available_years)):
            prev_year = self.available_years[i-1]
            curr_year = self.available_years[i]
            
            if curr_year != prev_year + 1:
                # Need strictly consecutive years
                continue
                
            prev = self.data_by_year[prev_year]
            curr = self.data_by_year[curr_year]
            
            score = self._compute_beneish_pair(prev, curr, prev_year, curr_year)
            results.append(score)
            
        if not results:
            return [BeneishScore(
                verdict="NOT_COMPUTABLE",
                reason="No consecutive fiscal years available."
            )]
        
        # Multi-year persistence check (research best practice):
        # A company that is persistently LIKELY_MANIPULATOR for 3+ consecutive years
        # is a stronger signal than a single year anomaly.
        # We tag each score with persistence context.
        likely_count = sum(1 for r in results if r.verdict == "LIKELY_MANIPULATOR")
        if likely_count >= 3:
            persistence_note = f"PERSISTENT: LIKELY_MANIPULATOR verdict for {likely_count}/{len(results)} year-pairs. Sustained aggressive accounting signal."
        elif likely_count == 2:
            persistence_note = f"RECURRING: LIKELY_MANIPULATOR for {likely_count}/{len(results)} year-pairs. Monitor closely."
        else:
            persistence_note = None
        
        if persistence_note:
            # Annotate the latest result with persistence context
            latest = results[-1]
            existing_note = latest.note or ""
            results[-1] = BeneishScore(
                model=latest.model,
                fiscal_year_pair=latest.fiscal_year_pair,
                variables=latest.variables,
                m_score=latest.m_score,
                verdict=latest.verdict,
                individual_flags=latest.individual_flags,
                missing_variables=latest.missing_variables,
                reason=latest.reason,
                note=f"{existing_note} | {persistence_note}"
            )
            
        return results

    def _compute_beneish_pair(self, prev: dict, curr: dict, prev_year: int, curr_year: int) -> BeneishScore:
        # Variables setup: Current year (_c) aur Previous year (_p) ke saare important numbers variables me daal rahe hain
        # Ye saare variables aage chal kar 8 alag-alag indices banayenge
        rev_c = curr.get("revenue")
        rev_p = prev.get("revenue")
        ar_c = curr.get("accounts_receivable")
        ar_p = prev.get("accounts_receivable")
        gp_c = curr.get("gross_profit")
        gp_p = prev.get("gross_profit")
        ca_c = curr.get("current_assets")
        ca_p = prev.get("current_assets")
        ppe_c = curr.get("ppe_net")
        ppe_p = prev.get("ppe_net")
        ta_c = curr.get("total_assets")
        ta_p = prev.get("total_assets")
        dep_c = curr.get("depreciation_and_amortization")
        dep_p = prev.get("depreciation_and_amortization")
        sga_c = curr.get("selling_general_and_administrative_expense") or curr.get("sga_expense")
        sga_p = prev.get("selling_general_and_administrative_expense") or prev.get("sga_expense")
        ltd_c = curr.get("long_term_debt")
        ltd_p = prev.get("long_term_debt")
        cl_c = curr.get("current_liabilities")
        cl_p = prev.get("current_liabilities")
        ni_c = curr.get("net_income")
        ocf_c = curr.get("operating_cash_flow")
        
        missing = []
        flags = []
        variables = {}

        def _guard_ratio(num, den):
            if num is None or den is None or den == 0:
                return None
            return num / den
            
        # 1. DSRI — Days' Sales in Receivables Index
        # Measures if accounts receivable are growing faster than revenues.
        # A large increase (>1.31) suggests revenues may be inflated or collections declining.
        t_dsri = 1.31
        ar_rev_c = _guard_ratio(ar_c, rev_c)
        ar_rev_p = _guard_ratio(ar_p, rev_p)
        dsri = _guard_ratio(ar_rev_c, ar_rev_p)
        if dsri is None: missing.append("DSRI")
        elif dsri > t_dsri: flags.append("DSRI above threshold")
        variables["DSRI"] = BeneishVariable(value=dsri, threshold=t_dsri, flag=(dsri > t_dsri) if dsri is not None else False)

        # 2. GMI — Gross Margin Index
        # Measures if gross margins are deteriorating (>1.19 = worse margins = manipulation pressure).
        t_gmi = 1.19
        gm_c = _guard_ratio(gp_c, rev_c)
        gm_p = _guard_ratio(gp_p, rev_p)
        gmi = _guard_ratio(gm_p, gm_c)
        if gm_c == 0: gmi = None
        if gmi is None: missing.append("GMI")
        elif gmi > t_gmi: flags.append("GMI above threshold")
        variables["GMI"] = BeneishVariable(value=gmi, threshold=t_gmi, flag=(gmi > t_gmi) if gmi is not None else False)

        # 3. AQI — Asset Quality Index
        # Measures proportion of non-current/non-PPE assets. An increase suggests cost capitalization.
        t_aqi = 1.25
        if ca_c is not None and ppe_c is not None and ta_c is not None and ta_c != 0:
            aq_c = 1 - ((ca_c + ppe_c) / ta_c)
        else:
            aq_c = None
            
        if ca_p is not None and ppe_p is not None and ta_p is not None and ta_p != 0:
            aq_p = 1 - ((ca_p + ppe_p) / ta_p)
        else:
            aq_p = None
            
        aqi = _guard_ratio(aq_c, aq_p)
        if aqi is None: missing.append("AQI")
        elif aqi > t_aqi: flags.append("AQI above threshold")
        variables["AQI"] = BeneishVariable(value=aqi, threshold=t_aqi, flag=(aqi > t_aqi) if aqi is not None else False)

        # 4. SGI — Sales Growth Index
        # Measures revenue growth rate. The 1.607 value is the MEAN SGI of manipulators in Beneish's original
        # 1999 sample — NOT a hard fraud threshold. Non-manipulators averaged ~1.134.
        # IMPORTANT: For hypergrowth companies (SGI > 2.0), this variable alone is NOT indicative of manipulation.
        # It must be corroborated by high TATA (non-cash earnings) or DSRI (receivables inflation).
        t_sgi = 1.607
        sgi = _guard_ratio(rev_c, rev_p)
        if sgi is None: missing.append("SGI")
        elif sgi > t_sgi: flags.append("SGI above threshold")
        variables["SGI"] = BeneishVariable(value=sgi, threshold=t_sgi, flag=(sgi > t_sgi) if sgi is not None else False)

        # 5. DEPI — Depreciation Index
        # Measures if the firm has slowed its depreciation rate (income-increasing policy shift).
        t_depi = 1.00
        if dep_p is not None and ppe_p is not None and (ppe_p + dep_p) != 0:
            dep_rate_p = dep_p / (ppe_p + dep_p)
        else:
            dep_rate_p = None
            
        if dep_c is not None and ppe_c is not None and (ppe_c + dep_c) != 0:
            dep_rate_c = dep_c / (ppe_c + dep_c)
        else:
            dep_rate_c = None
            
        depi = _guard_ratio(dep_rate_p, dep_rate_c)
        if depi is None: missing.append("DEPI")
        elif depi > t_depi: flags.append("DEPI above threshold")
        variables["DEPI"] = BeneishVariable(value=depi, threshold=t_depi, flag=(depi > t_depi) if depi is not None else False)

        # 6. SGAI — Sales, General & Administrative Expenses Index
        # Measures disproportionate overhead increases relative to revenue growth.
        t_sgai = 1.00
        sga_rev_c = _guard_ratio(sga_c, rev_c)
        sga_rev_p = _guard_ratio(sga_p, rev_p)
        sgai = _guard_ratio(sga_rev_c, sga_rev_p)
        if sgai is None: missing.append("SGAI")
        elif sgai > t_sgai: flags.append("SGAI above threshold")
        variables["SGAI"] = BeneishVariable(value=sgai, threshold=t_sgai, flag=(sgai > t_sgai) if sgai is not None else False)

        # 7. LVGI — Leverage Index
        # Measures if total leverage (LTD + current liabilities) relative to assets is increasing.
        t_lvgi = 1.00
        if ltd_c is not None and cl_c is not None and ta_c is not None and ta_c != 0:
            lev_c = (ltd_c + cl_c) / ta_c
        else:
            lev_c = None
            
        if ltd_p is not None and cl_p is not None and ta_p is not None and ta_p != 0:
            lev_p = (ltd_p + cl_p) / ta_p
        else:
            lev_p = None
            
        lvgi = _guard_ratio(lev_c, lev_p)
        if lvgi is None: missing.append("LVGI")
        elif lvgi > t_lvgi: flags.append("LVGI above threshold")
        variables["LVGI"] = BeneishVariable(value=lvgi, threshold=t_lvgi, flag=(lvgi > t_lvgi) if lvgi is not None else False)

        # 8. TATA — Total Accruals to Total Assets
        # Correct formula per Beneish 1999: (Net Income - Operating Cash Flow) / Total Assets.
        # This isolates the non-cash component of earnings. A high positive TATA means earnings
        # are NOT backed by cash — the single most important red flag in the model.
        # A NEGATIVE TATA (CFO > Net Income) is a strong anti-manipulation signal.
        t_tata = 0.05
        if ni_c is not None and ocf_c is not None and ta_c is not None and ta_c != 0:
            tata = (ni_c - ocf_c) / ta_c
        else:
            tata = None
            
        if tata is None: missing.append("TATA")
        elif tata > t_tata: flags.append("TATA above threshold")
        variables["TATA"] = BeneishVariable(value=tata, threshold=t_tata, flag=(tata > t_tata) if tata is not None else False)

        # Compute M-Score using fallback means if necessary (1.0 for indices, 0.0 for TATA)
        # Agar koi data missing hai to us metric ko neutral value de rahe hain taaki formula crash na ho
        v_dsri = dsri if dsri is not None else 1.0
        v_gmi = gmi if gmi is not None else 1.0
        v_aqi = aqi if aqi is not None else 1.0
        v_sgi = sgi if sgi is not None else 1.0
        v_depi = depi if depi is not None else 1.0
        v_sgai = sgai if sgai is not None else 1.0
        v_lvgi = lvgi if lvgi is not None else 1.0
        v_tata = tata if tata is not None else 0.0

        # Final formula from Beneish (1999) — 8-variable version
        m_score = -4.840 + (0.920 * v_dsri) + (0.528 * v_gmi) + (0.404 * v_aqi) + (0.892 * v_sgi) + (0.115 * v_depi) - (0.172 * v_sgai) + (4.679 * v_tata) - (0.327 * v_lvgi)
        m_score = round(m_score, 4)
        
        # Research-backed tiered threshold system (Beneish 1999):
        # Primary warning threshold: -2.22 (8-variable model calibration)
        # High risk threshold: -1.78 (higher sensitivity — fewer false negatives)
        # Grey zone between -2.22 and -1.78 is ambiguous and requires qualitative overlay.
        if m_score > -1.78:
            verdict = "LIKELY_MANIPULATOR"
        elif m_score > -2.22:
            verdict = "GREY_ZONE"
        else:
            verdict = "UNLIKELY_MANIPULATOR"

        # ── Hypergrowth False-Positive Detection ─────────────────────────────
        # Research finding: The model systematically misclassifies legitimate hypergrowth
        # companies (NVDA, AMZN, TSLA) as LIKELY_MANIPULATOR due to their high SGI.
        # Key insight from Beneish literature: If SGI is the primary driver AND
        # TATA is negative (CFO > Net Income = cash-backed earnings), the flag is
        # very likely a false positive caused by genuine revenue acceleration.
        hypergrowth_fp_detected = False
        hypergrowth_note = ""
        if verdict == "LIKELY_MANIPULATOR" and sgi is not None and tata is not None:
            sgi_only_driver = sgi > t_sgi and tata <= t_tata  # SGI flagged, TATA clean
            cash_backed_earnings = tata < 0  # CFO > Net Income = STRONG anti-manipulation
            if sgi_only_driver and cash_backed_earnings:
                hypergrowth_fp_detected = True
                hypergrowth_note = (
                    f" | HYPERGROWTH FALSE-POSITIVE WARNING: SGI={sgi:.3f} (revenue acceleration) "
                    f"is the primary M-Score driver, but TATA={tata:.4f} < 0 confirms earnings "
                    f"are fully cash-backed (CFO exceeds Net Income). Per Beneish (1999) literature, "
                    f"this pattern is characteristic of legitimate hypergrowth, not manipulation. "
                    f"Qualitative filing review is required before escalating this flag."
                )

        note = "All 8 variables computed. Score is reliable."
        if missing:
            note = f"Score is an approximation. Missing variables substituted with research means: {', '.join(missing)}."
        if hypergrowth_note:
            note += hypergrowth_note

        return BeneishScore(
            fiscal_year_pair=f"{prev_year} to {curr_year}",
            variables=variables,
            m_score=m_score,
            verdict=verdict,
            individual_flags=flags,
            missing_variables=missing,
            note=note
        )

    def _compute_altman(self) -> list[AltmanScore]:
        # Altman Z-Score: Company ka bankruptcy ya diwaliya hone ka risk check karta hai.
        try:
            sic = int(self.sic_code)
        except (ValueError, TypeError):
            return [AltmanScore(
                verdict="NOT_APPLICABLE",
                reason="Invalid or missing SIC code."
            )]
            
        # Financial sector (Banks/Insurance) ke liye Altman formula sahi kaam nahi karta, isliye exclude karte hain
        if 6000 <= sic <= 6799:
            return [AltmanScore(
                verdict="NOT_APPLICABLE",
                reason=f"Altman Z-Score is not valid for financial-sector companies (SIC 6000-6799). This company's SIC code is {self.sic_code} ({self.industry_name}). Financial institutions carry structurally different leverage than the manufacturing and general-industry companies the model was calibrated on."
            )]

        # Check kar rahe hain ki company Manufacturing me aati hai ya nahi (Manufacturing aur Non-Mfg ke formulas alag hote hain)
        is_mfg = 2000 <= sic <= 3999
        results = []

        for year in self.available_years:
            curr = self.data_by_year[year]
            
            ca = curr.get("current_assets")
            cl = curr.get("current_liabilities")
            ta = curr.get("total_assets")
            re = curr.get("retained_earnings")
            op_inc = curr.get("operating_income")
            tl = curr.get("total_liabilities")
            mcap = curr.get("market_cap")
            te = curr.get("total_equity")
            rev = curr.get("revenue")
            
            if ta is None or ta == 0:
                results.append(AltmanScore(
                    fiscal_year=year,
                    verdict="NOT_COMPUTABLE",
                    reason="Total Assets missing or zero."
                ))
                continue
                
            x1 = self._safe_div((ca - cl) if ca is not None and cl is not None else None, ta)
            x2 = self._safe_div(re, ta)
            x3 = self._safe_div(op_inc, ta)
            
            # Market Cap na hone par (jaise private company), Book Value (te = total equity) ko fallback ke roop me use kar rahe hain
            x4_num = mcap if mcap is not None else te
            x4 = self._safe_div(x4_num, tl)
            mcap_version = "MARKET_VALUE" if mcap is not None else "BOOK_VALUE"
            
            if tl == 0:
                x4 = None # Guard

            vars_dict = {
                "X1_working_capital_to_assets": round(x1, 4) if x1 is not None else None,
                "X2_retained_earnings_to_assets": round(x2, 4) if x2 is not None else None,
                "X3_ebit_to_assets": round(x3, 4) if x3 is not None else None,
                "X4_market_cap_to_liabilities": round(x4, 4) if x4 is not None else None
            }
            
            if x1 is None or x2 is None or x3 is None or x4 is None:
                results.append(AltmanScore(
                    fiscal_year=year,
                    verdict="NOT_COMPUTABLE",
                    reason="One or more required variables are missing."
                ))
                continue

            if is_mfg:
                # Manufacturing company ka 5-variable Z-Score formula
                x5 = self._safe_div(rev, ta)
                vars_dict["X5_sales_to_assets"] = round(x5, 4) if x5 is not None else None
                if x5 is None:
                    results.append(AltmanScore(
                        fiscal_year=year,
                        verdict="NOT_COMPUTABLE",
                        reason="X5 required for manufacturing version but revenue is missing."
                    ))
                    continue
                    
                z = (1.2 * x1) + (1.4 * x2) + (3.3 * x3) + (0.6 * x4) + (1.0 * x5)
                z = round(z, 4)
                
                # Z-Score ke standard risk zones
                if z > 2.99: verdict = "SAFE_ZONE"
                elif 1.81 <= z <= 2.99: verdict = "GREY_ZONE"
                else: verdict = "DISTRESS_ZONE"
                
                results.append(AltmanScore(
                    version="Z-Score (Manufacturing)",
                    fiscal_year=year,
                    variables=vars_dict,
                    z_score=z,
                    verdict=verdict,
                    market_cap_version=mcap_version,
                    note=f"Manufacturing formula applied (SIC code {self.sic_code})."
                ))
            else:
                # Non-Manufacturing (Service/Tech) ke liye 4-variable Z''-Score (Z double prime) formula
                z_prime = (6.56 * x1) + (3.26 * x2) + (6.72 * x3) + (1.05 * x4)
                z_prime = round(z_prime, 4)
                
                # Z''-Score ke standard risk zones
                if z_prime > 2.60: verdict = "SAFE_ZONE"
                elif 1.10 <= z_prime <= 2.60: verdict = "GREY_ZONE"
                else: verdict = "DISTRESS_ZONE"
                
                results.append(AltmanScore(
                    version="Z-Prime (Non-manufacturing)",
                    fiscal_year=year,
                    variables=vars_dict,
                    z_score=z_prime,
                    verdict=verdict,
                    market_cap_version=mcap_version,
                    note=f"Non-manufacturing formula applied (SIC code {self.sic_code})."
                ))

        if not results:
             results.append(AltmanScore(
                 verdict="NOT_COMPUTABLE",
                 reason="No valid fiscal years to compute."
             ))
             
        return results
