from typing import Any, Literal

from pydantic import BaseModel, Field


class TickerResolutionResult(BaseModel):
    """Result of resolving a ticker to a CIK via SEC EDGAR.
    # Ye model Ingestion phase me use hota hai check karne ke liye ki company ka Ticker valid hai ya nahi,
    # aur usse SEC ka unique CIK number nikalne ke liye.
    """
    found: bool
    cik: str | None = None
    company_name: str | None = None
    ticker_matched: str | None = None


class FilingRecord(BaseModel):
    """A single SEC filing record from the submissions list."""
    form: str
    filing_date: str
    accession_number: str


class CompanyIdentity(BaseModel):
    """Core company metadata extracted from the SEC submissions endpoint.
    # Ye company ki basic details store karta hai jaise naam, CIK, Industry Code (SIC) etc.
    """
    company_name: str
    cik: str
    sic_code: str
    industry_name: str
    exchange: str | None = None
    state_of_incorp: str | None = None
    fiscal_year_end: str
    fiscal_year_end_month: int


class CompanySubmissionsResult(BaseModel):
    """The result of fetching a company's submission history."""
    company_identity: CompanyIdentity
    filings: list[FilingRecord]


class SelectedFilings(BaseModel):
    """The specific filings selected for ingestion in Phase 1."""
    ten_k: list[FilingRecord] = Field(default_factory=list)
    eight_k: list[FilingRecord] = Field(default_factory=list)
    def_14a: FilingRecord | None = None
    ten_q: list[FilingRecord] = Field(default_factory=list)


class IngestionSummaryError(BaseModel):
    """Structured error summary for when ingestion fails cleanly (e.g. invalid ticker)."""
    run_id: str
    status: Literal["ERROR"]
    reason: str
    ticker_provided: str
    module_status: dict[str, str]
    ingestion_timestamp: str


EIGHT_K_EVENT_TYPES = {
    "1.01": "Material Definitive Agreement",
    "1.02": "Termination of Material Agreement",
    "1.03": "Bankruptcy or Receivership",
    "2.01": "Acquisition or Disposition of Assets (M&A)",
    "2.02": "Results of Operations (Earnings Release)",
    "2.06": "Material Impairments",
    "3.01": "Rating Agency Actions (Credit Downgrade or Upgrade)",
    "3.02": "Unregistered Sales of Equity Securities",
    "4.01": "Changes in Registrant's Certifying Accountant (Auditor Change)",
    "4.02": "Non-Reliance on Financial Statements (Restatement Warning)",
    "5.01": "Changes in Control",
    "5.02": "Departure or Appointment of Directors or Officers (CEO/CFO Change)",
    "5.03": "Amendments to Articles of Incorporation",
    "7.01": "Regulation FD Disclosure (Guidance Update)",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits"
}

class ChromaChunkMetadata(BaseModel):
    """Metadata attached to every chunk stored in ChromaDB."""
    ticker: str
    company_name: str
    fiscal_year: str | None = None
    filing_type: str
    filing_date: str | None = None
    section_code: str | None = None
    section_name: str | None = None
    event_item: str | None = None
    event_type: str | None = None
    chunk_index: int
    total_chunks: int
    word_count: int | None = None
    
    # Phase 3 User File fields
    source: str | None = None
    filename: str | None = None
    priority: str | None = None
    upload_date: str | None = None


class AnnualFinancials(BaseModel):
    """A single fiscal year of financial data.
    # Ye sabse bada aur important model hai. Har saal ka pura Income Statement, Balance Sheet 
    # aur Cash Flow isme save hota hai. Ratio Engine isi data ka use karta hai.
    """
    fiscal_year: int
    
    # A. Income Statement
    revenue: float | None = None
    cost_of_revenue: float | None = None
    gross_profit: float | None = None
    sga_expense: float | None = None
    rd_expense: float | None = None
    operating_income: float | None = None
    interest_expense: float | None = None
    income_before_tax: float | None = None
    income_tax_expense: float | None = None
    net_income: float | None = None
    eps_basic: float | None = None
    eps_diluted: float | None = None
    non_operating_income: float | None = None
    
    # B. Balance Sheet
    total_assets: float | None = None
    current_assets: float | None = None
    cash_and_equivalents: float | None = None
    short_term_investments: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None
    ppe_net: float | None = None
    goodwill: float | None = None
    intangible_assets: float | None = None
    total_liabilities: float | None = None
    current_liabilities: float | None = None
    accounts_payable: float | None = None
    short_term_debt: float | None = None
    long_term_debt: float | None = None
    total_equity: float | None = None
    retained_earnings: float | None = None
    shares_outstanding: float | None = None
    weighted_avg_shares: float | None = None
    
    # C. Cash Flow
    operating_cash_flow: float | None = None
    capital_expenditures: float | None = None
    depreciation_and_amortization: float | None = None
    free_cash_flow: float | None = None
    investing_cash_flow: float | None = None
    financing_cash_flow: float | None = None
    dividends_paid: float | None = None
    stock_buybacks: float | None = None
    
    # D. Derived
    ebitda: float | None = None
    net_debt: float | None = None
    working_capital: float | None = None
    
    # E. Market Data
    stock_price_fy_end: float | None = None
    market_cap: float | None = None

