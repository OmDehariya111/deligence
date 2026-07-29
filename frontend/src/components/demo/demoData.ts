import {
  Database,
  Calculator,
  Globe2,
  ShieldAlert,
  FileText,
  type LucideIcon,
} from "lucide-react";

export type AgentStep = {
  id: string;
  name: string;
  icon: LucideIcon;
  statuses: string[];
};

/** Pipeline definition — swap `statuses` for live server events later. */
export const agentSteps: AgentStep[] = [
  {
    id: "ingestion",
    name: "Ingestion Agent",
    icon: Database,
    statuses: [
      "Resolving ticker to SEC CIK…",
      "Fetching 5 years of XBRL company facts…",
      "Indexing 10-K, 8-K and proxy filings…",
    ],
  },
  {
    id: "analysis",
    name: "Analysis Agent",
    icon: Calculator,
    statuses: [
      "Computing 36 financial ratios…",
      "Running Beneish M-Score…",
      "Running Altman Z-Score…",
      "Scanning 15 anomaly patterns…",
    ],
  },
  {
    id: "market",
    name: "Market Intelligence Agent",
    icon: Globe2,
    statuses: [
      "Identifying named competitors…",
      "Building LTM trading comps table…",
      "Scoring live news sentiment…",
    ],
  },
  {
    id: "risk",
    name: "Risk Assessment Agent",
    icon: ShieldAlert,
    statuses: [
      "Scoring six risk dimensions…",
      "Checking eight deal-breaker conditions…",
    ],
  },
  {
    id: "memo",
    name: "Memo Generation Agent",
    icon: FileText,
    statuses: [
      "Drafting investment memorandum…",
      "Cross-checking every figure against source…",
      "Finalising citations…",
    ],
  },
];

export type RiskLevel = "low" | "medium" | "high";

export type RiskRow = {
  dimension: string;
  score: number; // 0-10, higher = riskier
  level: RiskLevel;
  note: string;
};

export type AnomalyFlag = {
  title: string;
  severity: RiskLevel;
  detail: string;
};

export type DemoReport = {
  ticker: string;
  company: string;
  sector: string;
  stance: string;
  generatedAt: string;
  summary: string[];
  metrics: { label: string; value: string }[];
  risks: RiskRow[];
  anomalies: AnomalyFlag[];
};

const reports: Record<string, DemoReport> = {
  AAPL: {
    ticker: "AAPL",
    company: "Apple Inc.",
    sector: "Technology · Consumer Electronics",
    stance: "CAUTION",
    generatedAt: "FY2021–FY2025 filings · 4m 12s runtime",
    summary: [
      "Apple Inc. generates industry-leading operating margins (30.1% LTM) on a revenue base of $391.0B, with free cash flow conversion above 100% of net income in four of the last five fiscal years [10-K FY2025, p.31].",
      "Deterministic screens return a Beneish M-Score of −2.71 (below the −1.78 manipulation threshold) and an Altman Z-Score of 6.4, both consistent with low accounting-manipulation and low distress probability [computed, XBRL company facts].",
      "The principal reservation is concentration: hardware remains 74% of revenue and Greater China contributed 17% of net sales while declining year over year, alongside unresolved antitrust and App Store regulatory exposure [10-K FY2025, Item 1A].",
    ],
    metrics: [
      { label: "Revenue (LTM)", value: "$391.0B" },
      { label: "Operating margin", value: "30.1%" },
      { label: "Beneish M-Score", value: "−2.71" },
      { label: "Altman Z-Score", value: "6.4" },
    ],
    risks: [
      { dimension: "Financial", score: 2.1, level: "low", note: "Net cash position, strong FCF conversion" },
      { dimension: "Market", score: 6.4, level: "medium", note: "China exposure, hardware cycle sensitivity" },
      { dimension: "Operational", score: 3.2, level: "low", note: "Concentrated supply chain, mitigated by scale" },
      { dimension: "Legal & Regulatory", score: 7.8, level: "high", note: "App Store antitrust across US and EU" },
      { dimension: "Management & Governance", score: 2.4, level: "low", note: "Stable tenure, no restatements on record" },
      { dimension: "ESG", score: 4.6, level: "medium", note: "Supplier labour audits flagged in disclosures" },
    ],
    anomalies: [
      { title: "Gross margin expansion outpacing revenue growth", severity: "medium", detail: "Services mix shift explains 240bps of the 310bps delta; residual unexplained." },
      { title: "Days sales outstanding drift", severity: "low", detail: "DSO up 4.1 days YoY, still well inside sector norms." },
      { title: "Regulatory contingency disclosure expanded", severity: "high", detail: "Item 1A legal proceedings language broadened materially versus prior year." },
    ],
  },
};

const fallback = (ticker: string): DemoReport => ({
  ...reports.AAPL,
  ticker,
  company: `${ticker} Holdings, Inc.`,
  sector: "US Public Equity · Sample Data",
});

/** Replace with a server call once the pipeline API is wired. */
export function getDemoReport(ticker: string): DemoReport {
  return reports[ticker] ?? fallback(ticker);
}

export const exampleTickers = ["AAPL", "MSFT", "TSLA", "NVDA"];

export const riskStyles: Record<RiskLevel, { text: string; bar: string; chip: string; label: string }> = {
  low: {
    text: "text-primary",
    bar: "bg-primary",
    chip: "border-primary/40 bg-primary/10 text-primary",
    label: "Low",
  },
  medium: {
    text: "text-warn",
    bar: "bg-warn",
    chip: "border-warn/40 bg-warn/10 text-warn",
    label: "Medium",
  },
  high: {
    text: "text-risk",
    bar: "bg-risk",
    chip: "border-risk/40 bg-risk/10 text-risk",
    label: "High",
  },
};