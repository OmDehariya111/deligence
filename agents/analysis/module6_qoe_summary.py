import json
from datetime import datetime, timezone
from schemas.pydantic_models import (
    QOESummary, ModulesStatus, DataLimitations,
    RatioRecord, RatioTrend, FraudDistressOutput, AnomalyOutput, BenchmarkOutput, MissingFieldLog
)
from typing import Any

class QOESummaryEngine:
    def __init__(
        self,
        ticker: str,
        company_name: str,
        run_id: str,
        n_years: int,
        data_depth_mode: str,
        ingestion_summary: dict[str, Any],
        ratios: list[RatioRecord],
        trends: list[RatioTrend],
        fraud: FraudDistressOutput | None,
        anomaly: AnomalyOutput | None,
        benchmark: BenchmarkOutput | None,
        module_statuses: dict[str, str]
    ):
        # Yahan pichle sabhi modules ka data collect hota hai taaki ek final Report Card ban sake
        self.ticker = ticker
        self.company_name = company_name
        self.run_id = run_id
        self.n_years = n_years
        self.data_depth_mode = data_depth_mode
        self.ingestion = ingestion_summary
        self.ratios = ratios
        self.trends = trends
        self.fraud = fraud
        self.anomaly = anomaly
        self.benchmark = benchmark
        self.module_statuses = module_statuses

    def run(self) -> QOESummary:
        # Step 6.0: ModulesStatus
        # Status store karte hain taaki pata chale kaunse module successfully run hue aur kaunse skip/fail
        mod_status = ModulesStatus(
            module_1_ratio_engine=self.module_statuses.get("MODULE_1_RATIO_ENGINE", "SKIPPED"),
            module_2_trend_analysis=self.module_statuses.get("MODULE_2_TREND_ANALYSIS", "SKIPPED"),
            module_3_fraud_distress=self.module_statuses.get("MODULE_3_FRAUD_DISTRESS", "SKIPPED"),
            module_4_anomaly_detection=self.module_statuses.get("MODULE_4_ANOMALY_DETECTION", "SKIPPED"),
            module_5_sector_benchmark=self.module_statuses.get("MODULE_5_SECTOR_BENCHMARK", "SKIPPED"),
            data_years=self.n_years,
            data_depth_mode=self.data_depth_mode
        )

        # Step 6.1: Score
        # Shuruwat me company ko 100 points milte hain. Phir galatiyo ke hisab se points (deductions) kat-te hain.
        score = 100
        
        # Fraud Deductions (Agar company manipulation kar rahi hai ya bankrupt hone wali hai to bhari penalty lagegi)
        latest_beneish = None
        latest_altman = None
        
        if self.fraud:
            if self.fraud.beneish_scores:
                latest_beneish = self.fraud.beneish_scores[-1]
                if latest_beneish.verdict == "LIKELY_MANIPULATOR":
                    score -= 25
                elif latest_beneish.verdict == "GREY_ZONE":
                    score -= 10
                    
            if self.fraud.altman_scores:
                latest_altman = self.fraud.altman_scores[-1]
                if latest_altman.verdict == "DISTRESS_ZONE":
                    score -= 20
                elif latest_altman.verdict == "GREY_ZONE":
                    score -= 10
                # NOT_APPLICABLE (financial) receives 0 deduction

        # Anomaly Deductions
        if self.anomaly:
            for flag in self.anomaly.flags:
                if flag.severity == "CRITICAL":
                    score -= 15
                elif flag.severity == "HIGH":
                    score -= 10
                elif flag.severity == "MEDIUM":
                    score -= 5
                elif flag.severity == "LOW":
                    score -= 2

        # Trend Deductions
        if mod_status.module_2_trend_analysis == "COMPLETE":
            declining_count = sum(1 for t in self.trends if t.trend_direction == "DECLINING")
            if declining_count >= 3:
                score -= 5
                
            rev_trend = next((t for t in self.trends if t.ratio_name == "Revenue Growth YoY"), None)
            if rev_trend and rev_trend.trend_direction == "DECLINING":
                score -= 5
                
            fcf_ni_trend = next((t for t in self.trends if t.ratio_name == "FCF/Net Income"), None)
            if fcf_ni_trend and fcf_ni_trend.year_values:
                bad_fcf_years = sum(1 for v in fcf_ni_trend.year_values.values() if v < 0.8)
                if bad_fcf_years >= 3:
                    score -= 5

        # Missing Data Deductions
        missing_fields_log = self.ingestion.get("missing_critical_fields", [])
        missing_names = [m.get("field") if isinstance(m, dict) else m.field for m in missing_fields_log]
        
        for mf in missing_names:
            if mf == "interest_expense":
                score -= 3
            elif mf == "depreciation_and_amortization":
                score -= 3
            elif mf == "property_plant_equipment_net":
                score -= 3
            else:
                score -= 1

        score = max(0, score)
        
        # Label
        if score >= 90:
            label = "EXCELLENT"
        elif score >= 75:
            label = "GOOD"
        elif score >= 60:
            label = "FAIR"
        elif score >= 40:
            label = "POOR"
        else:
            label = "VERY POOR"

        # Step 6.2 & 6.3: Top Strengths and Concerns
        # Har positive aur negative point ko ek weight/score dete hain taaki aakhir me unhe sort kar sakein
        strengths_candidates = []
        concerns_candidates = []
        
        # Pull anomalies (Anomalies hamesha concerns yani buri baat me jayengi)
        if self.anomaly:
            for flag in self.anomaly.flags:
                weight = {"CRITICAL": 100, "HIGH": 75, "MEDIUM": 50, "LOW": 25}.get(flag.severity, 0)
                concerns_candidates.append((weight, f"[{flag.severity}] {flag.title}: {flag.description}"))
                
        # Pull fraud
        if latest_beneish and latest_beneish.verdict in ["LIKELY_MANIPULATOR", "GREY_ZONE"]:
            weight = 100 if latest_beneish.verdict == "LIKELY_MANIPULATOR" else 75
            concerns_candidates.append((weight, f"Beneish M-Score indicates {latest_beneish.verdict.replace('_', ' ').title()}"))
        elif latest_beneish and latest_beneish.verdict == "SAFE_ZONE":
            strengths_candidates.append((50, "Beneish M-Score indicates SAFE ZONE (no significant signs of earnings manipulation)."))
            
        if latest_altman and latest_altman.verdict in ["DISTRESS_ZONE", "GREY_ZONE"]:
            weight = 100 if latest_altman.verdict == "DISTRESS_ZONE" else 75
            concerns_candidates.append((weight, f"Altman Z-Score indicates {latest_altman.verdict.replace('_', ' ').title()}"))
        elif latest_altman and latest_altman.verdict == "SAFE_ZONE":
            strengths_candidates.append((50, "Altman Z-Score indicates SAFE ZONE (strong financial health and low bankruptcy risk)."))

        # Pull benchmark
        if self.benchmark:
            for metric, data in self.benchmark.metrics.items():
                if data.relative_position == "ABOVE_AVERAGE":
                    strengths_candidates.append((70, f"{metric} is ABOVE AVERAGE compared to peers (Company: {data.company_value}, Sector Median: {data.sector_median})."))
                elif data.relative_position == "SIGNIFICANTLY_BELOW_AVERAGE":
                    concerns_candidates.append((70, f"{metric} is SIGNIFICANTLY BELOW AVERAGE compared to peers (Company: {data.company_value}, Sector Median: {data.sector_median})."))
                elif data.relative_position == "BELOW_AVERAGE":
                    concerns_candidates.append((40, f"{metric} is BELOW AVERAGE compared to peers."))

        # Pull trends
        if mod_status.module_2_trend_analysis == "COMPLETE":
            for trend in self.trends:
                if trend.trend_direction == "IMPROVING":
                    strengths_candidates.append((30, f"{trend.ratio_name} trend is IMPROVING."))
                elif trend.trend_direction == "DECLINING":
                    concerns_candidates.append((30, f"{trend.ratio_name} trend is DECLINING."))
                
                for sc in trend.sudden_changes:
                    if sc.classification == "SUDDEN_DETERIORATION":
                        concerns_candidates.append((60, f"Sudden deterioration in {trend.ratio_name} in year {sc.year} (magnitude: {sc.magnitude}%)."))
                    elif sc.classification == "SUDDEN_IMPROVEMENT":
                        strengths_candidates.append((60, f"Sudden improvement in {trend.ratio_name} in year {sc.year}."))

        # Add not meaningful as concerns
        for r in self.ratios:
            if r.status == "NOT_MEANINGFUL":
                concerns_candidates.append((50, f"{r.ratio_name} could not be computed: {r.reason}"))

        # Sort and take top 5
        # Sort karke sabse highest weight wale 5 Top Strengths aur 5 Top Concerns nikalte hain
        strengths_candidates.sort(key=lambda x: x[0], reverse=True)
        concerns_candidates.sort(key=lambda x: x[0], reverse=True)
        
        top_strengths = [s[1] for s in strengths_candidates[:5]]
        top_concerns = [c[1] for c in concerns_candidates[:5]]

        if not top_strengths:
            top_strengths.append("No significant quantitative financial strengths identified.")
        if not top_concerns:
            top_concerns.append("No significant quantitative financial concerns identified.")

        # Step 6.4: 5-Year Ratio Table
        # Frontend par show karne ke liye saare saalo ka data ek simple table format me bana rahe hain
        ratio_table = []
        grouped_ratios = {}
        for r in self.ratios:
            if r.ratio_name not in grouped_ratios:
                grouped_ratios[r.ratio_name] = {}
            grouped_ratios[r.ratio_name][r.fiscal_year] = {"value": r.value, "status": r.status}

        for name, years in grouped_ratios.items():
            row = {"ratio_name": name}
            row.update({str(y): val["value"] if val["status"] == "COMPUTED" else val["status"] for y, val in years.items()})
            
            # Find trend
            t = next((tr for tr in self.trends if tr.ratio_name == name), None)
            row["trend"] = t.trend_direction if t else "INSUFFICIENT_DATA"
            
            ratio_table.append(row)

        # Step 6.5: Data Limitations
        ratios_blocked = list({r.ratio_name for r in self.ratios if r.status == "MISSING"})
        ratios_suppressed_na = list({r.ratio_name for r in self.ratios if r.status == "NOT_APPLICABLE"})
        ratios_suppressed_nm = list({r.ratio_name for r in self.ratios if r.status == "NOT_MEANINGFUL"})
        
        b_missing = latest_beneish.missing_variables if latest_beneish else []
        a_status = latest_altman.verdict if latest_altman else "NOT_COMPUTED"
        a_cap = latest_altman.market_cap_version if latest_altman else None
        
        # Override a_status if NOT_APPLICABLE
        if latest_altman and latest_altman.verdict == "NOT_APPLICABLE":
            a_status = "NOT_APPLICABLE"

        limitations = DataLimitations(
            missing_fields=missing_names,
            ratios_blocked=ratios_blocked,
            ratios_suppressed_not_applicable=ratios_suppressed_na,
            ratios_suppressed_not_meaningful=ratios_suppressed_nm,
            beneish_missing_variables=b_missing,
            altman_market_cap_source=a_cap,
            altman_status=a_status
        )

        b_dict = latest_beneish.model_dump() if latest_beneish else None
        a_dict = latest_altman.model_dump() if latest_altman else None
        an_dict = self.anomaly.model_dump() if self.anomaly else None
        bm_dict = self.benchmark.model_dump() if self.benchmark else None
        tr_dict = [t.model_dump() for t in self.trends]

        return QOESummary(
            ticker=self.ticker,
            company_name=self.company_name,
            run_id=self.run_id,
            analysis_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            modules_status=mod_status,
            earnings_quality_score=score,
            earnings_quality_label=label,
            top_strengths=top_strengths,
            top_concerns=top_concerns,
            beneish_m_score_latest=b_dict,
            altman_z_score_latest=a_dict,
            anomaly_flags=an_dict,
            sector_benchmark=bm_dict,
            five_year_ratio_table=ratio_table,
            trend_analysis=tr_dict,
            data_limitations=limitations
        )