class FinancialValueMetadata(BaseModel):
    source: str
    xbrl_tag: str | None = None
    computation_method: str | None = None

class CompanyFinancialHistory(BaseModel):
    """The full extracted financial history and market profile."""
    ticker: str
    cik: str
    company_name: str
    beta: float | None = None
    annual_data: list[AnnualFinancials]
    field_metadata: dict[str, dict[int, FinancialValueMetadata]] = Field(default_factory=dict)

class MissingFieldLog(BaseModel):
    field: str
    years: list[int]
    impact: str
    criticality: str
    reason: str

class Phase5Result(BaseModel):
    financial_history: CompanyFinancialHistory
    warnings: list[str]
    missing_fields: list[MissingFieldLog]

class IngestionSummaryError(BaseModel):
    run_id: str
    status: str
    reason: str
    ticker_provided: str
    module_status: dict[str, str]
    ingestion_timestamp: str

class FieldCoverageSummary(BaseModel):
    total_fields: int
    fields_with_data: int
    fields_missing: int
    fields_computed: int

class VectorDatabaseStats(BaseModel):
    total_chunks: int
    chunks_from_10k: int
    chunks_from_10q: int = 0
    chunks_from_8k: int
    chunks_from_proxy: int
    chunks_from_user_file: int
    filings_processed: dict[str, Any]

class IngestionSummary(BaseModel):
    run_id: str
    status: str
    module_status: dict[str, str]
    company_identity: CompanyIdentity
    financial_data_coverage: dict[str, Any]
    field_coverage_summary: FieldCoverageSummary
    missing_critical_fields: list[MissingFieldLog]
    vector_database_stats: VectorDatabaseStats
    field_metadata: dict[str, dict[int, FinancialValueMetadata]] = Field(default_factory=dict)
    warnings: list[str]
    errors: list[str]
    ingestion_timestamp: str
    ingestion_duration_seconds: int

class RatioRecord(BaseModel):
    """A computed financial ratio for a specific fiscal year.
    # Ye Ratio Engine (Module 1) ka output record hai. Har calculated ratio 
    # isme save hota hai apne formula aur status (e.g. COMPUTED ya MISSING) ke sath.
    """
    ratio_name: str
    fiscal_year: int
    value: float | None = None
    unit: str
    formula: str
    inputs_used: dict[str, float | None]
    status: str
    reason: str | None = None

class SuddenChange(BaseModel):
    year: int
    prior_value: float
    current_value: float
    magnitude: float
    classification: str

class RatioTrend(BaseModel):
    ratio_name: str
    trend_direction: str
    trend_confidence: str
    momentum: str
    sudden_changes: list[SuddenChange]
    average_value: float | None
    std_deviation: float | None
    year_values: dict[str, float]
    linear_slope: float | None
    data_years: int

class BeneishVariable(BaseModel):
    value: float | None
    threshold: float
    flag: bool

class BeneishScore(BaseModel):
    model: str = "Beneish M-Score"
    fiscal_year_pair: str | None = None
    variables: dict[str, BeneishVariable] | None = None
    m_score: float | None = None
    verdict: str
    individual_flags: list[str] = []
    missing_variables: list[str] = []
    reason: str | None = None
    note: str | None = None

class AltmanScore(BaseModel):
    model: str = "Altman Z-Score"
    version: str | None = None
    fiscal_year: int | None = None
    variables: dict[str, float] | None = None
    z_score: float | None = None
    verdict: str
    market_cap_version: str | None = None
    reason: str | None = None
    note: str | None = None

class FraudDistressOutput(BaseModel):
    beneish_scores: list[BeneishScore]
    altman_scores: list[AltmanScore]

class AnomalyFlag(BaseModel):
    flag_id: str
    severity: str
    category: str
    title: str
    description: str
    supporting_data: dict[str, Any]
    trend: str | None = None
    first_appeared: int | None = None

class AnomalyOutput(BaseModel):
    total_flags: int
    critical: int
    high: int
    medium: int
    low: int
    rules_skipped_missing_data: list[str]
    flags: list[AnomalyFlag]

