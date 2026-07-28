"""Package: utils. Purpose: Parse XBRL taxonomy from CompanyFacts MCP call."""
# Ye file poore Ingestion system ka sabse critical "Financial Brain" hai.
# SEC XBRL format me data deta hai jahan har item ke multiple tags ho sakte hain (jaise Revenue ko "SalesRevenueNet" bhi bolte hain).
# Is class ka kaam us huge raw dictionary me se exact saal (year) ka valid financial number dhoondna aur use normalize karna hai.

import logging
from typing import Any
from schemas.pydantic_models import AnnualFinancials

logger = logging.getLogger(__name__)

class FinancialExtractor:
    """Class to extract standardized financial metrics from SEC CompanyFacts."""
    def __init__(self, company_facts: dict, fiscal_year_end: str = "1231"):
        # company_facts wo raw data hai jo SEC ne diya hai
        self.facts = company_facts.get("facts", {})
        self.us_gaap = self.facts.get("us-gaap", {}) # America ki standard accounting dictionary
        self.dei = self.facts.get("dei", {}) # Document Entity Information (Shares wagera yahan hote hain)
        self.fye = fiscal_year_end or "1231"
        from collections import defaultdict
        self.field_metadata = defaultdict(dict) # Har metric kahan se (kis tag se) aaya, uska record rakhne ke liye


    def is_matching_year(self, entry_end: str, target_year: int) -> bool:
        """Check if the entry's end date falls within 7 days of the target fiscal year end."""
        if not entry_end or len(entry_end) != 10:
            return False
        try:
            from datetime import datetime
            end_dt = datetime.strptime(entry_end, "%Y-%m-%d")
            
            # Extract FYE month and day
            fye_month = int(self.fye[:2])
            fye_day = int(self.fye[2:])
            
            # Construct target date for the target_year
            target_dt = datetime(target_year, fye_month, fye_day)
            
            # Check absolute difference in days
            if abs((end_dt - target_dt).days) <= 7:
                return True
        except Exception:
            pass
        return False

    def get_annual_value(self, concept_dict: dict, year: int, unit_filter: str = "USD") -> float | None:
        """Finds the value for a specific fiscal year from a concept dictionary."""
        units = concept_dict.get("units", {})
        target_unit_list = []
        
        if unit_filter in units:
            target_unit_list = units[unit_filter]
        elif len(units) == 1:
            target_unit_list = list(units.values())[0]
            
        valid_entries = []
        for entry in target_unit_list:
            if entry.get("form") in ["10-K", "20-F"] and entry.get("fp") == "FY":
                if entry.get("fy") == year or self.is_matching_year(entry.get("end"), year):
                    valid_entries.append(entry)
                
        if not valid_entries:
            return None
            
        # Sort by end date descending (latest first) and filed date descending (newest restatements first)
        valid_entries.sort(key=lambda x: (x.get("end", ""), x.get("filed", "")), reverse=True)
        return float(valid_entries[0].get("val", 0.0))
        
    def find_first_available(self, taxonomy: dict, tags: list[str], year: int, unit_filter: str = "USD", field_name: str = None) -> float | None:
        for tag in tags:
            if tag in taxonomy:
                val = self.get_annual_value(taxonomy[tag], year, unit_filter)
                if val is not None:
                    if field_name:
                        self.field_metadata[field_name][year] = {
                            "source": "SEC EDGAR",
                            "xbrl_tag": tag
                        }
                    return val
        return None

    def extract_year(self, year: int) -> AnnualFinancials:
        fin = AnnualFinancials(fiscal_year=year)
        
        # A. Income Statement
        fin.revenue = self.find_first_available(self.us_gaap, [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "Revenues",
            "SalesRevenueNet"
        ], year, field_name="revenue")
        
        if fin.revenue is None:
            goods = self.find_first_available(self.us_gaap, ["SalesRevenueGoodsNet"], year)
            services = self.find_first_available(self.us_gaap, ["SalesRevenueServicesNet"], year)
            if goods is not None or services is not None:
                fin.revenue = (goods or 0.0) + (services or 0.0)
                
        fin.cost_of_revenue = self.find_first_available(self.us_gaap, [
            "CostOfGoodsAndServicesSold",
            "CostOfRevenue",
            "CostOfGoodsSold",
            "CostOfServices",
            "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"
        ], year, field_name="cost_of_revenue")
        
        fin.gross_profit = self.find_first_available(self.us_gaap, ["GrossProfit"], year, field_name="gross_profit")
        if fin.gross_profit is None and fin.revenue is not None and fin.cost_of_revenue is not None:
            fin.gross_profit = fin.revenue - fin.cost_of_revenue
            
        fin.sga_expense = self.find_first_available(self.us_gaap, [
            "SellingGeneralAndAdministrativeExpense",
            "SellingExpense"
        ], year, field_name="sga_expense")
        if fin.sga_expense is None:
            ga = self.find_first_available(self.us_gaap, ["GeneralAndAdministrativeExpense"], year)
            sm = self.find_first_available(self.us_gaap, ["SellingAndMarketingExpense"], year)
            if ga is not None and sm is not None:
                fin.sga_expense = ga + sm
            elif ga is not None:
                fin.sga_expense = ga
            elif sm is not None:
                fin.sga_expense = sm
                
        fin.rd_expense = self.find_first_available(self.us_gaap, [
            "ResearchAndDevelopmentExpense",
            "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"
        ], year, field_name="rd_expense")
        
        fin.operating_income = self.find_first_available(self.us_gaap, ["OperatingIncomeLoss"], year, field_name="operating_income")
        if fin.operating_income is None:
            if fin.gross_profit is not None:
                fin.operating_income = fin.gross_profit - (fin.sga_expense or 0.0) - (fin.rd_expense or 0.0)

        fin.interest_expense = self.find_first_available(self.us_gaap, [
            "InterestExpense",
            "InterestAndDebtExpense",
            "InterestExpenseDebt",
            "InterestExpenseRelatedParty",
            "InterestExpenseNonoperating"
        ], year, field_name="interest_expense")
        
        fin.income_before_tax = self.find_first_available(self.us_gaap, [
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"
        ], year, field_name="income_before_tax")
        
        fin.income_tax_expense = self.find_first_available(self.us_gaap, ["IncomeTaxExpenseBenefit"], year, field_name="income_tax_expense")
        fin.net_income = self.find_first_available(self.us_gaap, [
            "NetIncomeLoss",
            "NetIncomeLossAvailableToCommonStockholdersBasic",
            "ProfitLoss",
            "NetIncome"
        ], year, field_name="net_income")
        
        if fin.income_before_tax is None and fin.net_income is not None and fin.income_tax_expense is not None:
            fin.income_before_tax = fin.net_income + fin.income_tax_expense
            
        fin.eps_basic = self.find_first_available(self.us_gaap, ["EarningsPerShareBasic"], year, "USD/shares", field_name="eps_basic")
        fin.eps_diluted = self.find_first_available(self.us_gaap, ["EarningsPerShareDiluted"], year, "USD/shares", field_name="eps_diluted")
        
        if fin.income_before_tax is not None and fin.operating_income is not None:
            fin.non_operating_income = fin.income_before_tax - fin.operating_income
            
        # B. Balance Sheet
        fin.total_assets = self.find_first_available(self.us_gaap, ["Assets"], year, field_name="total_assets")
        fin.current_assets = self.find_first_available(self.us_gaap, ["AssetsCurrent"], year, field_name="current_assets")
        
        fin.cash_and_equivalents = self.find_first_available(self.us_gaap, [
            "CashAndCashEquivalentsAtCarryingValue",
            "Cash",
            "CashAndCashEquivalents",
            "CashCashEquivalentsAndShortTermInvestments"
        ], year, field_name="cash_and_equivalents")
        
        fin.short_term_investments = self.find_first_available(self.us_gaap, [
            "ShortTermInvestments",
            "MarketableSecuritiesCurrent",
            "AvailableForSaleSecuritiesCurrent",
            "AvailableForSaleSecuritiesDebtMaturitiesWithinOneYearFairValue",
            "AvailableForSaleSecuritiesDebtSecuritiesCurrent"
        ], year, field_name="short_term_investments")
        
        fin.accounts_receivable = self.find_first_available(self.us_gaap, [
            "AccountsReceivableNetCurrent",
            "ReceivablesNetCurrent",
            "AccountsReceivableNet"
        ], year, field_name="accounts_receivable")
        
        fin.inventory = self.find_first_available(self.us_gaap, ["InventoryNet", "Inventories"], year, field_name="inventory")
        fin.ppe_net = self.find_first_available(self.us_gaap, ["PropertyPlantAndEquipmentNet", "PropertyPlantAndEquipmentGross"], year, field_name="ppe_net")
        fin.goodwill = self.find_first_available(self.us_gaap, ["Goodwill"], year, field_name="goodwill")
        
        intangible_1 = self.find_first_available(self.us_gaap, ["FiniteLivedIntangibleAssetsNet"], year)
        intangible_2 = self.find_first_available(self.us_gaap, ["IntangibleAssetsNetExcludingGoodwill"], year)
        intangible_3 = self.find_first_available(self.us_gaap, ["IndefiniteLivedIntangibleAssetsExcludingGoodwill"], year)
        
        if intangible_2 is not None:
            fin.intangible_assets = intangible_2
        elif intangible_1 is not None or intangible_3 is not None:
            fin.intangible_assets = (intangible_1 or 0.0) + (intangible_3 or 0.0)
            
        fin.total_liabilities = self.find_first_available(self.us_gaap, ["Liabilities"], year, field_name="total_liabilities")
        fin.current_liabilities = self.find_first_available(self.us_gaap, ["LiabilitiesCurrent"], year, field_name="current_liabilities")
        fin.accounts_payable = self.find_first_available(self.us_gaap, ["AccountsPayableCurrent", "AccountsPayable"], year, field_name="accounts_payable")
        
        st1 = self.find_first_available(self.us_gaap, ["ShortTermBorrowings"], year)
        st2 = self.find_first_available(self.us_gaap, ["LongTermDebtCurrent"], year)
        st3 = self.find_first_available(self.us_gaap, ["CommercialPaper"], year)
        st4 = self.find_first_available(self.us_gaap, ["DebtCurrent"], year)
        st5 = self.find_first_available(self.us_gaap, ["NotesPayableCurrent"], year)
        
        if st1 is not None or st2 is not None:
            sum_1_2 = (st1 or 0.0) + (st2 or 0.0)
            if st4 is not None and abs(st4 - sum_1_2) < (st4 * 0.01 + 1000):
                fin.short_term_debt = sum_1_2
            elif st4 is not None:
                fin.short_term_debt = sum_1_2
            else:
                fin.short_term_debt = sum_1_2
        elif st4 is not None:
            fin.short_term_debt = st4
        elif st3 is not None or st5 is not None:
            fin.short_term_debt = (st3 or 0.0) + (st5 or 0.0)
            
        fin.long_term_debt = self.find_first_available(self.us_gaap, [
            "LongTermDebtNoncurrent",
            "LongTermDebt",
            "LongTermNotesPayable"
        ], year, field_name="long_term_debt")
        
        fin.total_equity = self.find_first_available(self.us_gaap, [
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
        ], year, field_name="total_equity")
        
        fin.retained_earnings = self.find_first_available(self.us_gaap, [
            "RetainedEarningsAccumulatedDeficit",
            "RetainedEarnings"
        ], year, field_name="retained_earnings")
        
        fin.shares_outstanding = self.find_first_available(self.us_gaap, ["CommonStockSharesOutstanding"], year, "shares", field_name="shares_outstanding")
        if fin.shares_outstanding is None:
            fin.shares_outstanding = self.find_first_available(self.dei, ["EntityCommonStockSharesOutstanding"], year, "shares", field_name="shares_outstanding")
            
        fin.weighted_avg_shares = self.find_first_available(self.us_gaap, ["WeightedAverageNumberOfDilutedSharesOutstanding"], year, "shares", field_name="weighted_avg_shares")
        if fin.weighted_avg_shares is None:
            fin.weighted_avg_shares = self.find_first_available(self.us_gaap, ["WeightedAverageNumberOfSharesOutstandingBasic"], year, "shares", field_name="weighted_avg_shares")
            
        # C. Cash Flow
        fin.operating_cash_flow = self.find_first_available(self.us_gaap, ["NetCashProvidedByUsedInOperatingActivities"], year, field_name="operating_cash_flow")
        
        fin.capital_expenditures = self.find_first_available(self.us_gaap, [
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquireProductiveAssets",
            "CapitalExpenditureContinuingOperations",
            "PaymentsForCapitalImprovements"
        ], year, field_name="capital_expenditures")
        
        fin.depreciation_and_amortization = self.find_first_available(self.us_gaap, [
            "DepreciationDepletionAndAmortization",
            "DepreciationAndAmortization"
        ], year, field_name="depreciation_and_amortization")
        if fin.depreciation_and_amortization is None:
            dep = self.find_first_available(self.us_gaap, ["Depreciation"], year)
            amo = self.find_first_available(self.us_gaap, ["AmortizationOfIntangibleAssets"], year)
            if dep is not None or amo is not None:
                fin.depreciation_and_amortization = (dep or 0.0) + (amo or 0.0)
                
        if fin.operating_cash_flow is not None:
            fin.free_cash_flow = fin.operating_cash_flow - (fin.capital_expenditures or 0.0)
            self.field_metadata["free_cash_flow"][year] = {
                "source": "computed",
                "formula": "operating_cash_flow - capital_expenditures"
            }
            
        fin.investing_cash_flow = self.find_first_available(self.us_gaap, ["NetCashProvidedByUsedInInvestingActivities"], year, field_name="investing_cash_flow")
        fin.financing_cash_flow = self.find_first_available(self.us_gaap, ["NetCashProvidedByUsedInFinancingActivities"], year, field_name="financing_cash_flow")
        
        fin.dividends_paid = self.find_first_available(self.us_gaap, ["PaymentsOfDividends"], year, field_name="dividends_paid")
        if fin.dividends_paid is None:
            div_c = self.find_first_available(self.us_gaap, ["PaymentsOfDividendsCommonStock"], year)
            div_p = self.find_first_available(self.us_gaap, ["PaymentsOfDividendsPreferredStockAndPreferenceStock"], year)
            if div_c is not None or div_p is not None:
                fin.dividends_paid = (div_c or 0.0) + (div_p or 0.0)
                
        fin.stock_buybacks = self.find_first_available(self.us_gaap, [
            "PaymentsForRepurchaseOfCommonStock",
            "TreasuryStockValueAcquiredCostMethod"
        ], year, field_name="stock_buybacks")
        
        # D. Derived
        if fin.operating_income is not None:
            fin.ebitda = fin.operating_income + (fin.depreciation_and_amortization or 0.0)
            self.field_metadata["ebitda"][year] = {
                "source": "computed",
                "formula": "operating_income + depreciation_and_amortization"
            }
            
        if fin.long_term_debt is not None or fin.short_term_debt is not None:
            total_debt = (fin.long_term_debt or 0.0) + (fin.short_term_debt or 0.0)
            if fin.cash_and_equivalents is not None:
                fin.net_debt = total_debt - fin.cash_and_equivalents
                self.field_metadata["net_debt"][year] = {
                    "source": "computed",
                    "formula": "(long_term_debt + short_term_debt) - cash_and_equivalents"
                }
            
        if fin.current_assets is not None and fin.current_liabilities is not None:
            fin.working_capital = fin.current_assets - fin.current_liabilities
            self.field_metadata["working_capital"][year] = {
                "source": "computed",
                "formula": "current_assets - current_liabilities"
            }
            
        return fin

    def get_available_years(self) -> list[int]:
        """Finds the most recent 5 fiscal years that have data in CompanyFacts."""
        years = set()
        for tag, data in self.us_gaap.items():
            for unit, entries in data.get("units", {}).items():
                for entry in entries:
                    if entry.get("form") == "10-K" and entry.get("fp") == "FY":
                        if "fy" in entry:
                            years.add(entry["fy"])
        
        sorted_years = sorted(list(years), reverse=True)
        return sorted_years[:5]
