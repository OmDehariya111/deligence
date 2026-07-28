"""
Module:  trend_engine.py
Agent:   Analysis Agent
Purpose: Computes trends, momentum, and sudden changes based on ratio data.
         # Is module ka main kaam Module 1 se aane wale ratios ko analyze karna hai
         # taaki unka trend (UP/DOWN/STABLE), momentum (speed), aur sudden changes detect ho sake.
"""

import math
from collections import defaultdict
from schemas.pydantic_models import RatioRecord, RatioTrend, SuddenChange

GOOD_DIRECTION = {
    # UP is good
    "gross_margin": "UP",
    "operating_margin": "UP",
    "net_profit_margin": "UP",
    "ebitda_margin": "UP",
    "roa": "UP",
    "roe": "UP",
    "roic": "UP",
    "current_ratio": "UP",
    "quick_ratio": "UP",
    "cash_ratio": "UP",
    "interest_coverage": "UP",
    "asset_turnover": "UP",
    "inventory_turnover": "UP",
    "fcf_margin": "UP",
    "fcf_to_net_income": "UP",
    "ocf_to_revenue": "UP",
    "revenue_yoy": "UP",
    "gross_profit_yoy": "UP",
    "operating_income_yoy": "UP",
    "net_income_yoy": "UP",
    "eps_diluted_yoy": "UP",
    "fcf_yoy": "UP",
    "dpo": "UP",
    
    # DOWN is good
    "debt_to_equity": "DOWN",
    "debt_to_ebitda": "DOWN",
    "net_debt_to_ebitda": "DOWN",
    "debt_to_assets": "DOWN",
    "dso": "DOWN",
    "ccc": "DOWN",
}