class FrameDataPoint(BaseModel):
    cik: int
    entity_name: str
    ticker: str | None = None
    value: float

class FramesResponse(BaseModel):
    tag: str
    unit: str
    period: str
    status: str
    data: list[FrameDataPoint]
    error_message: str | None = None

class TickersResponse(BaseModel):
    mapping: dict[str, str]

class BenchmarkMetric(BaseModel):
    company_value: float | None = None
    sector_median: float
    sector_mean: float
    company_percentile: int | None = None
    relative_position: str | None = None
    vs_median_delta: float | None = None
    note: str | None = None

class PeerInfo(BaseModel):
    cik: str
    entity_name: str
    revenue: float

class BenchmarkOutput(BaseModel):
    ticker: str
    sic_code: str
    industry: str
    benchmark_year: int
    peer_count: int
    top_peers: list[PeerInfo]
    metrics: dict[str, BenchmarkMetric]

class ModulesStatus(BaseModel):
    module_1_ratio_engine: str
    module_2_trend_analysis: str
    module_3_fraud_distress: str
    module_4_anomaly_detection: str
    module_5_sector_benchmark: str
    data_years: int
    data_depth_mode: str

class DataLimitations(BaseModel):
    missing_fields: list[str]
    ratios_blocked: list[str]
    ratios_suppressed_not_applicable: list[str]
    ratios_suppressed_not_meaningful: list[str]
    beneish_missing_variables: list[str]
    altman_market_cap_source: str | None
    altman_status: str

class QOESummary(BaseModel):
    ticker: str
    company_name: str
    run_id: str
    analysis_timestamp: str
    modules_status: ModulesStatus
    earnings_quality_score: int
    earnings_quality_label: str
    top_strengths: list[str]
    top_concerns: list[str]
    beneish_m_score_latest: dict | None
    altman_z_score_latest: dict | None
    anomaly_flags: dict | None
    sector_benchmark: dict | None
    five_year_ratio_table: list[dict]
    trend_analysis: list[dict]
    data_limitations: DataLimitations


class MarketIntelSummaryError(BaseModel):
    """Structured error summary for when the Market Intelligence agent fails."""
    run_id: str
    status: Literal["ERROR"]
    reason: str
    expected_path: str | None = None

class MarketIntelContext(BaseModel):
    """Data loaded during Pre-Processing to be used by subsequent modules.
    # Ye Market Intelligence Agent ke modules me company context (e.g. peers, industry) pass karne ke liye use hota hai.
    """
    run_id: str
    ticker: str
    company_name: str
    cik: str
    sic_code: str
    industry_name: str
    fiscal_year_end_month: int
    most_recent_fiscal_year: int
    is_sector_benchmark_partial: bool
    is_chromadb_reachable: bool
    top_peers: list[PeerInfo] = Field(default_factory=list)
    target_ratios: dict[str, Any] = Field(default_factory=dict)


# --- Agent 5: Memo Generation ---

class SectionPlanEntry(BaseModel):
    target_words: int
    depth: Literal["MINIMAL", "BRIEF", "STANDARD", "DEEP", "UNAVAILABLE"]

class MemoDocumentPlan(BaseModel):
    executive_summary: SectionPlanEntry
    company_overview: SectionPlanEntry
    financial_analysis: SectionPlanEntry
    sector_benchmarking: SectionPlanEntry
    market_context: SectionPlanEntry
    risk_assessment: SectionPlanEntry
    action_items: SectionPlanEntry
    recommendation: SectionPlanEntry

class MemoDataConfidence(BaseModel):
    executive_summary: Literal["HIGH", "MEDIUM", "LOW", "UNAVAILABLE"]
    company_overview: Literal["HIGH", "MEDIUM", "LOW", "UNAVAILABLE"]
    financial_analysis: Literal["HIGH", "MEDIUM", "LOW", "UNAVAILABLE"]
    sector_benchmarking: Literal["HIGH", "MEDIUM", "LOW", "UNAVAILABLE"]
    market_context: Literal["HIGH", "MEDIUM", "LOW", "UNAVAILABLE"]
    risk_assessment: Literal["HIGH", "MEDIUM", "LOW", "UNAVAILABLE"]
    recommendation: Literal["HIGH", "MEDIUM", "LOW", "UNAVAILABLE"]

class NumberLookupMetadata(BaseModel):
    value: float | int | None
    source_table: str
    source_key: str
    fiscal_year: str | None = None

class MemoPreProcessingResult(BaseModel):
    run_id: str
    status: Literal["COMPLETE", "ERROR"]
    reason: str | None = None
    market_intel_available: bool
    risk_assessment_available: bool
    libreoffice_available: bool

