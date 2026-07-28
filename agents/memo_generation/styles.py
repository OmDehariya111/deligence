"""
Module:  styles.py
Agent:   Memo Generation Agent
Purpose: Complete CSS design system for the investment memo HTML report.
         Contains all colors, typography, layouts, chart styling, and print rules.
         Uses Base64-embedded Inter and JetBrains Mono fonts for offline rendering.
Inputs:  None (pure CSS string generation).
Outputs: CSS string to embed in the HTML <style> tag.
"""


def get_base_css() -> str:
    """Return the complete CSS design system for the investment memo.

    This includes:
    - Base64-embedded fonts (Inter + JetBrains Mono) for offline rendering
    - Color palette (Navy, Emerald, Amber, Orange, Crimson)
    - Typography hierarchy (H1-H4, body, labels)
    - Table styles (striped, bordered, responsive)
    - Card / Badge / Alert components
    - Chart container styles
    - Section layout and spacing
    - Print-specific rules (@media print)
    - Cover page styling
    - Responsive grid utilities
    """
    # Load Base64 font data
    try:
        from agents.memo_generation.assets.font_data import (
            INTER_REGULAR_B64, INTER_BOLD_B64, JB_MONO_REGULAR_B64
        )
    except ImportError:
        INTER_REGULAR_B64 = ""
        INTER_BOLD_B64 = ""
        JB_MONO_REGULAR_B64 = ""

    # Build @font-face declarations
    font_faces = ""
    if INTER_REGULAR_B64:
        font_faces += f"""
@font-face {{
    font-family: 'Inter';
    font-style: normal;
    font-weight: 400;
    font-display: swap;
    src: url(data:font/woff2;base64,{INTER_REGULAR_B64}) format('woff2');
}}
"""
    if INTER_BOLD_B64:
        font_faces += f"""
@font-face {{
    font-family: 'Inter';
    font-style: normal;
    font-weight: 700;
    font-display: swap;
    src: url(data:font/woff2;base64,{INTER_BOLD_B64}) format('woff2');
}}
"""
    if JB_MONO_REGULAR_B64:
        font_faces += f"""
@font-face {{
    font-family: 'JetBrains Mono';
    font-style: normal;
    font-weight: 400;
    font-display: swap;
    src: url(data:font/woff2;base64,{JB_MONO_REGULAR_B64}) format('woff2');
}}
"""

    css_template = """
/* ============================================================
   DELIGENX INVESTMENT MEMO — DESIGN SYSTEM
   ============================================================ */

/* --- EMBEDDED FONTS (Base64, works offline) --- */
__FONT_FACES__

/* --- CSS VARIABLES (Design Tokens) --- */
:root {
    /* Primary Palette */
    --color-primary: #1B2A4A;
    --color-primary-light: #2D4A7A;
    --color-secondary: #3A5A8C;
    --color-accent: #4A90D9;

    /* Semantic Colors */
    --color-success: #10B981;
    --color-success-light: #D1FAE5;
    --color-success-dark: #059669;
    --color-warning: #F59E0B;
    --color-warning-light: #FEF3C7;
    --color-warning-dark: #D97706;
    --color-danger: #F97316;
    --color-danger-light: #FFEDD5;
    --color-danger-dark: #EA580C;
    --color-critical: #EF4444;
    --color-critical-light: #FEE2E2;
    --color-critical-dark: #DC2626;

    /* Neutral Palette */
    --color-bg: #F8FAFC;
    --color-bg-card: #FFFFFF;
    --color-bg-alt: #F1F5F9;
    --color-text: #1E293B;
    --color-text-secondary: #64748B;
    --color-text-muted: #94A3B8;
    --color-border: #E2E8F0;
    --color-border-light: #F1F5F9;

    /* Typography */
    --font-primary: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --font-mono: 'JetBrains Mono', 'Cascadia Code', 'Fira Code', monospace;

    /* Spacing */
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 16px;
    --space-lg: 24px;
    --space-xl: 32px;
    --space-2xl: 48px;
    --space-3xl: 64px;

    /* Border Radius */
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 12px;
    --radius-xl: 16px;

    /* Shadows */
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
    --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -1px rgba(0,0,0,0.04);
    --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -2px rgba(0,0,0,0.03);
    --shadow-xl: 0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04);
}

/* --- RESET & BASE --- */
*, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

html {
    font-size: 14px;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

body {
    font-family: var(--font-primary);
    color: var(--color-text);
    background-color: var(--color-bg);
    line-height: 1.7;
    min-height: 100vh;
}

/* --- TYPOGRAPHY --- */
h1, h2, h3, h4, h5, h6 {
    font-family: var(--font-primary);
    font-weight: 700;
    color: var(--color-primary);
    line-height: 1.3;
    margin-bottom: var(--space-md);
}

h1 { font-size: 2rem; font-weight: 800; }
h2 {
    font-size: 1.5rem;
    font-weight: 700;
    padding-bottom: var(--space-sm);
    border-bottom: 3px solid var(--color-accent);
    margin-top: var(--space-3xl);
    margin-bottom: var(--space-lg);
}
h3 {
    font-size: 1.2rem;
    font-weight: 600;
    color: var(--color-secondary);
    margin-top: var(--space-xl);
    margin-bottom: var(--space-md);
}
h4 {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--color-text);
    margin-top: var(--space-lg);
    margin-bottom: var(--space-sm);
}

p {
    margin-bottom: var(--space-md);
    line-height: 1.8;
    color: var(--color-text);
}

.text-muted { color: var(--color-text-muted); }
.text-secondary { color: var(--color-text-secondary); }
.text-small { font-size: 0.85rem; }
.text-mono { font-family: var(--font-mono); }
.text-center { text-align: center; }
.text-right { text-align: right; }
.fw-bold { font-weight: 700; }
.fw-semibold { font-weight: 600; }
.fw-medium { font-weight: 500; }

/* --- LAYOUT --- */
.memo-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--space-xl) var(--space-2xl);
    background: var(--color-bg-card);
}

.section {
    margin-bottom: var(--space-3xl);
    page-break-inside: avoid;
}

.section-header {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    margin-bottom: var(--space-lg);
}

.section-number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    background: var(--color-primary);
    color: white;
    font-size: 0.85rem;
    font-weight: 700;
    border-radius: 50%;
    flex-shrink: 0;
}

/* --- GRID SYSTEM --- */
.grid-2 {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-lg);
}

.grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-lg);
}

.grid-4 {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-md);
}

/* --- CARDS --- */
.card {
    background: var(--color-bg-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-lg);
    box-shadow: var(--shadow-sm);
    transition: box-shadow 0.2s ease;
}

.card:hover {
    box-shadow: var(--shadow-md);
}

.card-header {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--color-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: var(--space-sm);
}

.card-value {
    font-size: 1.8rem;
    font-weight: 800;
    font-family: var(--font-mono);
    color: var(--color-primary);
    line-height: 1.2;
}

.card-value.small {
    font-size: 1.3rem;
}

.card-footer {
    font-size: 0.8rem;
    color: var(--color-text-muted);
    margin-top: var(--space-sm);
}

/* --- BADGES --- */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 100px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    white-space: nowrap;
}

.badge-low, .badge-proceed, .badge-safe, .badge-passed, .badge-improving {
    background: var(--color-success-light);
    color: var(--color-success-dark);
}

.badge-medium, .badge-caution, .badge-grey {
    background: var(--color-warning-light);
    color: var(--color-warning-dark);
}

.badge-high, .badge-concerns {
    background: var(--color-danger-light);
    color: var(--color-danger-dark);
}

.badge-critical, .badge-avoid, .badge-distress, .badge-failed, .badge-deteriorating {
    background: var(--color-critical-light);
    color: var(--color-critical-dark);
}

.badge-info {
    background: #DBEAFE;
    color: #1D4ED8;
}

.badge-neutral, .badge-stable {
    background: var(--color-bg-alt);
    color: var(--color-text-secondary);
}

.badge-large {
    padding: 6px 16px;
    font-size: 0.85rem;
}

/* --- VERDICT BOX --- */
.verdict-box {
    border-radius: var(--radius-xl);
    padding: var(--space-xl);
    margin-bottom: var(--space-xl);
    text-align: center;
    box-shadow: var(--shadow-lg);
}

.verdict-box.low {
    background: linear-gradient(135deg, #D1FAE5 0%, #A7F3D0 100%);
    border: 2px solid var(--color-success);
}

.verdict-box.medium {
    background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
    border: 2px solid var(--color-warning);
}

.verdict-box.high {
    background: linear-gradient(135deg, #FFEDD5 0%, #FED7AA 100%);
    border: 2px solid var(--color-danger);
}

.verdict-box.critical {
    background: linear-gradient(135deg, #FEE2E2 0%, #FECACA 100%);
    border: 2px solid var(--color-critical);
}

.verdict-score {
    font-size: 3.5rem;
    font-weight: 900;
    font-family: var(--font-mono);
    line-height: 1;
    margin-bottom: var(--space-sm);
}

.verdict-label {
    font-size: 1.2rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* --- TABLES --- */
.table-container {
    overflow-x: auto;
    margin-bottom: var(--space-lg);
    border-radius: var(--radius-md);
    border: 1px solid var(--color-border);
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
}

thead th {
    background: var(--color-primary);
    color: white;
    padding: 10px 12px;
    text-align: left;
    font-weight: 600;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    white-space: nowrap;
    position: sticky;
    top: 0;
}

tbody td {
    padding: 8px 12px;
    border-bottom: 1px solid var(--color-border-light);
    vertical-align: middle;
}

tbody tr:nth-child(even) {
    background: var(--color-bg-alt);
}

tbody tr:hover {
    background: #E8F0FE;
}

/* Numeric cells */
td.num, th.num {
    text-align: right;
    font-family: var(--font-mono);
    font-size: 0.83rem;
    font-weight: 500;
}

td.positive { color: var(--color-success-dark); }
td.negative { color: var(--color-critical); }

/* Compact table variant */
table.compact td, table.compact th {
    padding: 6px 10px;
    font-size: 0.8rem;
}

/* Comps table (IB style) */
table.comps-table thead th {
    background: #1B2A4A;
    font-size: 0.7rem;
    padding: 8px 8px;
}

table.comps-table td {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    text-align: right;
    padding: 6px 8px;
}

table.comps-table td:first-child {
    text-align: left;
    font-family: var(--font-primary);
    font-weight: 600;
}

table.comps-table tr.target-row {
    background: #EBF5FF !important;
    font-weight: 700;
}

table.comps-table tr.median-row {
    background: #F0FDF4 !important;
    font-weight: 600;
    border-top: 2px solid var(--color-primary);
}

/* --- TRAFFIC LIGHTS --- */
.traffic-lights {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-md);
}

.traffic-light {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-md);
    background: var(--color-bg-alt);
    border: 1px solid var(--color-border);
    font-size: 0.85rem;
}

.traffic-light .indicator {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    flex-shrink: 0;
}

.traffic-light .indicator.green { background: var(--color-success); }
.traffic-light .indicator.red { background: var(--color-critical); }
.traffic-light .indicator.yellow { background: var(--color-warning); }

/* --- HEAT MAP --- */
.heatmap-grid {
    display: grid;
    grid-template-columns: 140px repeat(4, 1fr);
    gap: 2px;
    margin-bottom: var(--space-lg);
}

.heatmap-cell {
    padding: 10px 8px;
    text-align: center;
    font-size: 0.8rem;
    font-weight: 600;
    border-radius: var(--radius-sm);
}

.heatmap-cell.header {
    background: var(--color-primary);
    color: white;
    font-size: 0.7rem;
    text-transform: uppercase;
}

.heatmap-cell.row-label {
    background: var(--color-bg-alt);
    color: var(--color-primary);
    text-align: left;
    font-size: 0.8rem;
}

.heatmap-cell.low { background: #D1FAE5; color: #065F46; }
.heatmap-cell.medium { background: #FEF3C7; color: #92400E; }
.heatmap-cell.high { background: #FFEDD5; color: #9A3412; }
.heatmap-cell.critical { background: #FEE2E2; color: #991B1B; }
.heatmap-cell.active {
    box-shadow: inset 0 0 0 3px var(--color-primary);
    font-weight: 800;
}

/* --- CHART CONTAINERS --- */
.chart-container {
    position: relative;
    margin: var(--space-lg) 0;
    padding: var(--space-md);
    background: var(--color-bg-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
}

.chart-container canvas {
    max-height: 400px;
}

.chart-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--color-primary);
    margin-bottom: var(--space-md);
    text-align: center;
}

/* --- ALERTS / CALLOUTS --- */
.callout {
    padding: var(--space-md) var(--space-lg);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-lg);
    border-left: 4px solid;
    font-size: 0.9rem;
}

.callout-info {
    background: #EFF6FF;
    border-color: #3B82F6;
    color: #1E40AF;
}

.callout-success {
    background: var(--color-success-light);
    border-color: var(--color-success);
    color: #065F46;
}

.callout-warning {
    background: var(--color-warning-light);
    border-color: var(--color-warning);
    color: #92400E;
}

.callout-danger {
    background: var(--color-critical-light);
    border-color: var(--color-critical);
    color: #991B1B;
}

/* --- COVER PAGE --- */
.cover-page {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    background: linear-gradient(135deg, #1B2A4A 0%, #2D4A7A 50%, #3A5A8C 100%);
    color: white;
    padding: var(--space-3xl);
    page-break-after: always;
    position: relative;
    overflow: hidden;
}

.cover-page::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -50%;
    width: 100%;
    height: 100%;
    background: radial-gradient(circle, rgba(74,144,217,0.15) 0%, transparent 70%);
    pointer-events: none;
}

.cover-page::after {
    content: '';
    position: absolute;
    bottom: -50%;
    left: -50%;
    width: 100%;
    height: 100%;
    background: radial-gradient(circle, rgba(16,185,129,0.1) 0%, transparent 70%);
    pointer-events: none;
}

.cover-logo {
    width: 100px;
    height: 100px;
    background: rgba(255,255,255,0.15);
    border-radius: var(--radius-xl);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2.5rem;
    font-weight: 900;
    font-family: var(--font-mono);
    margin-bottom: var(--space-xl);
    border: 2px solid rgba(255,255,255,0.3);
    backdrop-filter: blur(10px);
    position: relative;
    z-index: 1;
}

.cover-title {
    font-size: 2.8rem;
    font-weight: 900;
    letter-spacing: -1px;
    margin-bottom: var(--space-sm);
    position: relative;
    z-index: 1;
}

.cover-subtitle {
    font-size: 1.3rem;
    font-weight: 300;
    opacity: 0.9;
    margin-bottom: var(--space-3xl);
    letter-spacing: 2px;
    text-transform: uppercase;
    position: relative;
    z-index: 1;
}

.cover-meta {
    display: grid;
    grid-template-columns: repeat(3, auto);
    gap: var(--space-xl);
    font-size: 0.9rem;
    opacity: 0.8;
    position: relative;
    z-index: 1;
}

.cover-meta-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.cover-meta-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    opacity: 0.7;
}

.cover-meta-value {
    font-family: var(--font-mono);
    font-weight: 600;
}

.cover-confidential {
    position: absolute;
    bottom: var(--space-xl);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    opacity: 0.5;
    z-index: 1;
}

/* --- SEPARATOR / DIVIDER --- */
.divider {
    height: 1px;
    background: var(--color-border);
    margin: var(--space-xl) 0;
}

.divider-thick {
    height: 3px;
    background: linear-gradient(90deg, var(--color-primary), var(--color-accent), transparent);
    margin: var(--space-2xl) 0;
}

/* --- VERIFICATION BADGE --- */
.verification-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-md);
    padding: var(--space-lg) var(--space-xl);
    background: linear-gradient(135deg, #D1FAE5 0%, #A7F3D0 100%);
    border: 2px solid var(--color-success);
    border-radius: var(--radius-xl);
    margin: var(--space-xl) 0;
}

.verification-badge .checkmark {
    font-size: 2.5rem;
}

.verification-badge .count {
    font-size: 2rem;
    font-weight: 900;
    font-family: var(--font-mono);
    color: var(--color-success-dark);
}

.verification-badge .label {
    font-size: 1rem;
    font-weight: 600;
    color: #065F46;
}

/* --- FOOTBALL FIELD (VALUATION CHART) --- */
.football-field {
    margin: var(--space-lg) 0;
}

.ff-row {
    display: grid;
    grid-template-columns: 120px 1fr 80px;
    align-items: center;
    gap: var(--space-md);
    margin-bottom: var(--space-sm);
    font-size: 0.85rem;
}

.ff-label {
    font-weight: 600;
    color: var(--color-primary);
}

.ff-bar-container {
    position: relative;
    height: 28px;
    background: var(--color-bg-alt);
    border-radius: var(--radius-sm);
    overflow: visible;
}

.ff-bar {
    position: absolute;
    height: 100%;
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 600;
    color: white;
    font-family: var(--font-mono);
}

.ff-current-line {
    position: absolute;
    top: -4px;
    bottom: -4px;
    width: 3px;
    background: var(--color-critical);
    border-radius: 2px;
    z-index: 10;
}

.ff-current-label {
    position: absolute;
    top: -20px;
    font-size: 0.65rem;
    font-weight: 700;
    color: var(--color-critical);
    white-space: nowrap;
    transform: translateX(-50%);
}

.ff-value {
    font-family: var(--font-mono);
    font-weight: 600;
    font-size: 0.8rem;
    text-align: right;
}

/* --- TABLE OF CONTENTS --- */
.toc {
    background: var(--color-bg-alt);
    border-radius: var(--radius-lg);
    padding: var(--space-xl);
    margin-bottom: var(--space-2xl);
}

.toc-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--color-primary);
    margin-bottom: var(--space-md);
}

.toc-list {
    list-style: none;
    columns: 2;
    column-gap: var(--space-xl);
}

.toc-list li {
    padding: 4px 0;
    font-size: 0.85rem;
    break-inside: avoid;
}

.toc-list li a {
    color: var(--color-text);
    text-decoration: none;
    display: flex;
    align-items: center;
    gap: var(--space-sm);
}

.toc-list li a:hover {
    color: var(--color-accent);
}

.toc-num {
    font-family: var(--font-mono);
    font-weight: 600;
    color: var(--color-accent);
    min-width: 28px;
}

/* --- GAUGE (CIRCULAR SCORE) --- */
.gauge-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-sm);
}

.gauge-svg {
    width: 160px;
    height: 160px;
}

.gauge-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--color-text-secondary);
}

/* --- TREND ARROWS --- */
.trend-up { color: var(--color-success); }
.trend-down { color: var(--color-critical); }
.trend-stable { color: var(--color-text-muted); }
.trend-volatile { color: var(--color-warning); }

.trend-arrow {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-weight: 600;
    font-size: 0.85rem;
}

/* --- PRINT STYLES --- */
@media print {
    @page {
        size: A4;
        margin: 15mm 12mm;
    }

    body {
        background: white !important;
        font-size: 11px;
        line-height: 1.5;
    }

    .memo-container {
        max-width: none;
        padding: 0;
        box-shadow: none;
    }

    .section {
        page-break-inside: avoid;
    }

    .cover-page {
        min-height: auto;
        height: auto;
        padding: 60px 40px;
        page-break-after: always;
    }

    .card:hover {
        box-shadow: var(--shadow-sm);
    }

    table { font-size: 9px; }
    thead th { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    tbody tr:nth-child(even) { -webkit-print-color-adjust: exact; print-color-adjust: exact; }

    .verdict-box, .heatmap-cell, .badge, .callout, .verification-badge {
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }

    .chart-container {
        page-break-inside: avoid;
    }

    canvas {
        max-height: 300px !important;
    }

    h2 { margin-top: var(--space-xl); }
    .no-print { display: none !important; }
}

/* --- UTILITY CLASSES --- */
.mt-0 { margin-top: 0; }
.mt-1 { margin-top: var(--space-sm); }
.mt-2 { margin-top: var(--space-md); }
.mt-3 { margin-top: var(--space-lg); }
.mt-4 { margin-top: var(--space-xl); }
.mb-0 { margin-bottom: 0; }
.mb-1 { margin-bottom: var(--space-sm); }
.mb-2 { margin-bottom: var(--space-md); }
.mb-3 { margin-bottom: var(--space-lg); }
.mb-4 { margin-bottom: var(--space-xl); }
.p-0 { padding: 0; }
.p-1 { padding: var(--space-sm); }
.p-2 { padding: var(--space-md); }
.p-3 { padding: var(--space-lg); }
.gap-1 { gap: var(--space-sm); }
.gap-2 { gap: var(--space-md); }
.gap-3 { gap: var(--space-lg); }
.d-flex { display: flex; }
.flex-wrap { flex-wrap: wrap; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.w-full { width: 100%; }
"""
    return css_template.replace("__FONT_FACES__", font_faces)