class TrendEngine:
    def __init__(self, ratios: list[RatioRecord]):
        self.ratios = ratios
        
        # Group ratios by name, ignoring MISSING, NOT_APPLICABLE, NOT_MEANINGFUL, NOT_COMPUTABLE
        # Yahan hum sabhi valid ratios ko unke naam ke hisab se alag-alag groups (list) me daal rahe hain
        self.ratios_by_name = defaultdict(list)
        for r in ratios:
            if r.status in ["COMPUTED", "EXTREME_VALUE"] and r.value is not None:
                if not r.ratio_name.endswith("_cagr_5yr") and not r.ratio_name.endswith("_cagr_nyr") and not "_cagr_" in r.ratio_name:
                    self.ratios_by_name[r.ratio_name].append(r)
                
        # Sort each list by year
        # Har metric ke saalo ko oldest se newest me sort kar rahe hain (e.g. 2021, 2022, 2023...)
        for name in self.ratios_by_name:
            self.ratios_by_name[name] = sorted(self.ratios_by_name[name], key=lambda x: x.fiscal_year)

    def run(self) -> list[RatioTrend]:
        results = []
        for name, records in self.ratios_by_name.items():
            trend = self._analyze_trend(name, records)
            results.append(trend)
        return results

    def _analyze_trend(self, ratio_name: str, records: list[RatioRecord]) -> RatioTrend:
        n = len(records)
        year_values = {str(r.fiscal_year): r.value for r in records}
        
        # Agar 3 saal se kam ka data hai, to trend analyze karna possible nahi hai (math points kam padenge)
        if n < 3:
            return RatioTrend(
                ratio_name=ratio_name,
                trend_direction="INSUFFICIENT_DATA",
                trend_confidence="NONE",
                momentum="NONE",
                sudden_changes=[],
                average_value=None,
                std_deviation=None,
                year_values=year_values,
                linear_slope=None,
                data_years=n
            )

        # 1. Averages and StdDev (Average aur Data kitna faila hua hai ye nikal rahe hain)
        values = [r.value for r in records]
        avg = sum(values) / n
        std_dev = math.sqrt(sum((v - avg)**2 for v in values) / n) if n > 1 else 0.0

        # 2. Linear Slope (Mathematical Regression Slope nikal rahe hain dekne ke liye line upar ja rahi hai ya neeche)
        x_mean = sum(range(n)) / n
        y_mean = avg
        num = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        den = sum((i - x_mean)**2 for i in range(n))
        slope = num / den if den != 0 else 0.0

        # 3. Trend Direction
        half = n // 2
        first_half_avg = sum(values[:half]) / half
        second_half_avg = sum(values[-half:]) / half
        
        # Determine STABLE
        # Stable agar saari values average ke aas paas hain (within +/- 10% range)
        is_stable = True
        if avg == 0:
            is_stable = all(v == 0 for v in values)
        else:
            for v in values:
                if abs((v - avg) / avg) > 0.10:
                    is_stable = False
                    break
        
        if is_stable:
            direction = "STABLE"
        else:
            # First half aur second half ko compare karte hain confirm karne ke liye ki slope sahi baat bata raha hai ya nahi
            if slope > 0 and second_half_avg > first_half_avg:
                mov = "UP"
            elif slope < 0 and second_half_avg < first_half_avg:
                mov = "DOWN"
            else:
                mov = "FLAT" # Conflict hai slope aur halves me, toh data properly ek direction me nahi badh raha

            good_dir = GOOD_DIRECTION.get(ratio_name)
            if mov == "FLAT":
                direction = "VOLATILE"
            elif good_dir:
                if mov == good_dir:
                    direction = "IMPROVING" # Badlav positive sign de raha hai company ke liye
                else:
                    direction = "DECLINING" # Badlav negative sign de raha hai company ke liye
            else:
                # Valuation ratios ke liye koi direct 'good' ya 'bad' nahi hota, isliye unhe bas UP ya DOWN bolenge
                direction = mov

        # 4. Momentum (Accelerating / Decelerating)
        # Bug Fix: abs() ko hata kar actual mathematical deltas aur trend sign ke basis par Momentum calculate kiya hai.
        momentum = "NONE"
        if direction in ["IMPROVING", "DECLINING", "UP", "DOWN"]:
            # Check last 3 years deltas if available
            if n >= 3:
                m1 = values[-2] - values[-3]
                m2 = values[-1] - values[-2]
                
                # Agar direction mathematically UP wali hai (positive trend chal raha hai)
                if mov == "UP":
                    # Upward momentum accelerating tab hai agar naya jump pichle wale jump se bada aur positive hai
                    if m2 > m1 and m2 > 0:
                        momentum = "ACCELERATING"
                    # Upward momentum decelerating agar naya jump pichle wale jump se chota ho gaya
                    elif m2 < m1:
                        momentum = "DECELERATING"
                # Agar direction mathematically DOWN wali hai (negative trend chal raha hai)
                elif mov == "DOWN":
                    # Downward momentum accelerating tab hai agar naya fall pichle fall se aur bada (more negative) hai
                    if m2 < m1 and m2 < 0:
                        momentum = "ACCELERATING"
                    # Downward momentum decelerating tab hai agar naya fall pichle fall se chota (less negative) hai
                    elif m2 > m1:
                        momentum = "DECELERATING"

        # 5. Sudden Changes (Early Warning System)
        unit = records[0].unit
        sudden_changes = []
        for i in range(1, n):
            prev = values[i-1]
            curr = values[i]
            year = records[i].fiscal_year
            
            is_sudden = False
            classification = "SUDDEN_DETERIORATION" # default
            magnitude = abs(curr - prev)
            
            if "yoy" in ratio_name:
                # Growth rate: flag sign swing
                if (prev > 0 and curr < 0) or (prev < 0 and curr > 0):
                    is_sudden = True
                    # Good direction logic
                    if curr > 0:
                        classification = "SUDDEN_IMPROVEMENT"
                    else:
                        classification = "SUDDEN_DETERIORATION"
            elif unit == "percent":
                if magnitude > 5.0:
                    is_sudden = True
                    # If it went UP and UP is good -> IMPROVEMENT
                    good_dir = GOOD_DIRECTION.get(ratio_name)
                    if good_dir == "UP" and curr > prev:
                        classification = "SUDDEN_IMPROVEMENT"
                    elif good_dir == "DOWN" and curr < prev:
                        classification = "SUDDEN_IMPROVEMENT"
                    elif not good_dir:
                        classification = f"SUDDEN_{'UP' if curr > prev else 'DOWN'}"
            elif unit == "multiple":
                if prev != 0 and (magnitude / abs(prev)) > 0.30:
                    is_sudden = True
                    good_dir = GOOD_DIRECTION.get(ratio_name)
                    if good_dir == "UP" and curr > prev:
                        classification = "SUDDEN_IMPROVEMENT"
                    elif good_dir == "DOWN" and curr < prev:
                        classification = "SUDDEN_IMPROVEMENT"
                    elif not good_dir:
                        classification = f"SUDDEN_{'UP' if curr > prev else 'DOWN'}"
            elif unit in ["days", "ratio"]:
                # Bug Fix: Days (DSO, DPO, CCC) aur ratio (Debt/Assets) ke liye Sudden Changes trigger include kiya.
                is_significant = False
                if unit == "days" and (magnitude > 10 or (prev != 0 and (magnitude / abs(prev)) > 0.20)):
                    is_significant = True
                elif unit == "ratio" and (magnitude > 0.1 or (prev != 0 and (magnitude / abs(prev)) > 0.20)):
                    is_significant = True
                    
                if is_significant:
                    is_sudden = True
                    good_dir = GOOD_DIRECTION.get(ratio_name)
                    if good_dir == "UP" and curr > prev:
                        classification = "SUDDEN_IMPROVEMENT"
                    elif good_dir == "DOWN" and curr < prev:
                        classification = "SUDDEN_IMPROVEMENT"
                    elif not good_dir:
                        classification = f"SUDDEN_{'UP' if curr > prev else 'DOWN'}"

            if is_sudden:
                sudden_changes.append(SuddenChange(
                    year=year,
                    prior_value=round(prev, 4),
                    current_value=round(curr, 4),
                    magnitude=round(magnitude, 4),
                    classification=classification
                ))

        return RatioTrend(
            ratio_name=ratio_name,
            trend_direction=direction,
            trend_confidence="HIGH" if direction not in ["INSUFFICIENT_DATA", "VOLATILE"] else "LOW",
            momentum=momentum,
            sudden_changes=sudden_changes,
            average_value=round(avg, 4),
            std_deviation=round(std_dev, 4),
            year_values={k: round(v, 4) for k, v in year_values.items()},
            linear_slope=round(slope, 4),
            data_years=n
        )