class MemoModule1Result(BaseModel):
    run_id: str
    status: Literal["COMPLETE", "ERROR"]
    template_variant: Literal["STANDARD", "DEAL_BREAKER_ALERT", "LIMITED_DATA"]
    template_sub_flags: list[str] = Field(default_factory=list)
    tone_profile: Literal["PROCEED", "CAUTION", "ENHANCED_DD", "AVOID"]
    data_confidence: MemoDataConfidence
    section_plan: MemoDocumentPlan


class ValidationMismatch(BaseModel):
    number_in_text: str
    matched_key: str
    source_value: str
    match: bool
    corrected_sentence: str | None = None

class MemoModule2Result(BaseModel):
    run_id: str
    status: Literal["COMPLETE", "ERROR"]
    executive_summary_text: str
    fallback_used: bool
    validation_mismatches_found: int
    validation_mismatches_corrected: int


class MemoModule3Result(BaseModel):
    run_id: str
    status: Literal["COMPLETE", "ERROR"]
    company_facts_table_text: str
    company_overview_narrative_text: str
    fallback_used: bool
    validation_mismatches_found: int
    validation_mismatches_corrected: int


class MemoModule4Result(BaseModel):
    run_id: str
    status: Literal["COMPLETE", "ERROR"]
    income_statement_table: str
    balance_sheet_table: str
    key_ratios_table: str
    fraud_distress_box: str
    anomaly_flags_summary: str
    profitability_narrative: str
    leverage_narrative: str
    liquidity_narrative: str
    cash_flow_narrative: str
    limitations_notice: str
    sections_failed_list: list[str]
    validation_mismatches_found: int
    validation_mismatches_corrected: int


class MemoModule5Result(BaseModel):
    run_id: str
    status: Literal["COMPLETE", "ERROR", "SKIPPED_UNAVAILABLE"]
    comps_table: str | None
    valuation_summary: str | None
    percentile_table: str | None
    competitive_narrative: str | None
    data_unavailable_disclosure: str | None
    fallback_used: bool
    validation_mismatches_found: int
    validation_mismatches_corrected: int


class MemoModule6Result(BaseModel):
    run_id: str
    status: Literal["COMPLETE", "ERROR", "SKIPPED_UNAVAILABLE"]
    macro_indicators_table: str | None
    news_sentiment_summary: str | None
    news_sentiment_narrative: str | None
    industry_overview_narrative: str | None
    data_unavailable_disclosure: str | None
    sections_failed_list: list[str]
    validation_mismatches_found: int
    validation_mismatches_corrected: int


class MemoModule7Result(BaseModel):
    run_id: str
    status: Literal["COMPLETE", "ERROR", "SKIPPED_UNAVAILABLE"]
    deal_breaker_box: str | None
    scorecard_table: str | None
    dimension_narratives: dict[str, str] | None
    top_risks_table: str | None
    data_unavailable_disclosure: str | None
    sections_failed_list: list[str]
    validation_mismatches_found: int
    validation_mismatches_corrected: int


class MemoModule8Result(BaseModel):
    run_id: str
    status: Literal["COMPLETE", "ERROR", "SKIPPED_UNAVAILABLE"]
    intro_narrative: str | None
    action_items_tables: str | None
    data_unavailable_disclosure: str | None
    fallback_used: bool


class MemoModule9Result(BaseModel):
    run_id: str
    status: Literal["COMPLETE", "ERROR"]
    recommendation_narrative: str
    facts_block_payload: dict[str, Any]
    fallback_used: bool
    validation_mismatches_found: int
    validation_mismatches_corrected: int


class MemoModule10Result(BaseModel):
    run_id: str
    status: Literal["COMPLETE"]
    appendix_a_financials: str
    appendix_b_risk_evidence: str
    appendix_c_methodology: str
    appendix_d_anomalies: str


class MemoModule11Result(BaseModel):
    run_id: str
    status: Literal["COMPLETE"]
    total_claims_checked: int
    regex_pass_claims: int
    llm_supplemental_claims: int
    verified: int
    mismatch_corrected: int
    not_found_removed: int
    sections_excluded_placeholder: list[str]
    validation_passed: str
    final_validated_sections: dict[str, str]


class MemoModule12Result(BaseModel):
    run_id: str
    status: Literal["COMPLETE"]
    docx_document: Any  # docx.Document object


class MemoModule13Result(BaseModel):
    run_id: str
    status: Literal["COMPLETE"]
    docx_path: str
    pdf_path: str | None
    json_cert_path: str
