"""
Module:  ratio_engine.py
Agent:   Analysis Agent
Purpose: Computes 36 financial ratios per year using deterministic formulas and
         Universal Denominator Guard Pattern.
         # Is module ka main kaam Ingestion Agent se aaye raw financial data ko process karke 
         # har saal ke liye 36 key financial ratios (Profitability, Liquidity, Debt, etc.) calculate karna hai.
Inputs:  financial_data_by_year (har saal ka raw data), data_depth_mode (analysis kitni deep karni hai), n_years (kitne saal ka data hai)
Outputs: List of RatioRecord objects (jo baad me JSON me save hote hain).
"""

import math
from typing import Any
from schemas.pydantic_models import RatioRecord


class RatioEngine:
    def __init__(
        self,
        financial_data_by_year: dict[int, dict[str, Any]],
        data_depth_mode: str,
        n_years: int
    ):
        # Yahan hum input data ko class variables me save kar rahe hain taaki baaki functions ise use kar sakein.
        self.data_by_year = financial_data_by_year
        self.data_depth_mode = data_depth_mode
        self.n_years = n_years
        self.results: list[RatioRecord] = []

        
        # Sort years to ensure oldest to newest processing (Purane saal se naye saal ki taraf sort kar rahe hain taaki YoY growth sahi nikle)
        self.available_years = sorted(self.data_by_year.keys())

    def run(self) -> list[RatioRecord]:
        # Har available year ke liye loop chalayenge
        for year in self.available_years:
            curr_data = self.data_by_year[year]
            prior_data = self.data_by_year.get(year - 1)
            
            # Alag-alag categories ke ratios calculate karne ke functions call ho rahe hain
            self._compute_profitability(curr_data, prior_data, year)
            self._compute_liquidity(curr_data, year)
            self._compute_leverage_solvency(curr_data, year)
            self._compute_efficiency(curr_data, prior_data, year)
            self._compute_cash_flow_quality(curr_data, year)
            self._compute_growth(curr_data, prior_data, year)
            self._compute_valuation(curr_data, year)

        # Aakhir me Multi-year growth (CAGR) nikalne ka function call hota hai
        self._compute_cagr()
        
        return self.results

    def _guard(self, numerator: float | None, denominator: float | None, 
               ratio_name: str, 
               specific_zero_reason: str = None, 
               specific_negative_reason: str = None, 
               is_percentage: bool = False,
               meaningless_if_negative: bool = False,
               numerator_name: str = "Numerator",
               denominator_name: str = "Denominator") -> tuple[float | None, str, str | None]:
        """Universal Denominator Guard Pattern (Fix A-2).
        Ye function ensure karta hai ki 'Divide by Zero' errors na aayein, aur data missing hone par properly handle kare.
        Sath hi ye check karta hai ki koi negative value se math error na ho.
        """
        # Agar denominator (jaise Revenue ya Assets) missing hai, to ratio calculate nahi ho sakta
        if denominator is None:
            return None, "MISSING", f"{denominator_name} not available"
        # Agar denominator exactly 0 hai, to divide by zero error se bachne ke liye NOT_APPLICABLE return karte hain
        if denominator == 0:
            reason = specific_zero_reason or f"{denominator_name} is exactly zero"
            return None, "NOT_APPLICABLE", reason
        if denominator < 0 and meaningless_if_negative:
            reason = specific_negative_reason or f"{denominator_name} is negative; {ratio_name} is not meaningful"
            return None, "NOT_MEANINGFUL", reason
            
        if numerator is None:
            return None, "MISSING", f"{numerator_name} not available"
            
        value = numerator / denominator
        if is_percentage:
            value *= 100
            
        status = "COMPUTED"
        if is_percentage and abs(value) > 10000:
            status = "EXTREME_VALUE"
        elif not is_percentage and abs(value) > 1000:
            status = "EXTREME_VALUE"
            
        return round(value, 4), status, None

    def _add_record(self, ratio_name: str, year: int, value: float | None, unit: str, 
                    formula: str, inputs: dict[str, float | None], status: str, reason: str | None = None):
        self.results.append(RatioRecord(
            ratio_name=ratio_name,
            fiscal_year=year,
            value=value,
            unit=unit,
            formula=formula,
            inputs_used=inputs,
            status=status,
            reason=reason
        ))

    def _compute_profitability(self, curr: dict, prior: dict | None, year: int):
        rev = curr.get("revenue")
        gp = curr.get("gross_profit")
        op_inc = curr.get("operating_income")
        ni = curr.get("net_income")
        ebitda = curr.get("ebitda")
        assets = curr.get("total_assets")
        equity = curr.get("total_equity")
        lt_debt = curr.get("long_term_debt")
        tax_exp = curr.get("income_tax_expense")
        ebt = curr.get("income_before_tax")
        
        # 1. Gross Margin
        val, stat, res = self._guard(gp, rev, "Gross Margin", is_percentage=True, numerator_name="gross_profit", denominator_name="revenue")
        self._add_record("gross_margin", year, val, "percent", "(Gross Profit / Revenue) * 100", {"gross_profit": gp, "revenue": rev}, stat, res)

        # 2. Operating Margin
        val, stat, res = self._guard(op_inc, rev, "Operating Margin", is_percentage=True, numerator_name="operating_income", denominator_name="revenue")
        self._add_record("operating_margin", year, val, "percent", "(Operating Income / Revenue) * 100", {"operating_income": op_inc, "revenue": rev}, stat, res)

        # 3. Net Profit Margin
        val, stat, res = self._guard(ni, rev, "Net Profit Margin", is_percentage=True, numerator_name="net_income", denominator_name="revenue")
        self._add_record("net_profit_margin", year, val, "percent", "(Net Income / Revenue) * 100", {"net_income": ni, "revenue": rev}, stat, res)

        # 4. EBITDA Margin
        val, stat, res = self._guard(ebitda, rev, "EBITDA Margin", is_percentage=True, numerator_name="ebitda", denominator_name="revenue")
        self._add_record("ebitda_margin", year, val, "percent", "(EBITDA / Revenue) * 100", {"ebitda": ebitda, "revenue": rev}, stat, res)

        # 5. ROA
        avg_assets = assets
        if prior and prior.get("total_assets") is not None and assets is not None:
            avg_assets = (assets + prior["total_assets"]) / 2
            
        val, stat, res = self._guard(ni, avg_assets, "ROA", is_percentage=True, numerator_name="net_income", denominator_name="average_assets")
        self._add_record("roa", year, val, "percent", "(Net Income / Average Assets) * 100", {"net_income": ni, "average_assets": avg_assets}, stat, res)

        # 6. ROE
        avg_equity = equity
        if prior and prior.get("total_equity") is not None and equity is not None:
            avg_equity = (equity + prior["total_equity"]) / 2
            
        val, stat, res = self._guard(ni, avg_equity, "ROE", is_percentage=True, meaningless_if_negative=True, 
                                     specific_negative_reason="Total Equity is negative; ROE is not economically meaningful with a negative equity base.",
                                     numerator_name="net_income", denominator_name="average_equity")
        self._add_record("roe", year, val, "percent", "(Net Income / Average Equity) * 100", {"net_income": ni, "average_equity": avg_equity}, stat, res)

        # 7. ROIC
        # Bug Fix: Agar long_term_debt missing hai (0 nahi diya gaya), to use 0 maan lenge (taki debt-free company ka ROIC nikal sake)
        inv_cap = (equity + (lt_debt or 0)) if equity is not None else None
        val, stat, res = self._guard(op_inc, inv_cap, "ROIC", is_percentage=True, meaningless_if_negative=True,
                                     numerator_name="operating_income", denominator_name="invested_capital")
        self._add_record("roic", year, val, "percent", "(Operating Income / Invested Capital) * 100", {"operating_income": op_inc, "invested_capital": inv_cap}, stat, res)

        # 8. Effective Tax Rate
        val, stat, res = self._guard(tax_exp, ebt, "Effective Tax Rate", is_percentage=True, numerator_name="income_tax_expense", denominator_name="income_before_tax")
        self._add_record("effective_tax_rate", year, val, "percent", "(Income Tax Expense / Income Before Tax) * 100", {"income_tax_expense": tax_exp, "income_before_tax": ebt}, stat, res)

    def _compute_liquidity(self, curr: dict, year: int):
        ca = curr.get("current_assets")
        cl = curr.get("current_liabilities")
        inv = curr.get("inventory")
        cash = curr.get("cash_and_equivalents")

        # 9. Current Ratio
        val, stat, res = self._guard(ca, cl, "Current Ratio", numerator_name="current_assets", denominator_name="current_liabilities")
        self._add_record("current_ratio", year, val, "multiple", "Current Assets / Current Liabilities", {"current_assets": ca, "current_liabilities": cl}, stat, res)

        # 10. Quick Ratio
        # Note: Agar inventory missing (None) hai, to `inv or 0` karke 0 subtract hota hai, matlab software/service company ke liye Quick Assets = Current Assets ho jayega.
        quick_assets = (ca - (inv or 0)) if ca is not None else None
        val, stat, res = self._guard(quick_assets, cl, "Quick Ratio", numerator_name="quick_assets", denominator_name="current_liabilities")
        self._add_record("quick_ratio", year, val, "multiple", "(Current Assets - Inventory) / Current Liabilities", {"quick_assets": quick_assets, "current_liabilities": cl}, stat, res)

        # 11. Cash Ratio
        val, stat, res = self._guard(cash, cl, "Cash Ratio", numerator_name="cash", denominator_name="current_liabilities")
        self._add_record("cash_ratio", year, val, "multiple", "Cash / Current Liabilities", {"cash": cash, "current_liabilities": cl}, stat, res)

    def _compute_leverage_solvency(self, curr: dict, year: int):
        tl = curr.get("total_liabilities")
        eq = curr.get("total_equity")
        lt_debt = curr.get("long_term_debt")
        ebitda = curr.get("ebitda")
        st_debt = curr.get("short_term_debt", 0) or 0
        cash = curr.get("cash_and_equivalents", 0) or 0
        op_inc = curr.get("operating_income")
        int_exp = curr.get("interest_expense")
        assets = curr.get("total_assets")

        # 12. Debt-to-Equity
        val, stat, res = self._guard(tl, eq, "Debt-to-Equity", meaningless_if_negative=True,
                                     specific_negative_reason="Total Equity is negative; Debt/Equity is not meaningful.",
                                     numerator_name="total_liabilities", denominator_name="total_equity")
        self._add_record("debt_to_equity", year, val, "multiple", "Total Liabilities / Total Equity", {"total_liabilities": tl, "total_equity": eq}, stat, res)

        # 13. Debt-to-EBITDA
        val, stat, res = self._guard(lt_debt, ebitda, "Debt-to-EBITDA", meaningless_if_negative=True,
                                     specific_negative_reason="EBITDA is negative; Debt/EBITDA multiple is not meaningful.",
                                     numerator_name="long_term_debt", denominator_name="ebitda")
        self._add_record("debt_to_ebitda", year, val, "multiple", "Long-term Debt / EBITDA", {"long_term_debt": lt_debt, "ebitda": ebitda}, stat, res)

        # 14. Net Debt-to-EBITDA
        # Bug Fix: Agar long_term_debt missing hai par short term debt hai, to pure net_debt ko None karne ki jagah properly calculate kiya gaya.
        total_debt = (lt_debt or 0) + st_debt
        net_debt = (total_debt - cash) if (lt_debt is not None or st_debt > 0) else None
        val, stat, res = self._guard(net_debt, ebitda, "Net Debt-to-EBITDA", meaningless_if_negative=True,
                                     specific_negative_reason="EBITDA is negative; Net Debt/EBITDA is not meaningful.",
                                     numerator_name="net_debt", denominator_name="ebitda")
        self._add_record("net_debt_to_ebitda", year, val, "multiple", "Net Debt / EBITDA", {"net_debt": net_debt, "ebitda": ebitda}, stat, res)

        # 15. Interest Coverage
        val, stat, res = self._guard(op_inc, int_exp, "Interest Coverage", 
                                     specific_zero_reason="Company reports zero interest expense — Interest Coverage Ratio is not applicable.",
                                     numerator_name="operating_income", denominator_name="interest_expense")
        self._add_record("interest_coverage", year, val, "multiple", "Operating Income / Interest Expense", {"operating_income": op_inc, "interest_expense": int_exp}, stat, res)

        # 16. Debt-to-Assets
        val, stat, res = self._guard(tl, assets, "Debt-to-Assets", numerator_name="total_liabilities", denominator_name="total_assets")
        self._add_record("debt_to_assets", year, val, "ratio", "Total Liabilities / Total Assets", {"total_liabilities": tl, "total_assets": assets}, stat, res)

    def _compute_efficiency(self, curr: dict, prior: dict | None, year: int):
        rev = curr.get("revenue")
        assets = curr.get("total_assets")
        cogs = curr.get("cost_of_revenue")
        inv = curr.get("inventory")
        ar = curr.get("accounts_receivable")
        ap = curr.get("accounts_payable")

        # 17. Asset Turnover
        val, stat, res = self._guard(rev, assets, "Asset Turnover", numerator_name="revenue", denominator_name="total_assets")
        self._add_record("asset_turnover", year, val, "multiple", "Revenue / Total Assets", {"revenue": rev, "total_assets": assets}, stat, res)

        # 18. Inventory Turnover
        avg_inv = inv
        if prior and prior.get("inventory") is not None and inv is not None:
            avg_inv = (inv + prior["inventory"]) / 2
        
        val, stat, res = self._guard(cogs, avg_inv, "Inventory Turnover", 
                                     specific_zero_reason="No inventory carried — ratio not applicable (service/software company)",
                                     numerator_name="cost_of_revenue", denominator_name="average_inventory")
        self._add_record("inventory_turnover", year, val, "multiple", "Cost of Revenue / Average Inventory", {"cost_of_revenue": cogs, "average_inventory": avg_inv}, stat, res)

        # 19. DSO
        val_dso, stat_dso, res_dso = self._guard(ar, rev, "DSO", numerator_name="accounts_receivable", denominator_name="revenue")
        dso_days = (val_dso * 365) if val_dso is not None else None
        self._add_record("dso", year, dso_days, "days", "(Accounts Receivable / Revenue) * 365", {"accounts_receivable": ar, "revenue": rev}, stat_dso, res_dso)

        # 20. DPO
        val_dpo, stat_dpo, res_dpo = self._guard(ap, cogs, "DPO", numerator_name="accounts_payable", denominator_name="cost_of_revenue")
        dpo_days = (val_dpo * 365) if val_dpo is not None else None
        self._add_record("dpo", year, dpo_days, "days", "(Accounts Payable / Cost of Revenue) * 365", {"accounts_payable": ap, "cost_of_revenue": cogs}, stat_dpo, res_dpo)

        # 21. CCC
        val_dio, stat_dio, res_dio = self._guard(inv, cogs, "DIO", numerator_name="inventory", denominator_name="cost_of_revenue")
        dio_days = (val_dio * 365) if val_dio is not None else 0
        
        if stat_dso not in ["COMPUTED", "EXTREME_VALUE"] or stat_dpo not in ["COMPUTED", "EXTREME_VALUE"]:
            self._add_record("ccc", year, None, "days", "DSO + DIO - DPO", {"dso": dso_days, "dio": dio_days, "dpo": dpo_days}, "MISSING", "DSO or DPO missing/not applicable")
        else:
            ccc = dso_days + dio_days - dpo_days
            self._add_record("ccc", year, ccc, "days", "DSO + DIO - DPO", {"dso": dso_days, "dio": dio_days, "dpo": dpo_days}, "COMPUTED")

    def _compute_cash_flow_quality(self, curr: dict, year: int):
        fcf = curr.get("free_cash_flow")
        rev = curr.get("revenue")
        ni = curr.get("net_income")
        ocf = curr.get("operating_cash_flow")
        capex = curr.get("capital_expenditures")

        # 22. FCF Margin
        val, stat, res = self._guard(fcf, rev, "FCF Margin", is_percentage=True, numerator_name="free_cash_flow", denominator_name="revenue")
        self._add_record("fcf_margin", year, val, "percent", "(Free Cash Flow / Revenue) * 100", {"free_cash_flow": fcf, "revenue": rev}, stat, res)

        # 23. FCF-to-Net Income
        val, stat, res = self._guard(fcf, ni, "FCF-to-Net Income", meaningless_if_negative=True,
                                     specific_negative_reason="Net income is negative; ratio evaluates to backwards sign.",
                                     numerator_name="free_cash_flow", denominator_name="net_income")
        self._add_record("fcf_to_net_income", year, val, "ratio", "Free Cash Flow / Net Income", {"free_cash_flow": fcf, "net_income": ni}, stat, res)

        # 24. OCF-to-Revenue
        val, stat, res = self._guard(ocf, rev, "OCF-to-Revenue", is_percentage=True, numerator_name="operating_cash_flow", denominator_name="revenue")
        self._add_record("ocf_to_revenue", year, val, "percent", "(Operating Cash Flow / Revenue) * 100", {"operating_cash_flow": ocf, "revenue": rev}, stat, res)

        # 25. CapEx-to-Revenue
        val, stat, res = self._guard(capex, rev, "CapEx-to-Revenue", is_percentage=True, numerator_name="capital_expenditures", denominator_name="revenue")
        self._add_record("capex_to_revenue", year, val, "percent", "(Capital Expenditures / Revenue) * 100", {"capital_expenditures": capex, "revenue": rev}, stat, res)

    def _compute_growth(self, curr: dict, prior: dict | None, year: int):
        if not prior:
            return

        def _growth(field: str, ratio_name: str, formula: str, allow_abs_denom: bool = False):
            c_val = curr.get(field)
            p_val = prior.get(field)
            denom = abs(p_val) if allow_abs_denom and p_val is not None else p_val
            
            val, stat, res = self._guard((c_val - p_val) if c_val is not None and p_val is not None else None, denom, ratio_name, is_percentage=True, numerator_name=f"change_in_{field}", denominator_name=f"prior_{field}")
            self._add_record(ratio_name, year, val, "percent", formula, {f"current_{field}": c_val, f"prior_{field}": p_val}, stat, res)

        _growth("revenue", "revenue_yoy", "((Revenue_t - Revenue_t-1) / Revenue_t-1) * 100")
        _growth("gross_profit", "gross_profit_yoy", "((GrossProfit_t - GrossProfit_t-1) / GrossProfit_t-1) * 100")
        _growth("operating_income", "operating_income_yoy", "((OpIncome_t - OpIncome_t-1) / abs(OpIncome_t-1)) * 100", True)
        _growth("net_income", "net_income_yoy", "((NetIncome_t - NetIncome_t-1) / abs(NetIncome_t-1)) * 100", True)
        _growth("eps_diluted", "eps_diluted_yoy", "((EPS_t - EPS_t-1) / abs(EPS_t-1)) * 100", True)
        _growth("free_cash_flow", "fcf_yoy", "((FCF_t - FCF_t-1) / abs(FCF_t-1)) * 100", True)

    def _compute_valuation(self, curr: dict, year: int):
        mcap = curr.get("market_cap")
        ni = curr.get("net_income")
        fcf = curr.get("free_cash_flow")
        ebitda = curr.get("ebitda")
        lt_debt = curr.get("long_term_debt")
        st_debt = curr.get("short_term_debt", 0) or 0
        cash = curr.get("cash_and_equivalents", 0) or 0

        # 34. P/E Ratio
        val, stat, res = self._guard(mcap, ni, "P/E", meaningless_if_negative=True,
                                     specific_negative_reason="Net Income is zero or negative; P/E Ratio is not meaningful.",
                                     numerator_name="market_cap", denominator_name="net_income")
        self._add_record("pe_ratio", year, val, "multiple", "Market Cap / Net Income", {"market_cap": mcap, "net_income": ni}, stat, res)

        # 35. P/FCF
        val, stat, res = self._guard(mcap, fcf, "P/FCF", meaningless_if_negative=True, numerator_name="market_cap", denominator_name="free_cash_flow")
        self._add_record("p_fcf", year, val, "multiple", "Market Cap / Free Cash Flow", {"market_cap": mcap, "free_cash_flow": fcf}, stat, res)

        # 36. EV/EBITDA
        ev = (mcap + lt_debt + st_debt - cash) if (mcap is not None and lt_debt is not None) else None
        val, stat, res = self._guard(ev, ebitda, "EV/EBITDA", meaningless_if_negative=True, numerator_name="enterprise_value", denominator_name="ebitda")
        self._add_record("ev_ebitda", year, val, "multiple", "Enterprise Value / EBITDA", {"enterprise_value": ev, "ebitda": ebitda}, stat, res)

    def _compute_cagr(self):
        # CAGR (Compound Annual Growth Rate) nikalne ke liye
        if not self.available_years:
            return
            
        recent_year = self.available_years[-1]
        recent_data = self.data_by_year[recent_year]
        
        def _cagr(field: str, ratio_name: str, formula: str):
            # Bug Fix: Oldest available year dhoondenge jisme is field ka data available ho
            oldest_year = None
            for y in self.available_years:
                if self.data_by_year[y].get(field) is not None:
                    oldest_year = y
                    break
            
            if oldest_year is None or oldest_year == recent_year:
                # Agar koi bhi data nahi hai ya sirf ek hi saal ka data hai
                self._add_record(ratio_name, recent_year, None, "percent", formula, 
                                 {f"{field}_oldest": None, f"{field}_recent": recent_data.get(field), "n_years": 0}, 
                                 "NOT_COMPUTABLE", "Not enough valid data points for CAGR.")
                return

            n = recent_year - oldest_year
            oldest_data = self.data_by_year[oldest_year]
            oldest_val = oldest_data.get(field)
            recent_val = recent_data.get(field)
            
            inputs = {
                f"{field}_oldest": oldest_val,
                f"{field}_recent": recent_val,
                "n_years": n
            }
            
            if oldest_val is None or oldest_val <= 0:
                self._add_record(ratio_name, recent_year, None, "percent", formula, inputs, "NOT_COMPUTABLE", 
                                 f"Base year value is zero or negative — CAGR cannot be meaningfully computed. Base year value: {oldest_val}.")
            elif n < 2:
                self._add_record(ratio_name, recent_year, None, "percent", formula, inputs, "NOT_COMPUTABLE", 
                                 "Fewer than 3 fiscal years of data available (n<2) — CAGR requires at least 3 years to be meaningful.")
            else:
                if recent_val is None:
                    self._add_record(ratio_name, recent_year, None, "percent", formula, inputs, "MISSING", f"Most recent {field} is missing")
                else:
                    try:
                        val = (math.pow(recent_val / oldest_val, 1/n) - 1) * 100
                        status = "COMPUTED"
                        if abs(val) > 10000:
                            status = "EXTREME_VALUE"
                        self._add_record(ratio_name, recent_year, round(val, 4), "percent", formula, inputs, status)
                    except Exception as e:
                        self._add_record(ratio_name, recent_year, None, "percent", formula, inputs, "NOT_COMPUTABLE", f"Math error: {e}")

        n = (self.available_years[-1] - self.available_years[0]) if len(self.available_years) > 1 else 0
        cagr_name_suffix = f"_{n}yr" if n > 0 else "_nyr"
        _cagr("revenue", f"revenue_cagr{cagr_name_suffix}", f"((Revenue_most_recent / Revenue_oldest) ^ (1/{n if n>0 else 'n'}) - 1) * 100")
        _cagr("net_income", f"net_income_cagr{cagr_name_suffix}", f"((NetIncome_most_recent / NetIncome_oldest) ^ (1/{n if n>0 else 'n'}) - 1) * 100")
