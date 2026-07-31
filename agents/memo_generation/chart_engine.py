"""
Module:  chart_engine.py
Agent:   Memo Generation Agent
Purpose: Chart.js configuration generator for all investment memo visualizations.
         Generates JavaScript code for rendering charts inside the HTML report.
         Supports: Bar, Line, Combo, Doughnut, Radar, Pie, Horizontal Bar,
         and custom gauge/football-field visualizations.
Inputs:  Chart data (labels, values, colors) from section writers.
Outputs: HTML+JS strings containing <canvas> + <script> blocks for Chart.js rendering.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Global chart counter for unique IDs
_chart_counter = 0


def _next_chart_id(prefix: str = "chart") -> str:
    """Generate a unique chart canvas ID."""
    global _chart_counter
    _chart_counter += 1
    return f"{prefix}_{_chart_counter}"


def reset_chart_counter() -> None:
    """Reset the global chart counter (call at the start of each memo generation)."""
    global _chart_counter
    _chart_counter = 0


# ── Color Palette ──────────────────────────────────────────────────────
COLORS = {
    "primary": "#1B2A4A",
    "secondary": "#3A5A8C",
    "accent": "#4A90D9",
    "success": "#10B981",
    "success_light": "#A7F3D0",
    "warning": "#F59E0B",
    "warning_light": "#FDE68A",
    "danger": "#F97316",
    "danger_light": "#FED7AA",
    "critical": "#EF4444",
    "critical_light": "#FECACA",
    "blue": "#3B82F6",
    "indigo": "#6366F1",
    "purple": "#8B5CF6",
    "teal": "#14B8A6",
    "cyan": "#06B6D4",
    "rose": "#F43F5E",
    "slate": "#64748B",
    "emerald": "#10B981",
    "amber": "#F59E0B",
}

# Default multi-series palette
PALETTE = [
    "#4A90D9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6",
    "#06B6D4", "#F43F5E", "#14B8A6", "#6366F1", "#F97316",
]

PALETTE_BG = [
    "rgba(74,144,217,0.15)", "rgba(16,185,129,0.15)", "rgba(245,158,11,0.15)",
    "rgba(239,68,68,0.15)", "rgba(139,92,246,0.15)", "rgba(6,182,212,0.15)",
    "rgba(244,63,94,0.15)", "rgba(20,184,166,0.15)", "rgba(99,102,241,0.15)",
    "rgba(249,115,22,0.15)",
]


def _base_chart_options(title: str = "", y_label: str = "", x_label: str = "",
                        show_legend: bool = True, aspect_ratio: float = 2.0,
                        currency_format: bool = False, percentage_format: bool = False) -> dict:
    """Return base Chart.js options with professional styling.
    
    Args:
        currency_format: If True, Y-axis ticks will be formatted as $100B, $50M, etc.
        percentage_format: If True, Y-axis ticks will show '%' suffix.
    """
    opts: dict[str, Any] = {
        "responsive": True,
        "maintainAspectRatio": True,
        "aspectRatio": aspect_ratio,
        "plugins": {
            "legend": {
                "display": show_legend,
                "position": "top",
                "labels": {
                    "font": {"family": "'Inter', sans-serif", "size": 11},
                    "padding": 15,
                    "usePointStyle": True,
                    "pointStyle": "circle",
                },
            },
            "title": {
                "display": bool(title),
                "text": title,
                "font": {"family": "'Inter', sans-serif", "size": 14, "weight": "600"},
                "color": "#1B2A4A",
                "padding": {"bottom": 15},
            },
            "tooltip": {
                "backgroundColor": "#1E293B",
                "titleFont": {"family": "'Inter', sans-serif", "size": 12},
                "bodyFont": {"family": "'JetBrains Mono', monospace", "size": 11},
                "cornerRadius": 8,
                "padding": 10,
            },
        },
        "scales": {
            "x": {
                "grid": {"display": False},
                "ticks": {
                    "autoSkip": False,
                    "font": {"family": "'Inter', sans-serif", "size": 11},
                    "color": "#64748B",
                },
            },
            "y": {
                "grid": {"color": "rgba(0,0,0,0.06)", "drawBorder": False},
                "ticks": {
                    "autoSkip": False,
                    "font": {"family": "'JetBrains Mono', monospace", "size": 11},
                    "color": "#64748B",
                },
            },
        },
        # Custom flags for _wrap_chart to inject JS callbacks
        "_currency_format": currency_format,
        "_percentage_format": percentage_format,
    }
    if y_label:
        opts["scales"]["y"]["title"] = {"display": True, "text": y_label,
                                         "font": {"size": 11}, "color": "#94A3B8"}
    if x_label:
        opts["scales"]["x"]["title"] = {"display": True, "text": x_label,
                                         "font": {"size": 11}, "color": "#94A3B8"}
    return opts


def _wrap_chart(canvas_id: str, config: dict, title: str = "", height: str = "400px") -> str:
    """Wrap a Chart.js config into a renderable HTML block with <canvas> and <script>.
    
    Handles special _currency_format and _percentage_format flags by injecting
    JavaScript tick callback functions after JSON serialization.
    """
    # Extract custom flags before serialization
    options = config.get("options", {})
    currency_format = options.pop("_currency_format", False)
    percentage_format = options.pop("_percentage_format", False)
    
    config_json = json.dumps(config, indent=2, default=str)
    
    # Inject tick callback for currency formatting
    # We replace the y-axis ticks section with a callback that formats numbers
    if currency_format:
        # Add a post-creation script to set tick callback
        callback_js = """
            // Currency formatting for Y-axis
            chart.options.scales.y.ticks.callback = function(value) {
                var abs = Math.abs(value);
                if (abs >= 1e12) return '$' + (value/1e12).toFixed(1) + 'T';
                if (abs >= 1e9) return '$' + (value/1e9).toFixed(1) + 'B';
                if (abs >= 1e6) return '$' + (value/1e6).toFixed(0) + 'M';
                if (abs >= 1e3) return '$' + (value/1e3).toFixed(0) + 'K';
                return '$' + value.toFixed(0);
            };
            // Also format y2 axis if it exists (combo charts with dual Y-axes)
            if (chart.options.scales.y2) {
                chart.options.scales.y2.ticks.callback = function(value) {
                    var abs = Math.abs(value);
                    if (abs >= 1e12) return '$' + (value/1e12).toFixed(1) + 'T';
                    if (abs >= 1e9) return '$' + (value/1e9).toFixed(1) + 'B';
                    if (abs >= 1e6) return '$' + (value/1e6).toFixed(0) + 'M';
                    if (abs >= 1e3) return '$' + (value/1e3).toFixed(0) + 'K';
                    return '$' + value.toFixed(0);
                };
            }
            chart.options.plugins.tooltip.callbacks = chart.options.plugins.tooltip.callbacks || {};
            chart.options.plugins.tooltip.callbacks.label = function(ctx) {
                var v = ctx.parsed.y != null ? ctx.parsed.y : ctx.parsed.x;
                var abs = Math.abs(v);
                var formatted;
                if (abs >= 1e12) formatted = '$' + (v/1e12).toFixed(2) + 'T';
                else if (abs >= 1e9) formatted = '$' + (v/1e9).toFixed(2) + 'B';
                else if (abs >= 1e6) formatted = '$' + (v/1e6).toFixed(1) + 'M';
                else if (abs >= 1e3) formatted = '$' + (v/1e3).toFixed(1) + 'K';
                else formatted = '$' + v.toFixed(0);
                return ctx.dataset.label + ': ' + formatted;
            };
            chart.update();
        """
    elif percentage_format:
        callback_js = """
            chart.options.scales.y.ticks.callback = function(value) {
                return value.toFixed(1) + '%';
            };
            chart.update();
        """
    else:
        callback_js = ""
    
    html = f"""
    <div class="chart-container">
        {"<div class='chart-title'>" + title + "</div>" if title else ""}
        <canvas id="{canvas_id}" style="max-height:{height};"></canvas>
    </div>
    <script>
        (function() {{
            const ctx = document.getElementById('{canvas_id}').getContext('2d');
            const chart = new Chart(ctx, {config_json});
            {callback_js}
        }})();
    </script>
    """
    return html


# ══════════════════════════════════════════════════════════════════════
#                        CHART TYPE GENERATORS
# ══════════════════════════════════════════════════════════════════════

def bar_chart(labels: list, datasets: list[dict], title: str = "",
              y_label: str = "", stacked: bool = False, horizontal: bool = False,
              height: str = "400px", show_legend: bool = True,
              currency_format: bool = False, percentage_format: bool = False) -> str:
    """Generate a bar chart (vertical or horizontal).

    Args:
        labels: Category labels (x-axis).
        datasets: List of dicts with keys: label, data, color (optional), bg_color (optional).
        title: Chart title.
        y_label: Y-axis label.
        stacked: Whether to stack bars.
        horizontal: If True, renders horizontal bars.
        height: CSS max-height.
        show_legend: Whether to show legend.
        currency_format: Format Y-axis ticks as $100B, $50M, etc.
        percentage_format: Format Y-axis ticks with % suffix.

    Returns:
        HTML string with canvas + script.
    """
    canvas_id = _next_chart_id("bar")
    chart_datasets = []
    for i, ds in enumerate(datasets):
        color = ds.get("color", PALETTE[i % len(PALETTE)])
        bg = ds.get("bg_color", color)
        chart_datasets.append({
            "label": ds.get("label", f"Series {i+1}"),
            "data": ds["data"],
            "backgroundColor": bg,
            "borderColor": color,
            "borderWidth": 1,
            "borderRadius": 4,
            "maxBarThickness": 50,
        })

    opts = _base_chart_options(title, y_label, show_legend=show_legend,
                               currency_format=currency_format,
                               percentage_format=percentage_format)
    if stacked:
        opts["scales"]["x"]["stacked"] = True
        opts["scales"]["y"]["stacked"] = True
    if horizontal:
        opts["indexAxis"] = "y"

    config = {"type": "bar", "data": {"labels": labels, "datasets": chart_datasets}, "options": opts}
    return _wrap_chart(canvas_id, config, height=height)


def line_chart(labels: list, datasets: list[dict], title: str = "",
               y_label: str = "", height: str = "400px", show_legend: bool = True,
               fill: bool = False, currency_format: bool = False,
               percentage_format: bool = False) -> str:
    """Generate a line chart.

    Args:
        labels: X-axis labels.
        datasets: List of dicts with keys: label, data, color (optional).
        title: Chart title.
        y_label: Y-axis label.
        height: CSS max-height.
        show_legend: Whether to show legend.
        fill: Whether to fill area under lines.
        currency_format: Format Y-axis ticks as $100B, $50M, etc.
        percentage_format: Format Y-axis ticks with % suffix.

    Returns:
        HTML string with canvas + script.
    """
    canvas_id = _next_chart_id("line")
    chart_datasets = []
    for i, ds in enumerate(datasets):
        color = ds.get("color", PALETTE[i % len(PALETTE)])
        chart_datasets.append({
            "label": ds.get("label", f"Series {i+1}"),
            "data": ds["data"],
            "borderColor": color,
            "backgroundColor": PALETTE_BG[i % len(PALETTE_BG)] if fill else "transparent",
            "borderWidth": 2.5,
            "pointRadius": 4,
            "pointBackgroundColor": color,
            "pointBorderColor": "#fff",
            "pointBorderWidth": 2,
            "tension": 0.3,
            "fill": fill,
        })

    opts = _base_chart_options(title, y_label, show_legend=show_legend,
                               currency_format=currency_format,
                               percentage_format=percentage_format)
    config = {"type": "line", "data": {"labels": labels, "datasets": chart_datasets}, "options": opts}
    return _wrap_chart(canvas_id, config, height=height)


def combo_chart(labels: list, bar_datasets: list[dict], line_datasets: list[dict],
                title: str = "", y_label: str = "", y2_label: str = "",
                height: str = "400px", currency_format: bool = False) -> str:
    """Generate a combo bar + line chart with optional dual Y-axes.

    Args:
        labels: X-axis labels.
        bar_datasets: Bar series dicts (label, data, color).
        line_datasets: Line series dicts (label, data, color).
        title: Chart title.
        y_label: Left Y-axis label.
        y2_label: Right Y-axis label (if set, lines use y2 axis).
        height: CSS max-height.
        currency_format: Format Y-axis ticks as $100B, $50M, etc.

    Returns:
        HTML string.
    """
    canvas_id = _next_chart_id("combo")
    all_datasets = []

    for i, ds in enumerate(bar_datasets):
        color = ds.get("color", PALETTE[i % len(PALETTE)])
        all_datasets.append({
            "type": "bar",
            "label": ds.get("label", f"Bar {i+1}"),
            "data": ds["data"],
            "backgroundColor": color,
            "borderColor": color,
            "borderWidth": 1,
            "borderRadius": 4,
            "yAxisID": "y",
            "order": 2,
        })

    for j, ds in enumerate(line_datasets):
        color = ds.get("color", PALETTE[(len(bar_datasets) + j) % len(PALETTE)])
        all_datasets.append({
            "type": "line",
            "label": ds.get("label", f"Line {j+1}"),
            "data": ds["data"],
            "borderColor": color,
            "backgroundColor": "transparent",
            "borderWidth": 2.5,
            "pointRadius": 4,
            "pointBackgroundColor": color,
            "tension": 0.3,
            "yAxisID": "y2" if y2_label else "y",
            "order": 1,
        })

    opts = _base_chart_options(title, y_label, show_legend=True,
                               currency_format=currency_format)
    if y2_label:
        opts["scales"]["y2"] = {
            "position": "right",
            "grid": {"drawOnChartArea": False},
            "title": {"display": True, "text": y2_label, "font": {"size": 11}, "color": "#94A3B8"},
            "ticks": {"font": {"family": "'JetBrains Mono', monospace", "size": 11}, "color": "#64748B"},
        }

    config = {"type": "bar", "data": {"labels": labels, "datasets": all_datasets}, "options": opts}
    return _wrap_chart(canvas_id, config, height=height)


def doughnut_chart(labels: list, data: list, title: str = "",
                   colors: list | None = None, height: str = "350px") -> str:
    """Generate a doughnut/donut chart.

    Args:
        labels: Segment labels.
        data: Segment values.
        title: Chart title.
        colors: Optional custom colors list.
        height: CSS max-height.

    Returns:
        HTML string.
    """
    canvas_id = _next_chart_id("doughnut")
    chart_colors = colors or PALETTE[:len(labels)]

    config = {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [{
                "data": data,
                "backgroundColor": chart_colors,
                "borderWidth": 2,
                "borderColor": "#fff",
            }],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": True,
            "cutout": "55%",
            "plugins": {
                "legend": {
                    "position": "right",
                    "labels": {
                        "font": {"family": "'Inter', sans-serif", "size": 11},
                        "padding": 12,
                        "usePointStyle": True,
                    },
                },
                "title": {
                    "display": bool(title),
                    "text": title,
                    "font": {"family": "'Inter', sans-serif", "size": 14, "weight": "600"},
                    "color": "#1B2A4A",
                },
            },
        },
    }
    return _wrap_chart(canvas_id, config, height=height)


def radar_chart(labels: list, datasets: list[dict], title: str = "",
                height: str = "400px") -> str:
    """Generate a radar/spider chart.

    Args:
        labels: Axis labels (one per spoke).
        datasets: List of dicts with keys: label, data, color.
        title: Chart title.
        height: CSS max-height.

    Returns:
        HTML string.
    """
    canvas_id = _next_chart_id("radar")
    chart_datasets = []
    for i, ds in enumerate(datasets):
        color = ds.get("color", PALETTE[i % len(PALETTE)])
        chart_datasets.append({
            "label": ds.get("label", f"Series {i+1}"),
            "data": ds["data"],
            "borderColor": color,
            "backgroundColor": f"{color}33",
            "borderWidth": 2.5,
            "pointRadius": 4,
            "pointBackgroundColor": color,
            "pointBorderColor": "#fff",
            "pointBorderWidth": 2,
        })

    config = {
        "type": "radar",
        "data": {"labels": labels, "datasets": chart_datasets},
        "options": {
            "responsive": True,
            "maintainAspectRatio": True,
            "scales": {
                "r": {
                    "beginAtZero": True,
                    "grid": {"color": "rgba(0,0,0,0.06)"},
                    "ticks": {
                        "font": {"family": "'JetBrains Mono', monospace", "size": 10},
                        "color": "#94A3B8",
                        "backdropColor": "transparent",
                    },
                    "pointLabels": {
                        "font": {"family": "'Inter', sans-serif", "size": 11, "weight": "500"},
                        "color": "#1E293B",
                    },
                },
            },
            "plugins": {
                "legend": {
                    "position": "top",
                    "labels": {"font": {"family": "'Inter', sans-serif", "size": 11},
                               "usePointStyle": True},
                },
                "title": {
                    "display": bool(title),
                    "text": title,
                    "font": {"family": "'Inter', sans-serif", "size": 14, "weight": "600"},
                    "color": "#1B2A4A",
                },
            },
        },
    }
    return _wrap_chart(canvas_id, config, height=height)


def pie_chart(labels: list, data: list, title: str = "",
              colors: list | None = None, height: str = "350px") -> str:
    """Generate a pie chart.

    Args:
        labels: Segment labels.
        data: Segment values.
        title: Chart title.
        colors: Optional custom colors.
        height: CSS max-height.

    Returns:
        HTML string.
    """
    canvas_id = _next_chart_id("pie")
    chart_colors = colors or PALETTE[:len(labels)]

    config = {
        "type": "pie",
        "data": {
            "labels": labels,
            "datasets": [{
                "data": data,
                "backgroundColor": chart_colors,
                "borderWidth": 2,
                "borderColor": "#fff",
            }],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": True,
            "plugins": {
                "legend": {
                    "position": "right",
                    "labels": {"font": {"family": "'Inter', sans-serif", "size": 11},
                               "padding": 12, "usePointStyle": True},
                },
                "title": {
                    "display": bool(title),
                    "text": title,
                    "font": {"family": "'Inter', sans-serif", "size": 14, "weight": "600"},
                    "color": "#1B2A4A",
                },
            },
        },
    }
    return _wrap_chart(canvas_id, config, height=height)


# ══════════════════════════════════════════════════════════════════════
#                    CUSTOM SVG VISUALIZATIONS
# ══════════════════════════════════════════════════════════════════════

def gauge_svg(score: float, max_score: float = 100, label: str = "",
              thresholds: dict | None = None) -> str:
    """Generate a circular gauge SVG visualization.

    Args:
        score: Current score value.
        max_score: Maximum possible score.
        label: Label text below the score.
        thresholds: Dict mapping color to min value, e.g. {90: '#10B981', 75: '#F59E0B', ...}

    Returns:
        HTML string with inline SVG.
    """
    pct = min(max(score / max_score, 0), 1.0)
    circumference = 2 * 3.14159 * 60  # radius = 60
    dash = circumference * pct
    gap = circumference - dash

    # Determine color from thresholds
    default_thresholds = {90: "#10B981", 75: "#4A90D9", 60: "#F59E0B", 40: "#F97316", 0: "#EF4444"}
    thresholds = thresholds or default_thresholds
    color = "#EF4444"
    for threshold in sorted(thresholds.keys(), reverse=True):
        if score >= threshold:
            color = thresholds[threshold]
            break

    return f"""
    <div class="gauge-container">
        <svg class="gauge-svg" viewBox="0 0 140 140">
            <!-- Background circle -->
            <circle cx="70" cy="70" r="60" fill="none" stroke="#E2E8F0" stroke-width="10"/>
            <!-- Score arc -->
            <circle cx="70" cy="70" r="60" fill="none" stroke="{color}" stroke-width="10"
                    stroke-dasharray="{dash:.1f} {gap:.1f}"
                    stroke-linecap="round" transform="rotate(-90 70 70)"
                    style="transition: stroke-dasharray 0.8s ease;"/>
            <!-- Score text -->
            <text x="70" y="65" text-anchor="middle" font-family="'JetBrains Mono', monospace"
                  font-size="28" font-weight="800" fill="{color}">{score:.0f}</text>
            <text x="70" y="82" text-anchor="middle" font-family="'Inter', sans-serif"
                  font-size="10" fill="#64748B">/ {max_score:.0f}</text>
        </svg>
        {"<div class='gauge-label'>" + label + "</div>" if label else ""}
    </div>
    """


def football_field_chart(methods: list[dict], current_price: float) -> str:
    """Generate a football field valuation chart (horizontal range bars).

    Args:
        methods: List of dicts with keys: name, low, base, high, color.
        current_price: Current stock price for the reference line.

    Returns:
        HTML string.
    """
    if not methods or current_price <= 0:
        return "<p class='text-muted'>Insufficient data for football field chart.</p>"

    # Find the global min/max for scaling
    all_values = [current_price]
    for m in methods:
        all_values.extend([m.get("low", 0), m.get("base", 0), m.get("high", 0)])
    global_min = min(v for v in all_values if v > 0) * 0.8
    global_max = max(all_values) * 1.1
    total_range = global_max - global_min

    if total_range <= 0:
        return "<p class='text-muted'>Invalid valuation range.</p>"

    rows_html = []
    for i, m in enumerate(methods):
        low = m.get("low", 0)
        base = m.get("base", 0)
        high = m.get("high", 0)
        color = m.get("color", PALETTE[i % len(PALETTE)])

        left_pct = ((low - global_min) / total_range) * 100
        width_pct = ((high - low) / total_range) * 100
        current_pct = ((current_price - global_min) / total_range) * 100

        rows_html.append(f"""
        <div class="ff-row">
            <div class="ff-label">{m.get('name', f'Method {i+1}')}</div>
            <div class="ff-bar-container">
                <div class="ff-bar" style="left:{left_pct:.1f}%; width:{width_pct:.1f}%;
                     background:linear-gradient(90deg, {color}66, {color});">
                    ${base:,.0f}
                </div>
                <div class="ff-current-line" style="left:{current_pct:.1f}%;"></div>
                <div class="ff-current-label" style="left:{current_pct:.1f}%;">Current: ${current_price:,.2f}</div>
            </div>
            <div class="ff-value">${base:,.0f}</div>
        </div>
        """)

    return f"""
    <div class="football-field">
        <div class="chart-title">Implied Valuation Range vs Current Price</div>
        {''.join(rows_html)}
        <div style="text-align:center; margin-top:8px;">
            <span class="text-small text-muted">◾ Bar range = 25th to 75th percentile implied price &nbsp;|&nbsp; 🔴 Red line = Current stock price</span>
        </div>
    </div>
    """


def heatmap_risk(dimensions: list[dict]) -> str:
    """Generate a risk heat map grid.

    Args:
        dimensions: List of dicts with keys: name, score, level (LOW/MEDIUM/HIGH/CRITICAL).

    Returns:
        HTML string.
    """
    level_map = {
        "LOW": (0, "low"),
        "MEDIUM": (1, "medium"),
        "HIGH": (2, "high"),
        "CRITICAL": (3, "critical"),
    }

    rows_html = []
    for dim in dimensions:
        name = dim.get("name", "Unknown")
        level = dim.get("level", "LOW").upper()
        score = dim.get("score", 0)
        level_idx, level_class = level_map.get(level, (0, "low"))

        cells = []
        for col_idx, (col_level, col_class) in enumerate([("LOW", "low"), ("MEDIUM", "medium"),
                                                           ("HIGH", "high"), ("CRITICAL", "critical")]):
            active = "active" if col_idx == level_idx else ""
            cell_text = f"{score:.0f}" if col_idx == level_idx else ""
            cells.append(f'<div class="heatmap-cell {col_class} {active}">{cell_text}</div>')

        rows_html.append(f"""
            <div class="heatmap-cell row-label">{name}</div>
            {''.join(cells)}
        """)

    return f"""
    <div class="heatmap-grid">
        <div class="heatmap-cell header">Dimension</div>
        <div class="heatmap-cell header">Low</div>
        <div class="heatmap-cell header">Medium</div>
        <div class="heatmap-cell header">High</div>
        <div class="heatmap-cell header">Critical</div>
        {''.join(rows_html)}
    </div>
    """
