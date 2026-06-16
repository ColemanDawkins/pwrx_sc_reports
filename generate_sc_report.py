"""
generate_sc_report.py
─────────────────────────────────────────────────────────────────────────────
Strength & Conditioning Performance Report Generator
Mirrors the PitchingWRX report style.

Outputs a single fully self-contained HTML file (no CDN, no internet needed).
All charts are rendered via matplotlib and embedded as base64 PNG images.

Dependencies (pip install):
    matplotlib    – static chart rendering (embedded as base64 PNG)
    jinja2        – HTML templating

Usage:
    python generate_sc_report.py
    python generate_sc_report.py --athlete "Jane Doe" --out reports/jane_doe.html
─────────────────────────────────────────────────────────────────────────────
"""

import argparse
import base64
import io
import math
import os
import sys

# ── optional dependency check ────────────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch
    from matplotlib.ticker import MaxNLocator
except ImportError:
    sys.exit("Missing dependency: pip install matplotlib")

try:
    from jinja2 import Environment, BaseLoader
except ImportError:
    sys.exit("Missing dependency: pip install jinja2")


# ─────────────────────────────────────────────────────────────────────────────
# DATA  (swap these dicts with Supabase / API calls per athlete)
# ─────────────────────────────────────────────────────────────────────────────

DATA = {
    "athlete_name": "Isaac Stebens",
    "report_date":  "Jan 2026",

    # DARI — Athletic Movement Assessment
    "dari": {
        "trend": [
            {"session": "Sep '25", "overall": 88.1, "athleticism": 84.7, "functionality": 73.2, "explosiveness": 99.4, "dysfunction": 3.1},
            {"session": "Nov '25", "overall": 90.4, "athleticism": 86.0, "functionality": 79.7, "explosiveness": 95.0, "dysfunction": 2.8},
            {"session": "Dec '25", "overall": 89.0, "athleticism": 85.2, "functionality": 79.6, "explosiveness": 95.1, "dysfunction": 4.2},
            {"session": "Jan '26", "overall": 86.5, "athleticism": 83.3, "functionality": 74.1, "explosiveness": 97.7, "dysfunction": 5.2},
        ],
        "current": {"overall": 86.5, "athleticism": 83.3, "functionality": 74.1, "explosiveness": 97.7, "dysfunction": 5.2},
        "percentiles": {"athleticism": 83, "explosiveness": 98, "dysfunction": 35, "vulnerability": 30},
        "focus_areas": ["R Knee Kinetics", "L Knee Kinetics", "R Shoulder Align."],
    },

    # VALD Force Decks — Countermovement Jump
    "vald": {
        "trend": [
            {"session": "Oct '24", "jump_height": 19.89, "peak_power": 5603, "rsi_mod": 0.671},
            {"session": "Dec '24", "jump_height": 20.82, "peak_power": 5853, "rsi_mod": 0.719},
            {"session": "Jan '25", "jump_height": 21.15, "peak_power": 5997, "rsi_mod": 0.699},
            {"session": "Jan '26", "jump_height": 20.71, "peak_power": 5633, "rsi_mod": 0.773},
        ],
        "current": {"jump_height": 20.71, "peak_power": 5633, "rsi_mod": 0.773},
        "prev":    {"jump_height": 21.15, "peak_power": 5997, "rsi_mod": 0.699},
    },

    # ArmCare — Throwing Arm Health
    "arm": {
        "trend": [
            {"session": "Sep '25", "arm_score": 94.7,  "total_strength": 198.9, "balance": 0.88, "svr": 2.09},
            {"session": "Nov '25", "arm_score": 89.9,  "total_strength": 188.7, "balance": 0.95, "svr": 1.99},
            {"session": "Dec '25", "arm_score": 96.5,  "total_strength": 202.7, "balance": 0.97, "svr": 2.13},
            {"session": "Jan '26", "arm_score": 102.1, "total_strength": 214.4, "balance": 0.88, "svr": 2.26},
        ],
        "current": {"arm_score": 102.1, "total_strength": 214.4, "balance": 0.88, "svr": 2.26},
        "prev":    {"arm_score": 96.5,  "total_strength": 202.7, "balance": 0.97, "svr": 2.13},
    },

    # InBody — Body Composition
    "inbody": {
        "available": True,
        "weight": 207.7,
        "weight_lbs": 207.7,
        "smm":    93.5,
        "smm_lbs": 93.5,
        "pbf":    22.1,
        "bmi":    29.0,
        "score":  85,
        "bmr": 2150,
        "phase_angle": 7.2,
        "trend": [
            {"session": "Nov '25", "weight": 210.2, "smm": 92.0, "pbf": 24.8, "bmi": 29.4, "score": 82, "bmr": 2120, "phase_angle": 7.0},
            {"session": "Jan '26", "weight": 207.7, "smm": 93.5, "pbf": 22.1, "bmi": 29.0, "score": 85, "bmr": 2150, "phase_angle": 7.2},
        ],
        "segments": [
            {"segment": "R Arm",  "lean_mass": 10.94, "highlight": True},
            {"segment": "L Arm",  "lean_mass":  8.62, "highlight": False},
            {"segment": "Trunk",  "lean_mass": 68.30, "highlight": False},
            {"segment": "R Leg",  "lean_mass": 23.46, "highlight": False},
            {"segment": "L Leg",  "lean_mass": 23.46, "highlight": False},
        ],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# COLORS
# ─────────────────────────────────────────────────────────────────────────────

C = {
    "orange":  "#E8621A",
    "orangeL": "#FF8040",
    "blue":    "#1565C0",
    "blueL":   "#2196F3",
    "blueMid": "#0D47A1",
    "dark":    "#0A2744",
    "deeper":  "#061828",
    "bg":      "#0A1830",
    "grey":    "#8BA4BF",
    "greyL":   "#C5D6E8",
    "green":   "#22c55e",
    "amber":   "#f59e0b",
    "purple":  "#a855f7",
    "panel":   "rgba(10,24,48,0.95)",
    "border":  "rgba(33,150,243,0.14)",
}


# ─────────────────────────────────────────────────────────────────────────────
# MATPLOTLIB HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _style_ax(ax):
    """Apply dark transparent theme to an axes."""
    ax.set_facecolor("none")
    ax.tick_params(colors=C["grey"], labelsize=7)
    ax.xaxis.label.set_color(C["grey"])
    ax.yaxis.label.set_color(C["grey"])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="rgba(255,255,255,0.05)" if False else "#1a2d45", linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)


def _fig_to_html(fig, height_px=150):
    """Render a matplotlib figure to a base64 PNG <img> tag."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor="none", transparent=True)
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    return (f'<img src="data:image/png;base64,{b64}" '
            f'style="width:100%;height:{height_px}px;object-fit:contain;" />')


def _make_fig(w=4.2, h=1.5):
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_alpha(0)
    return fig, ax


# ─────────────────────────────────────────────────────────────────────────────
# CHART BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def _dynamic_ylim(ax, vals, pad_pct=0.15, min_spread=None):
    """Set y-axis limits dynamically based on data with padding."""
    clean = [v for v in vals if v is not None and v == v]  # filter None/NaN
    if not clean:
        return
    lo, hi = min(clean), max(clean)
    spread = hi - lo if hi != lo else (abs(hi) * 0.1 or 1.0)
    if min_spread and spread < min_spread:
        mid = (lo + hi) / 2
        lo, hi = mid - min_spread/2, mid + min_spread/2
        spread = min_spread
    pad = spread * pad_pct
    ax.set_ylim(lo - pad, hi + pad)


def chart_dari_trend(data):
    rows = data["dari"]["trend"]
    sessions = [r["session"] for r in rows]
    x = range(len(sessions))

    fig, ax = plt.subplots(figsize=(4.2, 1.5))
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")

    for key, color, label in [
        ("athleticism",   C["orange"], "Athleticism"),
        ("functionality", C["blueL"],  "Functionality"),
        ("explosiveness", C["green"],  "Explosiveness"),
    ]:
        vals = [r[key] for r in rows]
        ax.plot(x, vals, color=color, linewidth=2, marker="o", markersize=4, label=label)

    all_vals = [r[k] for r in rows for k in ["athleticism","functionality","explosiveness"]]
    _dynamic_ylim(ax, all_vals, pad_pct=0.12, min_spread=10)
    ax.set_xticks(list(x))
    ax.set_xticklabels(sessions, fontsize=7, color=C["grey"])
    ax.tick_params(axis="y", colors=C["grey"], labelsize=7)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="#1a2d45", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)

    ax.legend(loc="upper left", fontsize=6, framealpha=0,
              labelcolor=C["grey"], ncol=3, bbox_to_anchor=(0, -0.18))

    fig.tight_layout(pad=0.3)
    return _fig_to_html(fig, 150)


def chart_dari_dysfunction(data):
    rows = data["dari"]["trend"]
    sessions = [r["session"] for r in rows]
    x = range(len(sessions))
    vals = [r["dysfunction"] for r in rows]

    # Color based on trend: improving (going down) = green, worsening (going up) = red
    if len(vals) >= 2:
        line_color = C["green"] if vals[-1] <= vals[0] else "#ef4444"
    else:
        line_color = C["amber"]

    fig, ax = _make_fig(4.2, 1.1)
    ax.set_facecolor("none")

    ax.plot(x, vals, color=line_color, linewidth=2, marker="o", markersize=5)
    ax.fill_between(x, vals, alpha=0.15, color=line_color)

    _dynamic_ylim(ax, vals, pad_pct=0.15, min_spread=2)
    ax.set_xticks(list(x))
    ax.set_xticklabels(sessions, fontsize=7, color=C["grey"])
    ax.tick_params(axis="y", colors=C["grey"], labelsize=7)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=4))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="#1a2d45", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)

    fig.tight_layout(pad=0.3)
    return _fig_to_html(fig, 110)


def chart_vald_jump_height(data):
    rows = data["vald"]["trend"]
    sessions = [r["session"] for r in rows]
    x = range(len(sessions))
    vals = [r["jump_height"] for r in rows]

    fig, ax = _make_fig(4.2, 1.2)
    ax.set_facecolor("none")
    ax.plot(x, vals, color=C["purple"], linewidth=2, marker="o", markersize=5)
    ax.fill_between(x, vals, alpha=0.15, color=C["purple"])
    _dynamic_ylim(ax, vals, pad_pct=0.15, min_spread=2)
    ax.set_xticks(list(x))
    ax.set_xticklabels(sessions, fontsize=7, color=C["grey"])
    ax.tick_params(axis="y", colors=C["grey"], labelsize=7)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="#1a2d45", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=0.3)
    return _fig_to_html(fig, 120)


def chart_vald_rsi(data):
    rows = data["vald"]["trend"]
    sessions = [r["session"] for r in rows]
    x = range(len(sessions))
    vals = [r["rsi_mod"] for r in rows]

    fig, ax = _make_fig(4.2, 1.2)
    ax.set_facecolor("none")
    ax.plot(x, vals, color=C["green"], linewidth=2, marker="o", markersize=5)
    ax.fill_between(x, vals, alpha=0.15, color=C["green"])
    _dynamic_ylim(ax, vals, pad_pct=0.15, min_spread=0.1)
    ax.set_xticks(list(x))
    ax.set_xticklabels(sessions, fontsize=7, color=C["grey"])
    ax.tick_params(axis="y", colors=C["grey"], labelsize=7)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="#1a2d45", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=0.3)
    return _fig_to_html(fig, 120)


def chart_vald_power(data):
    rows = data["vald"]["trend"]
    sessions = [r["session"] for r in rows]
    x = range(len(sessions))
    vals = [r["peak_power"] for r in rows]

    fig, ax = _make_fig(4.2, 1.2)
    ax.set_facecolor("none")

    ax.plot(x, vals, color=C["blueL"], linewidth=2, marker="o", markersize=5)
    ax.fill_between(x, vals, alpha=0.15, color=C["blueL"])
    _dynamic_ylim(ax, vals, pad_pct=0.15, min_spread=500)
    ax.set_xticks(list(x))
    ax.set_xticklabels(sessions, fontsize=7, color=C["grey"])
    ax.tick_params(axis="y", colors=C["grey"], labelsize=7)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="#1a2d45", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)

    fig.tight_layout(pad=0.3)
    return _fig_to_html(fig, 120)


def chart_arm_score(data):
    rows = data["arm"]["trend"]
    sessions = [r["session"] for r in rows]
    x = range(len(sessions))
    vals = [r["arm_score"] for r in rows]

    fig, ax = _make_fig(4.2, 1.6)
    ax.set_facecolor("none")
    ax.plot(x, vals, color=C["orange"], linewidth=2, marker="o", markersize=5)
    ax.fill_between(x, vals, alpha=0.2, color=C["orange"])
    _dynamic_ylim(ax, vals, pad_pct=0.12, min_spread=10)
    ax.set_xticks(list(x))
    ax.set_xticklabels(sessions, fontsize=7, color=C["grey"])
    ax.tick_params(axis="y", colors=C["grey"], labelsize=7)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="#1a2d45", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=0.3)
    return _fig_to_html(fig, 155)


def chart_arm_strength(data):
    rows = data["arm"]["trend"]
    sessions = [r["session"] for r in rows]
    x = range(len(sessions))
    vals = [r["total_strength"] for r in rows]

    fig, ax = _make_fig(3.8, 1.3)
    ax.set_facecolor("none")
    ax.plot(x, vals, color=C["blueL"], linewidth=2, marker="o", markersize=4)
    ax.fill_between(x, vals, alpha=0.18, color=C["blueL"])
    _dynamic_ylim(ax, vals, pad_pct=0.12, min_spread=20)
    ax.set_xticks(list(x))
    ax.set_xticklabels(sessions, fontsize=6.5, color=C["grey"])
    ax.tick_params(axis="y", colors=C["grey"], labelsize=7)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="#1a2d45", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=0.3)
    return _fig_to_html(fig, 125)


def chart_arm_svr(data):
    rows = data["arm"]["trend"]
    sessions = [r["session"] for r in rows]
    x = range(len(sessions))
    vals = [r["svr"] for r in rows]

    fig, ax = _make_fig(3.8, 1.3)
    ax.set_facecolor("none")
    ax.plot(x, vals, color=C["amber"], linewidth=2, marker="o", markersize=4)
    ax.fill_between(x, vals, alpha=0.15, color=C["amber"])
    _dynamic_ylim(ax, vals, pad_pct=0.15, min_spread=0.3)
    ax.set_xticks(list(x))
    ax.set_xticklabels(sessions, fontsize=6.5, color=C["grey"])
    ax.tick_params(axis="y", colors=C["grey"], labelsize=7)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="#1a2d45", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=0.3)
    return _fig_to_html(fig, 125)


def chart_arm_balance(data):
    rows = data["arm"]["trend"]
    sessions = [r["session"] for r in rows]
    x = range(len(sessions))
    vals = [r["balance"] for r in rows]

    fig, ax = _make_fig(4.2, 1.5)
    ax.set_facecolor("none")
    ax.plot(x, vals, color=C["green"], linewidth=2, marker="o", markersize=5)
    ax.fill_between(x, vals, alpha=0.15, color=C["green"])
    ax.axhline(1.0, color=C["greyL"], linewidth=0.8, linestyle="--", alpha=0.4)
    _dynamic_ylim(ax, vals + [1.0], pad_pct=0.15, min_spread=0.15)
    ax.set_xticks(list(x))
    ax.set_xticklabels(sessions, fontsize=7, color=C["grey"])
    ax.tick_params(axis="y", colors=C["grey"], labelsize=7)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="#1a2d45", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=0.3)
    return _fig_to_html(fig, 145)


def chart_inbody_donut(data):
    pbf  = data["inbody"]["pbf"]
    lean = 100 - pbf

    fig, ax = plt.subplots(figsize=(2.8, 2.0))
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")

    # shift donut to the right to leave room for legend on the left
    ax.set_position([0.32, 0.05, 0.65, 0.90])

    wedge_props = dict(width=0.42, edgecolor="none")
    wedges, _ = ax.pie(
        [lean, pbf],
        colors=[C["blueL"], C["orange"]],
        startangle=90,
        wedgeprops=wedge_props,
        counterclock=False,
    )
    # centre label — smaller so it fits inside the ring
    ax.text(0, 0.13, f"{pbf}%", ha="center", va="center",
            fontsize=13, fontweight="bold", color="white")
    ax.text(0, -0.20, "Body Fat", ha="center", va="center",
            fontsize=7, color=C["grey"])
    # legend pinned to the left of the donut
    ax.legend(
        wedges,
        [f"Lean Mass\n{lean:.1f}%", f"Body Fat\n{pbf}%"],
        loc="center left",
        bbox_to_anchor=(-0.72, 0.50),
        fontsize=7.5,
        framealpha=0,
        labelcolor=C["greyL"],
        handlelength=0.9,
        handleheight=0.9,
        borderpad=0.2,
        labelspacing=0.7,
        ncol=1,
    )
    return _fig_to_html(fig, 190)


def chart_segments(data):
    segs   = data["inbody"]["segments"]
    names  = [s["segment"] for s in segs]
    vals   = [s["lean_mass"] for s in segs]
    colors = [C["orange"] if s["highlight"] else C["blueL"] for s in segs]

    fig, ax = _make_fig(4.2, 1.4)
    ax.set_facecolor("none")

    bars = ax.barh(names, vals, color=colors, height=0.55, zorder=2)
    for bar, val in zip(bars, vals):
        ax.text(val + 0.8, bar.get_y() + bar.get_height() / 2,
                f"{val} lbs", va="center", fontsize=6.5, color=C["greyL"])

    ax.set_xlim(0, 85)
    ax.tick_params(axis="x", colors=C["grey"], labelsize=7)
    ax.tick_params(axis="y", colors=C["greyL"], labelsize=7.5)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="x", color="#1a2d45", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=0.3)
    return _fig_to_html(fig, 210)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS — gauge SVG, chip badge
# ─────────────────────────────────────────────────────────────────────────────

def gauge_svg(value, max_val, label, color):
    R = 26; cx = 34; cy = 34
    arc = math.pi * R
    off = arc * (1 - min(value / max_val, 1))
    return f"""
    <div style="text-align:center;">
      <svg width="68" height="46" viewBox="0 0 68 46">
        <path d="M {cx-R} {cy} A {R} {R} 0 0 1 {cx+R} {cy}"
          fill="none" stroke="rgba(255,255,255,0.09)" stroke-width="7" stroke-linecap="round"/>
        <path d="M {cx-R} {cy} A {R} {R} 0 0 1 {cx+R} {cy}"
          fill="none" stroke="{color}" stroke-width="7" stroke-linecap="round"
          stroke-dasharray="{arc:.4f}" stroke-dashoffset="{off:.4f}"/>
        <text x="{cx}" y="{cy-2}" text-anchor="middle"
          fill="white" font-size="12" font-weight="800" font-family="monospace">{value:.1f}</text>
      </svg>
      <div style="font-size:8px;color:{C['greyL']};text-transform:uppercase;
        letter-spacing:0.9px;margin-top:-2px;">{label}</div>
    </div>"""


def chip(current, previous, invert=False):
    """
    invert=True for metrics where higher = worse (e.g. dysfunction score).
    Green when improving (going the right direction), red when worsening.
    """
    if previous == 0:
        return ""
    pct   = round((current - previous) / previous * 100, 1)
    # For inverted metrics: up is bad (red), down is good (green)
    good  = (pct < 0) if invert else (pct >= 0)
    color = "#22c55e" if good else "#ef4444"
    bg    = "rgba(34,197,94,0.18)" if good else "rgba(239,68,68,0.15)"
    arrow = "▲" if pct >= 0 else "▼"
    return (f'<span style="background:{bg};color:{color};font-size:9px;font-weight:700;'
            f'padding:1px 5px;border-radius:9px;">{arrow} {abs(pct):.1f}%</span>')


# ─────────────────────────────────────────────────────────────────────────────
# HTML TEMPLATE  (Plotly CDN removed — all charts are inline base64 PNGs)
# ─────────────────────────────────────────────────────────────────────────────

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{{ athlete_name }} — S&C Report</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;900&family=Barlow:wght@400;600;700&display=swap"/>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  background: {{ C.deeper }};
  font-family: 'Barlow', 'Helvetica Neue', sans-serif;
  color: #fff;
  min-height: 100vh;
}
.pwrx-header {
  background: {{ C.bg }};
  border-bottom: 3px solid {{ C.orange }};
  padding: 0 28px; height: 58px;
  display: flex; align-items: center; justify-content: space-between;
}
.pwrx-athlete-name {
  font-size: 24px; font-weight: 900; color: #fff;
  letter-spacing: 3px; text-transform: uppercase;
  font-family: 'Barlow Condensed', Impact, sans-serif;
  line-height: 1; text-align: center;
}
.pwrx-subtitle {
  font-size: 11px; color: {{ C.orange }};
  letter-spacing: 2.5px; text-transform: uppercase;
  margin-top: 3px; font-family: 'Barlow Condensed', sans-serif; text-align: center;
}
.pwrx-grid {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 10px; padding: 10px 14px;
  max-width: 1440px; margin: 0 auto;
}
.pwrx-panel {
  background: rgba(10,24,48,0.95);
  border: 1px solid rgba(33,150,243,0.14);
  border-radius: 8px; overflow: hidden;
}
.pwrx-panel-header {
  padding: 6px 16px;
  font-family: 'Barlow Condensed', Impact, sans-serif;
  font-size: 13px; font-weight: 700;
  letter-spacing: 2.5px; text-transform: uppercase; color: #fff;
}
.pwrx-panel-header.blue  { background: {{ C.blueMid }}; }
.pwrx-panel-header.orange{ background: {{ C.orange }}; }
.pwrx-panel-body { padding: 13px 15px; }
.pwrx-divider { height: 1px; background: rgba(255,255,255,0.07); margin: 10px 0; }
.pwrx-section-label {
  font-size: 10px; color: {{ C.grey }};
  text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px;
}
.pwrx-stat-box {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 7px; padding: 8px 5px; text-align: center;
}
.pwrx-stat-value {
  font-size: 19px; font-weight: 900; font-family: monospace; line-height: 1;
}
.pwrx-stat-unit { font-size: 9px; color: {{ C.grey }}; font-weight: 400; }
.pwrx-stat-label {
  font-size: 8px; color: {{ C.greyL }};
  text-transform: uppercase; letter-spacing: 0.8px; margin: 3px 0 2px;
}
.pwrx-focus-item {
  margin-bottom: 10px;
  background: rgba(255,255,255,0.04); border-radius: 6px; padding: 8px 10px;
}
.pwrx-focus-top {
  display: flex; align-items: center; gap: 8px; margin-bottom: 5px;
}
.pwrx-focus-num {
  width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; font-size: 11px; font-weight: 900; color: #fff;
}
.pwrx-focus-desc {
  font-size: 10px; color: #7a9bbf; line-height: 1.5;
  padding-left: 30px; margin-top: 3px;
}
.pwrx-focus-trend-up   { color: #ef4444; font-weight: 700; }
.pwrx-focus-trend-down { color: #22c55e; font-weight: 700; }
.pwrx-focus-trend-flat { color: #9ca3af; }
.pwrx-summary-strip {
  padding: 0 14px 14px; max-width: 1440px; margin: 0 auto;
}
.pwrx-summary-grid {
  display: grid; grid-template-columns: repeat(8, 1fr);
  gap: 8px; padding: 10px 14px;
}
.pwrx-summary-kpi {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 7px; padding: 8px 4px; text-align: center;
}
.pwrx-footer {
  text-align: center; padding-bottom: 16px;
  color: rgba(255,255,255,0.15); font-size: 9px; letter-spacing: 1.5px;
}

/* ── MOBILE RESPONSIVE ── */
/* Mobile: single column */
@media (max-width: 768px) {
  .pwrx-grid { grid-template-columns: 1fr !important; grid-template-rows: auto !important; height: auto !important; }
  .pwrx-page2-grid { grid-template-columns: 1fr !important; }
}
@media (max-width: 768px) {
  .pwrx-grid {
    grid-template-columns: 1fr !important;
  }
  .pwrx-summary-grid {
    grid-template-columns: repeat(4, 1fr) !important;
  }
  .pwrx-header {
    padding: 0 14px;
    height: auto;
    flex-direction: column;
    text-align: center;
    padding: 12px 14px;
    gap: 4px;
  }
  .pwrx-header > div:first-child,
  .pwrx-header > div:last-child {
    width: auto !important;
  }
  .pwrx-athlete-name { font-size: 20px; letter-spacing: 2px; }
}
@media (max-width: 480px) {
  .pwrx-summary-grid {
    grid-template-columns: repeat(2, 1fr) !important;
  }
}

/* ── DECLINE FLAGS ── */
.pwrx-flags {
  margin: 0 14px 10px;
  max-width: 1440px;
  margin-left: auto;
  margin-right: auto;
  padding: 0 14px 10px;
}
.pwrx-flag-panel {
  background: rgba(239,68,68,0.08);
  border: 1px solid rgba(239,68,68,0.35);
  border-radius: 8px;
  overflow: hidden;
}
.pwrx-flag-header {
  background: rgba(239,68,68,0.75);
  padding: 6px 16px;
  font-family: 'Barlow Condensed', Impact, sans-serif;
  font-size: 13px; font-weight: 700;
  letter-spacing: 2.5px; text-transform: uppercase; color: #fff;
  display: flex; align-items: center; gap: 8px;
}
.pwrx-flag-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
  padding: 12px;
}
.pwrx-flag-item {
  background: rgba(239,68,68,0.07);
  border: 1px solid rgba(239,68,68,0.2);
  border-radius: 6px;
  padding: 8px 10px;
}
.pwrx-flag-source {
  font-size: 9px; color: #ef4444;
  text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px;
}
.pwrx-flag-metric {
  font-size: 11px; font-weight: 600; color: #fff; margin-bottom: 4px;
}
.pwrx-flag-values {
  display: flex; align-items: center; gap: 6px;
}
.pwrx-flag-prev { font-size: 12px; color: #9ca3af; font-family: monospace; }
.pwrx-flag-arrow { font-size: 14px; color: #ef4444; }
.pwrx-flag-curr { font-size: 14px; font-weight: 900; color: #ef4444; font-family: monospace; }
.pwrx-flag-pct {
  font-size: 10px; color: #ef4444; font-weight: 700;
  background: rgba(239,68,68,0.15); border-radius: 4px; padding: 1px 5px;
}
.pwrx-no-flags {
  padding: 12px 16px;
  font-size: 12px; color: #22c55e;
  display: flex; align-items: center; gap: 8px;
}

/* ── MOBILE RESPONSIVE ── */
@media (max-width: 768px) {
  .pwrx-grid {
    grid-template-columns: 1fr !important;
  }
  .pwrx-summary-grid {
    grid-template-columns: repeat(4, 1fr) !important;
  }
  .pwrx-header {
    height: auto;
    flex-direction: column;
    text-align: center;
    padding: 12px 14px;
    gap: 4px;
  }
  .pwrx-header > div:first-child,
  .pwrx-header > div:last-child {
    width: auto !important;
  }
  .pwrx-athlete-name { font-size: 20px; letter-spacing: 2px; }
}
@media (max-width: 480px) {
  .pwrx-summary-grid {
    grid-template-columns: repeat(2, 1fr) !important;
  }
}
/* ── DECLINE FLAGS ── */
.pwrx-flags { padding: 0 14px 10px; max-width: 1440px; margin: 0 auto; }
.pwrx-flag-panel { background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.35); border-radius: 8px; overflow: hidden; }
.pwrx-flag-header { background: rgba(239,68,68,0.75); padding: 6px 16px; font-family: 'Barlow Condensed', Impact, sans-serif; font-size: 13px; font-weight: 700; letter-spacing: 2.5px; text-transform: uppercase; color: #fff; display: flex; align-items: center; gap: 8px; }
.pwrx-flag-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; padding: 12px; }
.pwrx-flag-item { background: rgba(239,68,68,0.07); border: 1px solid rgba(239,68,68,0.2); border-radius: 6px; padding: 8px 10px; }
.pwrx-flag-source { font-size: 9px; color: #ef4444; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px; }
.pwrx-flag-metric { font-size: 11px; font-weight: 600; color: #fff; margin-bottom: 4px; }
.pwrx-flag-values { display: flex; align-items: center; gap: 6px; }
.pwrx-flag-prev { font-size: 12px; color: #9ca3af; font-family: monospace; }
.pwrx-flag-arrow { font-size: 14px; color: #ef4444; }
.pwrx-flag-curr { font-size: 14px; font-weight: 900; color: #ef4444; font-family: monospace; }
.pwrx-flag-pct { font-size: 10px; color: #ef4444; font-weight: 700; background: rgba(239,68,68,0.15); border-radius: 4px; padding: 1px 5px; }
.pwrx-no-flags { padding: 12px 16px; font-size: 12px; color: #22c55e; display: flex; align-items: center; gap: 8px; }
</style>
</head>
<body>

<!-- HEADER -->
<div class="pwrx-header">
  <div style="width:160px; display:flex; align-items:center; padding-left:8px;">
    <img src="data:image/png;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/4gHYSUNDX1BST0ZJTEUAAQEAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADb/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAH0AfQDASIAAhEBAxEB/8QAHQABAAICAwEBAAAAAAAAAAAAAAYHBQgBAgQDCf/EAFcQAAEDAwEFBAYHBAYGBQoHAAEAAgMEBREGBxIhMUETUWFxCBQigZGhFSMyQlKxwWJygpIWM6KywtEXJENT0uEJJVWj8CY0NmNzdJOUs+I1RmRlg6Tx/8QAGwEBAAIDAQEAAAAAAAAAAAAAAAQFAgMGAQf/xAA/EQABAwIDAwoFAwMEAQUBAAABAAIDBBEFITESQVEGEyJhcYGRwdHwFDKhseEjM0IVUvEWJDRTciU1YoKSov/aAAwDAQACEQMRAD8A0yRERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERFyGuP3T8EXtrrlFlLdp+/XJnaW6y3GsYfvQUr3j4gFe6LQ+rpX7rdN3Np/wDWUzmf3gFgZWDUgLc2mlf8rSe4qO5CZClrdm+tTysM/vewfquz9mutmtLjYpcDulYT8A5YfEw/3DxCz+Aqf+t3gVEPf8kUim0Rq6E+3p25u/cp3O/IFfGTSGq4270umbyxve6hkA/urMSxnRw8Vi6lmb8zCO4rAovtPDPDK6OWJ8b2nDmOaQQfEFfLBWa0EEarhERF4iIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIu+Edx6pnjnqpDpXR+oNSPH0Vb5Xw5w6of7MTeWcuPAkZzgZPgsXPawbTjYLbFE+VwZGCSdwUdPl819aeGWombDBE+SR5DWMY0lzieQAHMq8dM7FrZTFst/r5K14wTDT5jjz1BcfacPLcKsiyWOz2SDsbTbqajbuhrjGwBzwOW877TvMkqoqMbgjyYNo+AXUUXJCrns6Uhg8T4Ba9WLZbrC57rn29tvicCd+rfuYx0LBl497VOLPsQoIwHXe9VExLfsU0bY9137zt7I9wVur2221XO5P3LfQVVUevZRFwHmRyVRLjNVKbMFuwLp4OS+HUrdqU7XW42H0t9VBrTs50ZbXNdHZIZ5GtwX1DnS73iWuJbnyAUit9voLc0st9DTUjSckQQtjHwaAp/btl+rqvBko4aNp6zyj8m5PyUjoNjU7gDX3uNne2GAu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ihhcObXTN3vhnK1mrLlcazPrlfV1GefbTOf+ZXkUd+Of2s8Sp8PIv/tl8B5k+Svy7bV9MUhLaQ1Ne8cuzi3W583Y+QKh152v3mo3mWygpqJp5OeTK/8AQfIqtFi75qOxWRrjdbrS0rmt3uzfIDIR3hg9o+4KK7EKuc7LPoPZVpHyewujbty523uOXkFJrzfrxeX71zuNRU8chrn4YPJo4D3BY1VfqDbPYaTejtFFU3GQHAe/6mIjHME5cePQtHmq41HtO1ZecxiuFvgOPqqIGP8AtZL+PUb2PBbYcIqpztSZduqwqOUuHUTdiHpW3NFh4+l1fOqNX6d03G/6UuMTZ2jhTR+3M44yBuDlnoXYHiqj1htiuteJKWwU4tlOct7d5D53DiMj7rMgjlkgjg5VYS4niSVwQMq7pcIggzPSPX6LkMR5UVlXdrDsN4DXxX1qqiapqJJ6meSaWRxc+SRxc5xPMkniSviChXCtVzZN8yiIiLxERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERche62XW5WuZ01uuFXRyEYL4JnRkjuy0heHqmV4QDqsmuc03Cndp2q6zoOzbJcI62NgwGVMTXZ83DDifMqSW7bjcGZ+kbDTTjp6vKYsfzB6qHOUHDoosmH00nzMH2+ys4Mbr4PklPfn91fNu222ORhNwtNwp3d0JZKPiSz8l74dsmkJHkOjucQ73wN/wALytdyuFFdg1IdAR3qwZysxJurge4eS2UbtZ0SedfO3zpn/oEk2s6Jb9mvnf8Au0z/ANQtbEWH9DpevxW3/WGIdXh+Vsa/a/o9o4SVz/KD/MrzP206UA9mju7iOX1MYB/7xa9+5cZWTcFpRuPisHcrsROhA7ld1Xtyp2ve2l07K9v3XyVYafe0MP5qO3LbNqmpjdHSQ26iBPsyMhL3gd3tktP8qrTI7kUhmGUrNGDvz+6gzcoMRm+aUjsy+ykd41rqq79oK6+VrmSN3Xxxv7ONw8WNw35KOuJJ4knzK4JHRcFTGsa0WaLKrkmklN3uJPWbrhERZLUiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIv/9k="
         style="height:52px; width:52px; border-radius:50%; object-fit:cover;"
         alt="PWRX Logo" />
  </div>
  <div>
    <div class="pwrx-athlete-name">{{ athlete_name }}</div>
    <div class="pwrx-subtitle">Strength &amp; Conditioning Performance Report</div>
  </div>
  <div style="width:160px; text-align:right; font-size:10px; color:{{ C.grey }}; letter-spacing:1px;">
    {{ report_date }}
  </div>
</div>

<!-- 2×2 PANEL GRID -->
<div class="pwrx-grid">

  <!-- ── DARI ── -->
  <div class="pwrx-panel" style="background:#071828;border:1px solid rgba(255,255,255,0.07);border-radius:10px;overflow:hidden;display:flex;flex-direction:column;">
    <div style="display:flex;align-items:center;padding:0 14px;height:48px;border-bottom:2px solid #38A3A5;background:rgba(56,163,165,0.15);flex-shrink:0;">
      <img src="data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNTgiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMTU4IDEwMCIgZmlsbD0ibm9uZSI+CiAgPGcgY2xpcC1wYXRoPSJ1cmwoI2NsaXAwXzExMV84KSI+CiAgICA8IS0tIEJyYWNrZXQgbWFyayAtIGNvbG9yZWQgLS0+CiAgICA8cGF0aCBkPSJNMjYuOTkxNCAwQzI2LjM3OTcgMC4wMjYzMjUgMjUuODA2IDAuMzA0MiAyNS40MTA4IDAuNzcyMkwwLjUyNzM3MiAzMC4wMjIyQzAuMTkwNzU0IDMwLjQyIDAuMDA2MzQ1MDkgMzAuOTIzMSAwLjAwMzQxNzk3IDMxLjQ0MzdWODUuNTU2MkMwLjAwMzQxNzk3IDg2Ljc2NzIgMC45ODY5MyA4Ny43NSAyLjE5ODc2IDg3Ljc1SDI5LjI3NDZWMi4xOTM3NUMyOS4yNzQ2IDAuOTQ3NyAyOC4yMzU1IC0wLjA0OTcyNSAyNi45ODg1IDAuMDAyOTI1TDI2Ljk5MTQgMFoiIGZpbGw9IiM4MEVEOTkiLz4KICAgIDxwYXRoIGQ9Ik0zMS41NiA4N0MzMi4xNzE4IDg2Ljk3MSAzMi43NDU1IDg2LjY5MyAzMy4xNDA3IDg2LjIyNUw1OC4wMjEyIDU2Ljk3NDlDNTguMzU3OCA1Ni41NzcxIDU4LjU0NTEgNTYuMDc0IDU4LjU0NTEgNTUuNTUzM1YzMS40NDM3QzU4LjU0NTEgMzAuMjMyOCA1Ny41NjE2IDI5LjI1IDU2LjM0OTggMjkuMjVIMjkuMjc2OVY4NC44MDZDMjkuMjc2OSA4Ni4wNTIgMzAuMzE2IDg3LjA1IDMxLjU2MjkgODYuOTk3SDMxLjU2WiIgZmlsbD0iIzIyNTc3QSIvPgogICAgPHBhdGggZD0iTTAuNjQ2OTEyIDg0LjAwNkMtMC43MzQ2ODggODUuMzg2NiAwLjI0Mjk3IDg3Ljc0NzEgMi4xOTgyOCA4Ny43NUgyOS4yNzQxVjU4LjVMMC42NDY5MTIgODQuMDA2WiIgZmlsbD0iIzM4QTNBNSIvPgogICAgPHBhdGggZD0iTTU3LjkwNDEgMzIuOTk0QzU5LjI4NTcgMzEuNjEzNCA1OC4zMDggMjkuMjUyOSA1Ni4zNTI3IDI5LjI1SDI5LjI3MzlWNTguNUw1Ny45MDQxIDMyLjk5NFoiIGZpbGw9IiMzOEEzQTUiLz4KICAgIDwhLS0gREFSSSBsZXR0ZXJzIC0gd2hpdGUgLS0+CiAgICA8cGF0aCBkPSJNNjQuMzk2NSA2NC4zMzgzSDc0LjIzNDVDODMuOTMyMSA2NC4zMzgzIDkxLjgwMzEgNTYuNDc4OCA5MS44MDMxIDQ2Ljc5NDFDOTEuODAzMSAzNy4xMDk1IDgzLjkzMjEgMjkuMjUgNzQuMjM0NSAyOS4yNUg2NC4zOTY1VjY0LjMzODNaTTY4LjY1ODQgNjAuNTQ3NVYzMy4wNDA4SDc0LjIzNDVDODEuNjM3MiAzMy4wNDA4IDg3LjUzODMgMzkuMTIxOSA4Ny41MzgzIDQ2Ljc5NzFDODcuNTM4MyA1NC40NzIzIDgxLjYzNDMgNjAuNTUzNCA3NC4yMzQ1IDYwLjU1MzRINjguNjU4NFY2MC41NDc1WiIgZmlsbD0id2hpdGUiLz4KICAgIDxwYXRoIGQ9Ik0xMTkuODE4IDY0LjMzODNIMTI0LjQ1NUwxMTAuMzU1IDI5LjI1SDEwNS41NzVMOTEuNDc1MSA2NC4zMzgzSDk2LjExMTdMOTguOTY4NSA1Ni45OTM2SDExNi45NTlMMTE5LjgxNSA2NC4zMzgzSDExOS44MThaTTEwMC4zMyA1My4zOUwxMDcuOTY2IDMzLjY0NjNMMTE1LjYwMyA1My4zOUgxMDAuMzNaIiBmaWxsPSJ3aGl0ZSIvPgogICAgPHBhdGggZD0iTTE0Mi4yNTggNDguNDMyMkMxNDYuNzU0IDQ3LjY4MzQgMTUwLjIyMyA0My44OTI2IDE1MC4yMjMgMzkuMTY4N0MxNTAuMjIzIDMzLjY0OTIgMTQ1Ljc3MyAyOS4yNSAxNDAuMzM4IDI5LjI1SDEyNy40NTZWNjQuMzM4M0gxMzEuNzE3VjQ4LjY2NjJIMTM3Ljk0OUwxNDYuMzM1IDY0LjMzODNIMTUxLjExNUwxNDIuMjYxIDQ4LjQzMjJIMTQyLjI1OFpNMTMxLjcxNyA0NS4xNTYyVjMzLjAzNzlIMTQwLjI0NEMxNDMuNTY5IDMzLjAzNzkgMTQ2LjI4OSAzNS43MDU1IDE0Ni4yODkgMzkuMDcyMkMxNDYuMjg5IDQyLjQzODggMTQzLjYxOSA0NS4xNTMyIDE0MC4yNDQgNDUuMTUzMkgxMzEuNzE3VjQ1LjE1NjJaIiBmaWxsPSJ3aGl0ZSIvPgogICAgPHBhdGggZD0iTTE1My43MzUgNjQuMzM4M0gxNTcuOTk3VjI5LjI1SDE1My43MzVWNjQuMzM4M1oiIGZpbGw9IndoaXRlIi8+CiAgICA8IS0tICJEYXJpIE1vdGlvbiIgdGV4dCBpbiB3aGl0ZSBiZWxvdyAtLT4KICAgIDx0ZXh0IHg9IjY0IiB5PSI4MiIgZm9udC1mYW1pbHk9IkJhcmxvdyBDb25kZW5zZWQsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTEiIGZvbnQtd2VpZ2h0PSI2MDAiIGZpbGw9IndoaXRlIiBsZXR0ZXItc3BhY2luZz0iMiI+REFSSSBNT1RJT048L3RleHQ+CiAgPC9nPgogIDxkZWZzPgogICAgPGNsaXBQYXRoIGlkPSJjbGlwMF8xMTFfOCI+CiAgICAgIDxyZWN0IHdpZHRoPSIxNTgiIGhlaWdodD0iMTAwIiBmaWxsPSJ3aGl0ZSIvPgogICAgPC9jbGlwUGF0aD4KICA8L2RlZnM+Cjwvc3ZnPg==" style="height:38px;width:auto;"/>
    </div>
    <div style="flex:1;padding:10px 14px;display:flex;flex-direction:column;gap:6px;overflow:hidden;">
      <div style="display:flex;gap:8px;flex:1;overflow:hidden;min-height:0;">

        <!-- BODY SCAN -->
        <div style="position:relative;flex-shrink:0;display:flex;align-items:center;justify-content:center;height:100%;">
          <div style="position:relative;height:100%;max-height:280px;aspect-ratio:500/1214;">
            <img src="data:image/png;base64,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" style="position:absolute;top:0;left:0;width:100%;height:100%;object-fit:fill;mix-blend-mode:screen;filter:sepia(1) hue-rotate(150deg) saturate(2) brightness(0.9);"/>
            {{ body_scan_dots }}
            <div style="position:absolute;bottom:0;left:50%;transform:translateX(-50%);display:flex;gap:5px;z-index:3;white-space:nowrap;padding:2px 5px;background:rgba(4,16,30,0.75);border-radius:5px;">
              <span style="display:flex;align-items:center;gap:2px;font-size:6.5px;color:#6B8DAD;font-family:'Barlow Condensed',sans-serif;"><span style="width:6px;height:6px;border-radius:50%;background:#3B82F6;display:inline-block;"></span>0-20%</span>
              <span style="display:flex;align-items:center;gap:2px;font-size:6.5px;color:#6B8DAD;font-family:'Barlow Condensed',sans-serif;"><span style="width:6px;height:6px;border-radius:50%;background:#22c55e;display:inline-block;"></span>20-40%</span>
              <span style="display:flex;align-items:center;gap:2px;font-size:6.5px;color:#6B8DAD;font-family:'Barlow Condensed',sans-serif;"><span style="width:6px;height:6px;border-radius:50%;background:#F59E0B;display:inline-block;"></span>40-60%</span>
              <span style="display:flex;align-items:center;gap:2px;font-size:6.5px;color:#6B8DAD;font-family:'Barlow Condensed',sans-serif;"><span style="width:6px;height:6px;border-radius:50%;background:#EF4444;display:inline-block;"></span>60%+</span>
            </div>
          </div>
        </div>

        <!-- SCORES -->
        <div style="flex:1;display:flex;flex-direction:column;gap:4px;justify-content:center;">
          <div style="font-size:9px;color:#5A7A9A;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:1px;">Athleticism Scores</div>
          <div style="display:flex;align-items:center;gap:7px;">
            <div style="font-size:9px;color:#5A7A9A;text-transform:uppercase;letter-spacing:0.8px;width:76px;flex-shrink:0;">Athleticism</div>
            <div style="flex:1;background:rgba(255,255,255,0.06);border-radius:4px;height:5px;overflow:hidden;"><div style="height:100%;border-radius:4px;background:#38A3A5;width:{{ dari.current.athleticism }}%;"></div></div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:20px;width:44px;text-align:right;color:#38A3A5;">{{ dari.current.athleticism }}</div>
          </div>
          <div style="display:flex;align-items:center;gap:7px;">
            <div style="font-size:9px;color:#5A7A9A;text-transform:uppercase;letter-spacing:0.8px;width:76px;flex-shrink:0;">Functionality</div>
            <div style="flex:1;background:rgba(255,255,255,0.06);border-radius:4px;height:5px;overflow:hidden;"><div style="height:100%;border-radius:4px;background:#38A3A5;width:{{ dari.current.functionality }}%;"></div></div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:20px;width:44px;text-align:right;color:#38A3A5;">{{ dari.current.functionality }}</div>
          </div>
          <div style="display:flex;align-items:center;gap:7px;">
            <div style="font-size:9px;color:#5A7A9A;text-transform:uppercase;letter-spacing:0.8px;width:76px;flex-shrink:0;">Explosiveness</div>
            <div style="flex:1;background:rgba(255,255,255,0.06);border-radius:4px;height:5px;overflow:hidden;"><div style="height:100%;border-radius:4px;background:#38A3A5;width:{{ dari.current.explosiveness }}%;"></div></div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:20px;width:44px;text-align:right;color:#38A3A5;">{{ dari.current.explosiveness }}</div>
          </div>
          <div style="display:flex;align-items:center;gap:7px;">
            <div style="font-size:9px;color:#5A7A9A;text-transform:uppercase;letter-spacing:0.8px;width:76px;flex-shrink:0;">Dysfunction</div>
            <div style="flex:1;background:rgba(255,255,255,0.06);border-radius:4px;height:5px;overflow:hidden;"><div style="height:100%;border-radius:4px;background:#EF4444;width:{{ dari.current.dysfunction * 10 }}%;"></div></div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:20px;width:44px;text-align:right;color:#EF4444;">{{ dari.current.dysfunction }}</div>
          </div>
          <div style="height:1px;background:rgba(255,255,255,0.07);margin:2px 0;"></div>
          <div style="font-size:9px;color:#5A7A9A;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:1px;">Vertical Jump (Dari)</div>
          <div style="display:flex;align-items:flex-end;gap:4px;">
            <span style="font-family:'Bebas Neue',sans-serif;font-size:56px;line-height:1;color:#38A3A5;">{{ dari.vj }}</span>
            <span style="font-size:13px;color:#5A7A9A;margin-bottom:10px;">IN</span>
          </div>
        </div>

      </div>
    </div>
  </div>

  <!-- ── VALD ── -->
  <div class="pwrx-panel">
    <div class="pwrx-panel-header orange">VALD Force Decks — CMJ</div>
    <div class="pwrx-panel-body">

      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px;margin-bottom:10px;">
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.purple }};">{{ vald.current.jump_height }}<span class="pwrx-stat-unit">in</span></div>
          <div class="pwrx-stat-label">Jump Height</div>
          {{ chip_jump }}
        </div>
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.blueL }};">{{ "%.2f"|format(vald.current.peak_power/1000) }}<span class="pwrx-stat-unit">kW</span></div>
          <div class="pwrx-stat-label">Peak Power</div>
          {{ chip_power }}
        </div>
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.green }};">{{ vald.current.rsi_mod }}<span class="pwrx-stat-unit">m/s</span></div>
          <div class="pwrx-stat-label">RSI-Mod</div>
          {{ chip_rsi }}
        </div>
      </div>

      <div class="pwrx-section-label">Jump Height (in)</div>
      {{ chart_vald_jump_height }}
      <div class="pwrx-divider"></div>
      <div class="pwrx-section-label">RSI-Modified</div>
      {{ chart_vald_rsi }}
      <div class="pwrx-divider"></div>
      <div class="pwrx-section-label">Peak Power (W)</div>
      {{ chart_vald_power }}
    </div>
  </div>

  <!-- ── ArmCare ── -->
  <div class="pwrx-panel">
    <div class="pwrx-panel-header blue">ArmCare — Throwing Arm Health</div>
    <div class="pwrx-panel-body">

      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-bottom:10px;">
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.orange }};">{{ arm.current.arm_score }}</div>
          <div class="pwrx-stat-label">Arm Score</div>
          {{ chip_arm_score }}
        </div>
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.blueL }};">{{ arm.current.total_strength|int }}<span class="pwrx-stat-unit">lbs</span></div>
          <div class="pwrx-stat-label">Strength</div>
          {{ chip_arm_strength }}
        </div>
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.green }};">{{ arm.current.balance }}</div>
          <div class="pwrx-stat-label">Balance</div>
          <span style="font-size:9px;color:#22c55e;">Normal</span>
        </div>
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.amber }};">{{ arm.current.svr }}</div>
          <div class="pwrx-stat-label">SVR</div>
          {{ chip_arm_svr }}
        </div>
      </div>

      <div class="pwrx-section-label">Last 4 Sessions — Arm Score</div>
      {{ chart_arm_score }}
      <div class="pwrx-divider"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div>
          <div class="pwrx-section-label">Total Strength (lbs)</div>
          {{ chart_arm_strength }}
        </div>
        <div>
          <div class="pwrx-section-label">SVR Trend</div>
          {{ chart_arm_svr }}
        </div>
      </div>
      <div class="pwrx-divider"></div>
      <div class="pwrx-section-label">Shoulder Balance History (1.0 = ideal)</div>
      {{ chart_arm_balance }}
    </div>
  </div>

  <!-- ── InBody ── -->
  <div class="pwrx-panel">
    <div class="pwrx-panel-header orange">InBody — Body Composition</div>
    <div class="pwrx-panel-body">
      {% if inbody.available %}
      <!-- Donut centred full-width -->
      <div style="display:flex;justify-content:center;margin-bottom:12px;">
        {{ chart_inbody_donut }}
      </div>
      <!-- 5 stat boxes in one row -->
      <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:7px;margin-bottom:10px;">
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:#fff;">{{ inbody.weight }}<span class="pwrx-stat-unit">lbs</span></div>
          <div class="pwrx-stat-label">Body Weight</div>
        </div>
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.blueL }};">{{ inbody.smm }}<span class="pwrx-stat-unit">lbs</span></div>
          <div class="pwrx-stat-label">Skeletal Muscle</div>
        </div>
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.orange }};">{{ inbody.pbf }}<span class="pwrx-stat-unit">%</span></div>
          <div class="pwrx-stat-label">Body Fat %</div>
        </div>
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.amber }};">{{ inbody.bmi }}</div>
          <div class="pwrx-stat-label">BMI</div>
        </div>
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.green }};">{{ inbody.score }}<span class="pwrx-stat-unit">/100</span></div>
          <div class="pwrx-stat-label">InBody Score</div>
        </div>
      </div>
      <!-- Extra metrics row -->
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-bottom:10px;">
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.blueL }};font-size:14px;">{{ inbody.bmr }}</div>
          <div class="pwrx-stat-label">BMR (kcal)</div>
        </div>
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.amber }};font-size:14px;">{{ inbody.vfl }}</div>
          <div class="pwrx-stat-label">Visceral Fat</div>
        </div>
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.green }};font-size:14px;">{{ inbody.phase_angle }}°</div>
          <div class="pwrx-stat-label">Phase Angle</div>
        </div>
        <div class="pwrx-stat-box">
          <div class="pwrx-stat-value" style="color:{{ C.purple }};font-size:14px;">{{ inbody.ecw_tbw_ratio }}</div>
          <div class="pwrx-stat-label">ECW/TBW</div>
        </div>
      </div>
      <div class="pwrx-divider"></div>
      <div class="pwrx-section-label">Segmental Lean Mass (lbs)</div>
      {{ chart_segments }}
      {% else %}
      <div style="display:flex;align-items:center;justify-content:center;height:200px;color:#4a6a8a;font-size:13px;flex-direction:column;gap:8px;">
        <div style="font-size:28px;opacity:0.4;">⊘</div>
        <div>No InBody data available</div>
      </div>
      {% endif %}
    </div>
  </div>

</div><!-- /pwrx-grid -->

<!-- DECLINE FLAGS -->
<div class="pwrx-flags">
  <div class="pwrx-flag-panel">
    <div class="pwrx-flag-header">
      &#9888; Performance Flags — &ge;10% Change from Previous Session
    </div>
    {% if decline_flags %}
    <div class="pwrx-flag-grid">
      {% for f in decline_flags %}
      <div class="pwrx-flag-item">
        <div class="pwrx-flag-source">{{ f.source }}</div>
        <div class="pwrx-flag-metric">{{ f.metric }}</div>
        <div class="pwrx-flag-values">
          <span class="pwrx-flag-prev">{{ f.prev }}</span>
          <span class="pwrx-flag-arrow">&#8594;</span>
          <span class="pwrx-flag-curr">{{ f.curr }}</span>
          <span class="pwrx-flag-pct">{{ f.pct }}</span>
        </div>
      </div>
      {% endfor %}
    </div>
    {% else %}
    <div class="pwrx-no-flags">
      &#10003; No significant declines detected across tracked metrics.
    </div>
    {% endif %}
  </div>
</div>

<!-- CROSS-MODULE SUMMARY BAR -->
<div class="pwrx-summary-strip">
  <div class="pwrx-panel">
    <div class="pwrx-panel-header orange">Cross-Module Summary — {{ report_date }} Latest</div>
    <div class="pwrx-summary-grid">
      {% for kpi in summary_kpis %}
      <div class="pwrx-summary-kpi">
        <div style="font-size:8px;color:{{ C.orange }};text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;">{{ kpi.src }}</div>
        <div style="font-size:15px;font-weight:900;color:{{ kpi.color }};line-height:1.1;font-family:monospace;">{{ kpi.val }}</div>
        <div style="font-size:8px;color:{{ C.greyL }};text-transform:uppercase;letter-spacing:0.8px;margin-top:3px;">{{ kpi.lbl }}</div>
        <div style="margin-top:4px;">{{ kpi.chip }}</div>
      </div>
      {% endfor %}
    </div>
  </div>
</div>

<!-- FOOTER -->
<div class="pwrx-footer">
  PITCHINGWRX · CONFIDENTIAL ATHLETE REPORT · {{ athlete_name|upper }} · {{ report_date|upper }}
</div>

</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
# RENDER
# ─────────────────────────────────────────────────────────────────────────────

def build_focus_list(data):
    colors   = [C["orange"], C["amber"], C["blueL"], C["purple"], C["green"]]
    enriched = data["dari"].get("focus_areas_enriched")
    if enriched:
        return [
            dict(f, rank=i+1, color=colors[i % len(colors)])
            for i, f in enumerate(enriched)
        ]
    # Fallback for sample/hardcoded data
    areas = data["dari"]["focus_areas"]
    return [
        {"rank": i+1, "name": area, "color": colors[i % len(colors)],
         "sessions_seen": 1, "total_sessions": 1,
         "score_trend": None, "trend_dir": None, "latest_score": 0}
        for i, area in enumerate(areas)
    ]


def build_summary_kpis(data):
    d   = data["dari"]["current"]
    dari_trend = data["dari"]["trend"]
    dp  = dari_trend[-2] if len(dari_trend) >= 2 else dari_trend[-1]
    v   = data["vald"]["current"]
    vp  = data["vald"]["prev"]
    a   = data["arm"]["current"]
    ap  = data["arm"]["prev"]
    ib  = data["inbody"]
    return [
        {"src": "DARI",    "lbl": "Athleticism",   "val": str(d["athleticism"]),   "color": C["orange"], "chip": chip(d["athleticism"],   dp["athleticism"])},
        {"src": "DARI",    "lbl": "Explosiveness",  "val": str(d["explosiveness"]), "color": C["green"],  "chip": chip(d["explosiveness"],  dp["explosiveness"])},
        {"src": "VALD",    "lbl": "Jump Height",    "val": f'{v["jump_height"]}"',  "color": C["purple"], "chip": chip(v["jump_height"],    vp["jump_height"])},
        {"src": "VALD",    "lbl": "Peak Power",     "val": f'{v["peak_power"]:,} W',"color": C["blueL"],  "chip": chip(v["peak_power"],     vp["peak_power"])},
        {"src": "VALD",    "lbl": "RSI-Modified",   "val": str(v["rsi_mod"]),       "color": C["green"],  "chip": chip(v["rsi_mod"],        vp["rsi_mod"])},
        {"src": "ArmCare", "lbl": "Arm Score",      "val": str(a["arm_score"]),     "color": C["orange"], "chip": chip(a["arm_score"],      ap["arm_score"])},
        {"src": "ArmCare", "lbl": "SVR",             "val": str(a["svr"]),           "color": C["amber"],  "chip": chip(a["svr"],            ap["svr"])},
        {"src": "InBody",  "lbl": "Body Fat %",     "val": f'{ib["pbf"]}%' if ib.get("available") else "N/A", "color": C["orange"], "chip": ""},
    ]


def build_decline_flags(data):
    """
    Check key tracked metrics for meaningful change from the previous session.
    Each metric can be flagged by a percent-change threshold, an absolute-point
    threshold, or either (whichever triggers first). Dysfunction and Body Fat %
    flag on increase (higher = worse); all others flag on decline.
    """
    flags = []

    def _check(source, metric, curr_val, prev_val, fmt="{:.1f}",
               invert=False, pct_threshold=0.10, point_threshold=None):
        if prev_val is None or curr_val is None:
            return
        try:
            c = float(curr_val)
            p = float(prev_val)
        except (TypeError, ValueError):
            return
        if p == 0 or c == 0:
            return

        delta = c - p
        pct   = delta / abs(p)

        # Percent-based trigger: only fires in the unfavorable direction
        pct_triggered = (pct >= pct_threshold) if invert else (pct <= -pct_threshold)

        # Point-based trigger (optional): fires on magnitude of change in
        # EITHER direction — display color (red/green) is decided separately
        point_triggered = False
        if point_threshold is not None:
            point_triggered = abs(delta) >= point_threshold

        if pct_triggered or point_triggered:
            direction = f"+{pct*100:.1f}%" if pct > 0 else f"{pct*100:.1f}%"
            # For invert metrics (higher = worse, e.g. dysfunction, body fat),
            # a decrease is the improvement. For normal metrics, an increase is.
            is_improvement = (delta < 0) if invert else (delta > 0)
            flags.append({
                "source": source,
                "metric": metric,
                "prev":   fmt.format(p),
                "curr":   fmt.format(c),
                "pct":    direction,
                "trend":  "improve" if is_improvement else "decline",
            })

    # ── DARI ──────────────────────────────────────────────────────────────────
    # Overall score: flag on 3-point change OR 5% change (either triggers)
    # All other tracked DARI metrics: 7.5% change threshold
    dari_trend = data["dari"]["trend"]
    if len(dari_trend) >= 2:
        c, p = dari_trend[-1], dari_trend[-2]
        _check("Dari", "Overall Score",  c["overall"],       p["overall"],
               pct_threshold=0.05, point_threshold=3)
        _check("Dari", "Vulnerability", c["athleticism"],   p["athleticism"],   pct_threshold=0.075)
        _check("Dari", "Functionality", c["functionality"], p["functionality"], pct_threshold=0.075)
        _check("Dari", "Explosiveness", c["explosiveness"], p["explosiveness"], pct_threshold=0.075)
        _check("Dari", "Dysfunction",   c["dysfunction"],   p["dysfunction"],
               invert=True, pct_threshold=0.075)  # higher = worse

    # ── VALD ──────────────────────────────────────────────────────────────────
    # 10% change threshold across the board
    vald_trend = data["vald"]["trend"]
    if len(vald_trend) >= 2:
        c, p = vald_trend[-1], vald_trend[-2]
        _check("Vald", "Jump Height",  c["jump_height"], p["jump_height"], "{:.2f}", pct_threshold=0.10)
        _check("Vald", "Peak Power",   c["peak_power"],  p["peak_power"],  "{:,.0f}", pct_threshold=0.10)
        _check("Vald", "RSI-Modified", c["rsi_mod"],     p["rsi_mod"],     "{:.3f}", pct_threshold=0.10)

    # ── ArmCare ───────────────────────────────────────────────────────────────
    # Arm Score: 5-point change threshold
    # Total Strength: 10% change threshold
    # SVR/Balance/Velo: unchanged 10% default
    arm_trend = data["arm"]["trend"]
    if len(arm_trend) >= 2:
        c, p = arm_trend[-1], arm_trend[-2]
        _check("ArmCare", "Arm Score",      c["arm_score"],      p["arm_score"],
               point_threshold=5, pct_threshold=999)  # point-only: disable pct path
        _check("ArmCare", "Total Strength", c["total_strength"], p["total_strength"], "{:.1f}", pct_threshold=0.10)
        _check("ArmCare", "SVR",            c["svr"],            p["svr"],            "{:.2f}", pct_threshold=0.10)
        _check("ArmCare", "Balance",        c["balance"],        p["balance"],        "{:.2f}", pct_threshold=0.10)
        _check("ArmCare", "Velo",           c.get("velo", 0),    p.get("velo", 0),    "{:.1f}", pct_threshold=0.10)

    # ── InBody ────────────────────────────────────────────────────────────────
    # Body Fat %: flag on 3-point change (point-only). Increase = worse (invert=True)
    inbody_trend = (data.get("inbody") or {}).get("trend") or []
    if len(inbody_trend) >= 2:
        c, p = inbody_trend[-1], inbody_trend[-2]
        _check("InBody", "Body Fat %", c["pbf"], p["pbf"], "{:.1f}",
               invert=True, point_threshold=3, pct_threshold=999)  # point-only: disable pct path

    # Sort by absolute % change — largest first
    flags.sort(key=lambda f: -abs(float(f["pct"].replace("%","").replace("+",""))))

    return flags



def build_body_scan_dots(data: dict) -> str:
    """Build HTML for joint vulnerability dots on the body scan."""
    joints = data.get("dari", {}).get("joints", {})

# ── Embedded Assets (base64) ──────────────────────────────────────────────────
PWRX_LOGO    = "data:image/png;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/4gHYSUNDX1BST0ZJTEUAAQEAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADb/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAH0AfQDASIAAhEBAxEB/8QAHQABAAICAwEBAAAAAAAAAAAAAAYHBQgBAgQDCf/EAFcQAAEDAwEFBAYHBAYGBQoHAAEAAgMEBREGBxIhMUETUWFxCBQigZGhFSMyQlKxwWJygpIWM6KywtEXJENT0uEJJVWj8CY0NmNzdJOUs+I1RmRlg6Tx/8QAGwEBAAIDAQEAAAAAAAAAAAAAAAQFAgMGAQf/xAA/EQABAwIDAwoFAwMEAQUBAAABAAIDBBEFITESQVEGEyJhcYGRwdHwFDKhseEjM0IVUvEWJDRTciU1YoKSov/aAAwDAQACEQMRAD8A0yRERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERFyGuP3T8EXtrrlFlLdp+/XJnaW6y3GsYfvQUr3j4gFe6LQ+rpX7rdN3Np/wDWUzmf3gFgZWDUgLc2mlf8rSe4qO5CZClrdm+tTysM/vewfquz9mutmtLjYpcDulYT8A5YfEw/3DxCz+Aqf+t3gVEPf8kUim0Rq6E+3p25u/cp3O/IFfGTSGq4270umbyxve6hkA/urMSxnRw8Vi6lmb8zCO4rAovtPDPDK6OWJ8b2nDmOaQQfEFfLBWa0EEarhERF4iIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIu+Edx6pnjnqpDpXR+oNSPH0Vb5Xw5w6of7MTeWcuPAkZzgZPgsXPawbTjYLbFE+VwZGCSdwUdPl819aeGWombDBE+SR5DWMY0lzieQAHMq8dM7FrZTFst/r5K14wTDT5jjz1BcfacPLcKsiyWOz2SDsbTbqajbuhrjGwBzwOW877TvMkqoqMbgjyYNo+AXUUXJCrns6Uhg8T4Ba9WLZbrC57rn29tvicCd+rfuYx0LBl497VOLPsQoIwHXe9VExLfsU0bY9137zt7I9wVur2221XO5P3LfQVVUevZRFwHmRyVRLjNVKbMFuwLp4OS+HUrdqU7XW42H0t9VBrTs50ZbXNdHZIZ5GtwX1DnS73iWuJbnyAUit9voLc0st9DTUjSckQQtjHwaAp/btl+rqvBko4aNp6zyj8m5PyUjoNjU7gDX3uNne2GAu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ihhcObXTN3vhnK1mrLlcazPrlfV1GefbTOf+ZXkUd+Of2s8Sp8PIv/tl8B5k+Svy7bV9MUhLaQ1Ne8cuzi3W583Y+QKh152v3mo3mWygpqJp5OeTK/8AQfIqtFi75qOxWRrjdbrS0rmt3uzfIDIR3hg9o+4KK7EKuc7LPoPZVpHyewujbty523uOXkFJrzfrxeX71zuNRU8chrn4YPJo4D3BY1VfqDbPYaTejtFFU3GQHAe/6mIjHME5cePQtHmq41HtO1ZecxiuFvgOPqqIGP8AtZL+PUb2PBbYcIqpztSZduqwqOUuHUTdiHpW3NFh4+l1fOqNX6d03G/6UuMTZ2jhTR+3M44yBuDlnoXYHiqj1htiuteJKWwU4tlOct7d5D53DiMj7rMgjlkgjg5VYS4niSVwQMq7pcIggzPSPX6LkMR5UVlXdrDsN4DXxX1qqiapqJJ6meSaWRxc+SRxc5xPMkniSviChXCtVzZN8yiIiLxERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERche62XW5WuZ01uuFXRyEYL4JnRkjuy0heHqmV4QDqsmuc03Cndp2q6zoOzbJcI62NgwGVMTXZ83DDifMqSW7bjcGZ+kbDTTjp6vKYsfzB6qHOUHDoosmH00nzMH2+ys4Mbr4PklPfn91fNu222ORhNwtNwp3d0JZKPiSz8l74dsmkJHkOjucQ73wN/wALytdyuFFdg1IdAR3qwZysxJurge4eS2UbtZ0SedfO3zpn/oEk2s6Jb9mvnf8Au0z/ANQtbEWH9DpevxW3/WGIdXh+Vsa/a/o9o4SVz/KD/MrzP206UA9mju7iOX1MYB/7xa9+5cZWTcFpRuPisHcrsROhA7ld1Xtyp2ve2l07K9v3XyVYafe0MP5qO3LbNqmpjdHSQ26iBPsyMhL3gd3tktP8qrTI7kUhmGUrNGDvz+6gzcoMRm+aUjsy+ykd41rqq79oK6+VrmSN3Xxxv7ONw8WNw35KOuJJ4knzK4JHRcFTGsa0WaLKrkmklN3uJPWbrhERZLUiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIv/9k="
DARI_LOGO    = "data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNTgiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMTU4IDEwMCIgZmlsbD0ibm9uZSI+CiAgPGcgY2xpcC1wYXRoPSJ1cmwoI2NsaXAwXzExMV84KSI+CiAgICA8IS0tIEJyYWNrZXQgbWFyayAtIGNvbG9yZWQgLS0+CiAgICA8cGF0aCBkPSJNMjYuOTkxNCAwQzI2LjM3OTcgMC4wMjYzMjUgMjUuODA2IDAuMzA0MiAyNS40MTA4IDAuNzcyMkwwLjUyNzM3MiAzMC4wMjIyQzAuMTkwNzU0IDMwLjQyIDAuMDA2MzQ1MDkgMzAuOTIzMSAwLjAwMzQxNzk3IDMxLjQ0MzdWODUuNTU2MkMwLjAwMzQxNzk3IDg2Ljc2NzIgMC45ODY5MyA4Ny43NSAyLjE5ODc2IDg3Ljc1SDI5LjI3NDZWMi4xOTM3NUMyOS4yNzQ2IDAuOTQ3NyAyOC4yMzU1IC0wLjA0OTcyNSAyNi45ODg1IDAuMDAyOTI1TDI2Ljk5MTQgMFoiIGZpbGw9IiM4MEVEOTkiLz4KICAgIDxwYXRoIGQ9Ik0zMS41NiA4N0MzMi4xNzE4IDg2Ljk3MSAzMi43NDU1IDg2LjY5MyAzMy4xNDA3IDg2LjIyNUw1OC4wMjEyIDU2Ljk3NDlDNTguMzU3OCA1Ni41NzcxIDU4LjU0NTEgNTYuMDc0IDU4LjU0NTEgNTUuNTUzM1YzMS40NDM3QzU4LjU0NTEgMzAuMjMyOCA1Ny41NjE2IDI5LjI1IDU2LjM0OTggMjkuMjVIMjkuMjc2OVY4NC44MDZDMjkuMjc2OSA4Ni4wNTIgMzAuMzE2IDg3LjA1IDMxLjU2MjkgODYuOTk3SDMxLjU2WiIgZmlsbD0iIzIyNTc3QSIvPgogICAgPHBhdGggZD0iTTAuNjQ2OTEyIDg0LjAwNkMtMC43MzQ2ODggODUuMzg2NiAwLjI0Mjk3IDg3Ljc0NzEgMi4xOTgyOCA4Ny43NUgyOS4yNzQxVjU4LjVMMC42NDY5MTIgODQuMDA2WiIgZmlsbD0iIzM4QTNBNSIvPgogICAgPHBhdGggZD0iTTU3LjkwNDEgMzIuOTk0QzU5LjI4NTcgMzEuNjEzNCA1OC4zMDggMjkuMjUyOSA1Ni4zNTI3IDI5LjI1SDI5LjI3MzlWNTguNUw1Ny45MDQxIDMyLjk5NFoiIGZpbGw9IiMzOEEzQTUiLz4KICAgIDwhLS0gREFSSSBsZXR0ZXJzIC0gd2hpdGUgLS0+CiAgICA8cGF0aCBkPSJNNjQuMzk2NSA2NC4zMzgzSDc0LjIzNDVDODMuOTMyMSA2NC4zMzgzIDkxLjgwMzEgNTYuNDc4OCA5MS44MDMxIDQ2Ljc5NDFDOTEuODAzMSAzNy4xMDk1IDgzLjkzMjEgMjkuMjUgNzQuMjM0NSAyOS4yNUg2NC4zOTY1VjY0LjMzODNaTTY4LjY1ODQgNjAuNTQ3NVYzMy4wNDA4SDc0LjIzNDVDODEuNjM3MiAzMy4wNDA4IDg3LjUzODMgMzkuMTIxOSA4Ny41MzgzIDQ2Ljc5NzFDODcuNTM4MyA1NC40NzIzIDgxLjYzNDMgNjAuNTUzNCA3NC4yMzQ1IDYwLjU1MzRINjguNjU4NFY2MC41NDc1WiIgZmlsbD0id2hpdGUiLz4KICAgIDxwYXRoIGQ9Ik0xMTkuODE4IDY0LjMzODNIMTI0LjQ1NUwxMTAuMzU1IDI5LjI1SDEwNS41NzVMOTEuNDc1MSA2NC4zMzgzSDk2LjExMTdMOTguOTY4NSA1Ni45OTM2SDExNi45NTlMMTE5LjgxNSA2NC4zMzgzSDExOS44MThaTTEwMC4zMyA1My4zOUwxMDcuOTY2IDMzLjY0NjNMMTE1LjYwMyA1My4zOUgxMDAuMzNaIiBmaWxsPSJ3aGl0ZSIvPgogICAgPHBhdGggZD0iTTE0Mi4yNTggNDguNDMyMkMxNDYuNzU0IDQ3LjY4MzQgMTUwLjIyMyA0My44OTI2IDE1MC4yMjMgMzkuMTY4N0MxNTAuMjIzIDMzLjY0OTIgMTQ1Ljc3MyAyOS4yNSAxNDAuMzM4IDI5LjI1SDEyNy40NTZWNjQuMzM4M0gxMzEuNzE3VjQ4LjY2NjJIMTM3Ljk0OUwxNDYuMzM1IDY0LjMzODNIMTUxLjExNUwxNDIuMjYxIDQ4LjQzMjJIMTQyLjI1OFpNMTMxLjcxNyA0NS4xNTYyVjMzLjAzNzlIMTQwLjI0NEMxNDMuNTY5IDMzLjAzNzkgMTQ2LjI4OSAzNS43MDU1IDE0Ni4yODkgMzkuMDcyMkMxNDYuMjg5IDQyLjQzODggMTQzLjYxOSA0NS4xNTMyIDE0MC4yNDQgNDUuMTUzMkgxMzEuNzE3VjQ1LjE1NjJaIiBmaWxsPSJ3aGl0ZSIvPgogICAgPHBhdGggZD0iTTE1My43MzUgNjQuMzM4M0gxNTcuOTk3VjI5LjI1SDE1My43MzVWNjQuMzM4M1oiIGZpbGw9IndoaXRlIi8+CiAgICA8IS0tICJEYXJpIE1vdGlvbiIgdGV4dCBpbiB3aGl0ZSBiZWxvdyAtLT4KICAgIDx0ZXh0IHg9IjY0IiB5PSI4MiIgZm9udC1mYW1pbHk9IkJhcmxvdyBDb25kZW5zZWQsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTEiIGZvbnQtd2VpZ2h0PSI2MDAiIGZpbGw9IndoaXRlIiBsZXR0ZXItc3BhY2luZz0iMiI+REFSSSBNT1RJT048L3RleHQ+CiAgPC9nPgogIDxkZWZzPgogICAgPGNsaXBQYXRoIGlkPSJjbGlwMF8xMTFfOCI+CiAgICAgIDxyZWN0IHdpZHRoPSIxNTgiIGhlaWdodD0iMTAwIiBmaWxsPSJ3aGl0ZSIvPgogICAgPC9jbGlwUGF0aD4KICA8L2RlZnM+Cjwvc3ZnPg=="
VALD_LOGO    = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNzMiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCA3MyAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGcgY2xpcC1wYXRoPSJ1cmwoI2NsaXAwXzEwNTc2XzEwODApIj4KPHBhdGggZD0iTTU1Ljg3MzcgMC4wMjM0Mzc1SDYwLjc0MTVDNjIuMTc3NCAwLjAyMzQzNzUgNjMuNjEzMyAwLjAyMzQzNzUgNjUuMDQ5MiAwLjAyMzQzNzVDNjguODk5MyAwLjAzOTA4NTQgNzIuMTk3MSAyLjc3NzQ3IDcyLjg5MTQgNi41NDA4QzczLjY5NjIgMTAuODk4NyA3MC45MDMzIDE0Ljk5MDcgNjYuNTMyNCAxNS44NTkxQzY2LjE1MzcgMTUuOTM3NCA2NS43NTkzIDE1Ljk4NDMgNjUuMzcyNyAxNS45ODQzQzYyLjI5NTggMTYgNTkuMjE4OCAxNS45OTIxIDU2LjE0MTkgMTZDNTYuMDQ3MiAxNiA1NS45NjA1IDE1Ljk5MjEgNTUuODY1OCAxNS45ODQzQzU1Ljc0NzQgMTUuNTg1MyA1NS43NTUzIDAuMzk4OTg4IDU1Ljg4MTYgMC4wMjM0Mzc1SDU1Ljg3MzdaTTU5LjIzNDYgMTIuNTU3NEM1OS40MDgyIDEyLjU2NTIgNTkuNTM0NCAxMi41ODA5IDU5LjY1MjggMTIuNTgwOUM2MC44OTkzIDEyLjU4MDkgNjIuMTUzNyAxMi41ODA5IDYzLjQwMDMgMTIuNTgwOUM2NC4xMDI1IDEyLjU4MDkgNjQuODEyNSAxMi42MiA2NS41MDY4IDEyLjU0OTZDNjcuNzA4IDEyLjMyMjcgNjkuNzI3NyAxMC4zNTExIDY5LjU2MiA3LjYzNjE1QzY5LjQyIDUuMzU5MzggNjcuNDMxOSAzLjQ4MTYzIDY1LjA0MTMgMy40NTgxNkM2My4yMjY3IDMuNDM0NjggNjEuNDIgMy40NTAzMyA1OS42MDU0IDMuNDUwMzNDNTkuNDg3MSAzLjQ1MDMzIDU5LjM2ODcgMy40NzM4IDU5LjIyNjcgMy40ODk0NVYxMi41NjUyTDU5LjIzNDYgMTIuNTU3NFoiIGZpbGw9IiNGRjdBMDAiLz4KPHBhdGggZD0iTTI5LjU3IDBDMzEuNjY4NiA1LjI4OSAzMy43NTk0IDEwLjU3MDIgMzUuODczOCAxNS44OTA1SDMxLjg0MjJDMzEuNTQyNCAxNS4xNTUgMzEuMjUwNSAxNC40Mjc0IDMwLjk0MjggMTMuNjYwNkgyNS4xMjAzQzI1LjQzNTkgMTIuODYyNiAyNS43MTk5IDEyLjE0MjggMjYuMDE5NyAxMS4zNzZIMzAuMDQzNEMyOS4xMzYxIDkuMDI4ODUgMjguMjIwOSA2Ljc1OTkgMjcuMzIxNSA0LjQ4MzEzQzI3LjI4MiA0LjQ4MzEzIDI3LjI0MjYgNC40ODMxMyAyNy4yMDMxIDQuNDc1MzFDMjUuNjcyNiA4LjI2OTkzIDI0LjE0MiAxMi4wNzI0IDIyLjYxMTQgMTUuODkwNUgxOC42NTA5QzIwLjc1NzQgMTAuNTc4IDIyLjg0ODEgNS4yOTY4MiAyNC45NDY3IDBDMjYuNDkzMSAwIDI4LjAxNTggMCAyOS41Nzc5IDBMMjkuNTcgMFoiIGZpbGw9IiNGRjdBMDAiLz4KPHBhdGggZD0iTTQuMDMxNTYgMEM1LjUzMDU3IDMuNzc4OTcgNy4wMzc0OCA3LjU4MTQyIDguNTkxNzIgMTEuNDkzNEM5LjQ2NzQ2IDkuNTIxNzYgMTAuMTc3NSA3LjU5NzA3IDEwLjk0MjggNS43MDM2N0MxMS43MDgxIDMuODEwMjcgMTIuNDQ5NyAxLjkwOTA1IDEzLjE5OTIgMEgxNy4yMzA4QzE1LjEyNDMgNS4zMjgxMiAxMy4wMzM1IDEwLjYwOTMgMTAuOTQyOCAxNS44OTA1SDYuMjk1ODZDNC4yMDUxMyAxMC42MjQ5IDIuMTE0NCA1LjM0Mzc3IDAgMEg0LjAzMTU2WiIgZmlsbD0iI0ZGN0EwMCIvPgo8cGF0aCBkPSJNMzkuODU4MSAwLjAyMzQzNzVINDMuMjgyMlYxMi40OTQ4SDUyLjMzOTRDNTEuODczOSAxMy42Njg0IDUxLjQ0IDE0Ljc3MTYgNTAuOTk4MiAxNS44OTgzSDM5Ljg3MzlDMzkuODM0NSAxMC42MjQ5IDM5Ljg0MjQgNS4zNTE1NSAzOS44NTgxIDAuMDMxMjYxNVYwLjAyMzQzNzVaIiBmaWxsPSIjRkY3QTAwIi8+CjwvZz4KPGRlZnM+CjxjbGlwUGF0aCBpZD0iY2xpcDBfMTA1NzZfMTA4MCI+CjxyZWN0IHdpZHRoPSI3MyIgaGVpZ2h0PSIxNiIgZmlsbD0id2hpdGUiLz4KPC9jbGlwUGF0aD4KPC9kZWZzPgo8L3N2Zz4K"
ARMCARE_LOGO = "data:image/webp;base64,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"
INBODY_LOGO  = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDA5NiIgaGVpZ2h0PSIxMTY2IiB2aWV3Qm94PSIwIDAgNDA5NiAxMTY2IiBmaWxsPSJub25lIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPg0KPGcgY2xpcC1wYXRoPSJ1cmwoI2NsaXAwXzI0NjZfOTQpIj4NCjxwYXRoIGQ9Ik0xMDEyIDBDMTQ4My4xIDAgMTQ4My4xIDAgMTUwNC43NSA1LjYyNUMxNTA1LjczIDUuODc1ODggMTUwNi43MSA2LjEyNjc3IDE1MDcuNzIgNi4zODUyNUMxNTI1LjIgMTEuMDI5MiAxNTQyLjE2IDE3LjI0NjcgMTU1OCAyNkMxNTU4LjggMjYuNDMxNSAxNTU5LjYgMjYuODYzIDE1NjAuNDIgMjcuMzA3NkMxNTczLjMyIDM0LjMwMzIgMTU4NS4zOCA0Mi4wMzQ5IDE1OTcgNTFDMTU5Ny43MSA1MS41NDMgMTU5OC40MSA1Mi4wODYgMTU5OS4xNCA1Mi42NDU1QzE2MTEuMiA2Mi4wMTQ0IDE2MjIuMjYgNzIuMTk3OCAxNjMyIDg0QzE2MzIuNDEgODQuNDkyNCAxNjMyLjgyIDg0Ljk4NDggMTYzMy4yNSA4NS40OTIyQzE2NTMuNjEgMTA5Ljk0IDE2NjkuNDIgMTM2LjQ3NyAxNjc5LjEyIDE2Ni44MTJDMTY3OS41MSAxNjguMDE3IDE2NzkuNTEgMTY4LjAxNyAxNjc5LjkxIDE2OS4yNDZDMTY4NC40MyAxODMuMzA3IDE2ODguMDUgMTk3LjMzMSAxNjkwIDIxMkMxNjkwLjA5IDIxMi42MzQgMTY5MC4xOCAyMTMuMjY3IDE2OTAuMjcgMjEzLjkyQzE2OTIuMTIgMjI3LjU5MyAxNjkyLjM0IDI0MS4yMDMgMTY5Mi4zMiAyNTQuOTg2QzE2OTIuMzEgMjU4LjU5OSAxNjkyLjM0IDI2Mi4yMTEgMTY5Mi4zNiAyNjUuODI0QzE2OTIuNCAyODEuNDIgMTY5MS4zMSAyOTYuNTc3IDE2ODkgMzEyQzE2ODguNzEgMzEzLjkzNSAxNjg4LjcxIDMxMy45MzUgMTY4OC40MSAzMTUuOTA5QzE2ODcuOTQgMzE4LjgwOSAxNjg3LjQgMzIxLjY4NCAxNjg2LjgxIDMyNC41NjJDMTY4Ni41IDMyNi4wNzkgMTY4Ni41IDMyNi4wNzkgMTY4Ni4xOSAzMjcuNjI3QzE2ODMuOTQgMzM4LjE1MSAxNjgwLjU5IDM0OC4yNjEgMTY3Ni45NCAzNTguMzczQzE2NzYuMTEgMzYwLjcwNSAxNjc1LjMgMzYzLjA0NCAxNjc0LjUgMzY1LjM5MUMxNjY5LjMgMzgwLjQwMSAxNjYxLjg0IDM5NC41MjYgMTY1MiA0MDdDMTY1MS4yNCA0MDguMDIxIDE2NTAuNDggNDA5LjA0MiAxNjQ5LjcgNDEwLjA5NEMxNjQwLjI2IDQyMi43ODkgMTYyOS4yNyA0MzYuMTU2IDE2MTYgNDQ1QzE2MTYuNDkgNDQ1LjMwMSAxNjE2Ljk4IDQ0NS42MDEgMTYxNy40OSA0NDUuOTExQzE2MzIuOTcgNDU1LjQyIDE2NDcuODMgNDY1LjQwMyAxNjYxIDQ3OEMxNjYxLjY5IDQ3OC42NDIgMTY2Mi4zOSA0NzkuMjg0IDE2NjMuMSA0NzkuOTQ1QzE2NjguNTIgNDg1LjExMSAxNjcyLjcxIDQ5MC44ODcgMTY3NyA0OTdDMTY3Ny43NiA0OTguMDI3IDE2NzguNTIgNDk5LjA1NSAxNjc5LjMgNTAwLjExM0MxNzA3LjIxIDUzNy44NDcgMTcyMi4wNSA1ODEuNzA3IDE3MjggNjI4QzE3MjguMDkgNjI4LjY5OCAxNzI4LjE4IDYyOS4zOTUgMTcyOC4yNyA2MzAuMTE0QzE3MjkuMzkgNjQwLjE3MyAxNzI5LjE4IDY1MC4zMDggMTcyOS4yIDY2MC40MTRDMTcyOS4yMSA2NjEuNDQzIDE3MjkuMjEgNjYyLjQ3MiAxNzI5LjIxIDY2My41MzJDMTcyOS4yMyA2NjguOTg4IDE3MjkuMjQgNjc0LjQ0NCAxNzI5LjI0IDY3OS44OTlDMTcyOS4yNCA2ODQuMzU4IDE3MjkuMjYgNjg4LjgxNyAxNzI5LjI4IDY5My4yNzVDMTcyOS42NCA3NjQuNDA0IDE3MTUuMjQgODI2Ljg1MiAxNjY2LjA1IDg4MC43MjNDMTY2NC4yOSA4ODIuNjc0IDE2NjIuNjEgODg0LjY2IDE2NjAuOTQgODg2LjY4OEMxNjU4LjI2IDg4OS44MjkgMTY1NS4zMSA4OTIuNDc5IDE2NTIuMTYgODk1LjE0MUMxNjUwLjcxIDg5Ni4zODggMTY0OS4yOSA4OTcuNjcgMTY0Ny45IDg5OC45ODRDMTYzOS45IDkwNi41MTYgMTYzMS4wMyA5MTIuNzcxIDE2MjIgOTE5QzE2MjEuMjYgOTE5LjUxNSAxNjIwLjUyIDkyMC4wMyAxNjE5Ljc2IDkyMC41NjFDMTU4Ny44IDk0Mi42MTkgMTU0OC4zNiA5NTUuMjk5IDE1MTAgOTYwQzE1MDkuMyA5NjAuMDg4IDE1MDguNTkgOTYwLjE3NyAxNTA3Ljg3IDk2MC4yNjhDMTQ5OC4zMyA5NjEuMjk3IDE0ODguNzcgOTYxLjEzNiAxNDc5LjE5IDk2MS4xMkMxNDc3LjE4IDk2MS4xMjEgMTQ3NS4xNiA5NjEuMTIyIDE0NzMuMTUgOTYxLjEyM0MxNDY3LjYyIDk2MS4xMjUgMTQ2Mi4xIDk2MS4xMjEgMTQ1Ni41NyA5NjEuMTE2QzE0NTAuNTIgOTYxLjExMiAxNDQ0LjQ3IDk2MS4xMTMgMTQzOC40MSA5NjEuMTE0QzE0MjcuMzQgOTYxLjExNCAxNDE2LjI2IDk2MS4xMTEgMTQwNS4xOCA5NjEuMTA0QzEzOTAuOTMgOTYxLjA5NyAxMzc2LjY3IDk2MS4wOTUgMTM2Mi40MiA5NjEuMDk1QzEzMjYuNTUgOTYxLjA4OSAxMjkwLjY4IDk2MS4wNzUgMTI1NC44MSA5NjEuMDYyQzExNzQuNjggOTYxLjA0MiAxMDk0LjU2IDk2MS4wMjEgMTAxMiA5NjFDMTAxMiA2NDMuODcgMTAxMiAzMjYuNzQgMTAxMiAwWk0xMTkxIDE3MEMxMTkxIDIzMy42OSAxMTkxIDI5Ny4zOCAxMTkxIDM2M0MxMjMyLjMzIDM2My4xMTcgMTIzMi4zMyAzNjMuMTE3IDEyNzMuNjYgMzYzLjE5NUMxMjc5LjI0IDM2My4yMDMgMTI4NC44MyAzNjMuMjExIDEyOTAuNDEgMzYzLjIyQzEyOTEuMTEgMzYzLjIyMSAxMjkxLjgxIDM2My4yMjIgMTI5Mi41NCAzNjMuMjIzQzEzMDMuOCAzNjMuMjQgMTMxNS4wNyAzNjMuMjcyIDEzMjYuMzQgMzYzLjMwOUMxMzM3LjkyIDM2My4zNDYgMTM0OS41IDM2My4zNjggMTM2MS4wOCAzNjMuMzc2QzEzNjcuNTggMzYzLjM4MiAxMzc0LjA4IDM2My4zOTQgMTM4MC41OCAzNjMuNDIzQzEzODYuNyAzNjMuNDUgMTM5Mi44MyAzNjMuNDU4IDEzOTguOTYgMzYzLjQ1MkMxNDAxLjIgMzYzLjQ1NCAxNDAzLjQzIDM2My40NjEgMTQwNS42NyAzNjMuNDc3QzE0MjIuMjQgMzYzLjU4NiAxNDM4LjI2IDM2Mi41MjEgMTQ1My40NCAzNTUuMTg4QzE0NTQuMTggMzU0Ljg0IDE0NTQuOTMgMzU0LjQ5MiAxNDU1LjY5IDM1NC4xMzRDMTQ3OC44MiAzNDMuMTExIDE0OTYuMyAzMjQuMjM5IDE1MDUgMzAwLjA0MkMxNTA1LjY5IDI5OC4wMzQgMTUwNi4zNSAyOTYuMDIxIDE1MDcgMjk0QzE1MDcuNTEgMjkyLjQwNyAxNTA3LjUxIDI5Mi40MDcgMTUwOC4wNCAyOTAuNzgxQzE1MTQuMzUgMjY2Ljk3IDE1MTAuMyAyMzkuMDkyIDE0OTguMTUgMjE3Ljc1NEMxNDkzLjc1IDIxMC44ODcgMTQ4OC42MiAyMDQuODg0IDE0ODMgMTk5QzE0ODIuMSAxOTcuOTg3IDE0ODIuMSAxOTcuOTg3IDE0ODEuMTggMTk2Ljk1M0MxNDY0LjcxIDE3OS4xMjUgMTQ0MS41NyAxNzEuODAyIDE0MTggMTcwQzE0MTQuNzMgMTY5Ljg3NyAxNDExLjQ2IDE2OS44NjkgMTQwOC4xOCAxNjkuODhDMTQwNy4yNCAxNjkuODc5IDE0MDYuMzEgMTY5Ljg3OCAxNDA1LjM0IDE2OS44NzdDMTQwMi4yNCAxNjkuODc2IDEzOTkuMTMgMTY5Ljg4MSAxMzk2LjAzIDE2OS44ODZDMTM5My43OSAxNjkuODg3IDEzOTEuNTUgMTY5Ljg4NyAxMzg5LjMxIDE2OS44ODZDMTM4My4yNiAxNjkuODg2IDEzNzcuMiAxNjkuODkyIDEzNzEuMTUgMTY5Ljg5OUMxMzY0LjgxIDE2OS45MDUgMTM1OC40OCAxNjkuOTA1IDEzNTIuMTQgMTY5LjkwN0MxMzQxLjUxIDE2OS45MDkgMTMzMC44OSAxNjkuOTE2IDEzMjAuMjYgMTY5LjkyNUMxMzA5LjMyIDE2OS45MzQgMTI5OC4zOCAxNjkuOTQxIDEyODcuNDQgMTY5Ljk0NUMxMjg2Ljc1IDE2OS45NDUgMTI4Ni4wNyAxNjkuOTQ2IDEyODUuMzcgMTY5Ljk0NkMxMjc5LjQzIDE2OS45NDggMTI3My41IDE2OS45NSAxMjY3LjU2IDE2OS45NTJDMTI0Mi4wNCAxNjkuOTYyIDEyMTYuNTIgMTY5Ljk4MiAxMTkxIDE3MFpNMTE5MSA1MzVDMTE5MSA2MTkuMTUgMTE5MSA3MDMuMyAxMTkxIDc5MEMxMjUxLjM2IDc5MC4wOTMgMTI1MS4zNiA3OTAuMDkzIDEzMTIuOTQgNzkwLjE4OEMxMzMxLjk3IDc5MC4yMjggMTMzMS45NyA3OTAuMjI4IDEzNTEuMzkgNzkwLjI3QzEzNjIuOCA3OTAuMjggMTM2Mi44IDc5MC4yOCAxMzc0LjIxIDc5MC4yODZDMTM3OS4yOCA3OTAuMjg5IDEzODQuMzQgNzkwLjMgMTM4OS40MSA3OTAuMzE3QzEzOTUuODkgNzkwLjMzNyAxNDAyLjM3IDc5MC4zNDMgMTQwOC44NSA3OTAuMzM5QzE0MTEuMjIgNzkwLjM0IDE0MTMuNTkgNzkwLjM0NiAxNDE1Ljk1IDc5MC4zNThDMTQzMi4wMSA3OTAuNDMzIDE0NDcuNTYgNzg5Ljc0OCAxNDYyLjg4IDc4NC40MzhDMTQ2My42IDc4NC4xODggMTQ2NC4zMyA3ODMuOTM5IDE0NjUuMDggNzgzLjY4M0MxNDc4Ljg4IDc3OC43MjYgMTQ5MS44IDc3MS40NTUgMTUwMyA3NjJDMTUwMy45OSA3NjEuMTcgMTUwNC45OSA3NjAuMzQgMTUwNi4wMSA3NTkuNDg0QzE1MzAuNDYgNzM4LjQwNyAxNTQ1LjQgNzA3LjM4MyAxNTQ3Ljg1IDY3NS4zMjlDMTU0OS45OSA2NDEuMDYxIDE1NDIuNCA2MDYuNzAxIDE1MTkuNDYgNTgwLjIyN0MxNDk2LjUxIDU1NC4yMzkgMTQ2Ni44NCA1MzcuNjM2IDE0MzIgNTM1QzE0MjguNTUgNTM0Ljg3NSAxNDI1LjEgNTM0Ljg2OSAxNDIxLjY1IDUzNC44OEMxNDIwLjY2IDUzNC44NzkgMTQxOS42NyA1MzQuODc4IDE0MTguNjUgNTM0Ljg3N0MxNDE1LjM1IDUzNC44NzUgMTQxMi4wNCA1MzQuODgxIDE0MDguNzQgNTM0Ljg4NkMxNDA2LjMzIDUzNC44ODcgMTQwMy45MSA1MzQuODg3IDE0MDEuNSA1MzQuODg2QzEzOTUuMDUgNTM0Ljg4NiAxMzg4LjYgNTM0Ljg5MiAxMzgyLjE1IDUzNC44OTlDMTM3Ni4wOSA1MzQuOTA0IDEzNzAuMDQgNTM0LjkwNSAxMzYzLjk4IDUzNC45MDVDMTM0Ni4yOCA1MzQuOTExIDEzMjguNTggNTM0LjkyNSAxMzEwLjg4IDUzNC45MzhDMTI3MS4zMiA1MzQuOTU4IDEyMzEuNzYgNTM0Ljk3OSAxMTkxIDUzNVoiIGZpbGw9ImJsYWNrIi8+DQo8cGF0aCBkPSJNMzA4NCAwQzMxNDMuMDcgMCAzMjAyLjE0IDAgMzI2MyAwQzMyNjMgMzE3LjEzIDMyNjMgNjM0LjI2IDMyNjMgOTYxQzMyMDMuOTMgOTYxIDMxNDQuODYgOTYxIDMwODQgOTYxQzMwODMuNjcgOTU4LjAzIDMwODMuMzQgOTU1LjA2IDMwODMgOTUyQzMwODIuMDEgOTUyLjI0OSAzMDgyLjAxIDk1Mi4yNDkgMzA4MC45OSA5NTIuNTAzQzMwNzcuODMgOTUzLjI4NyAzMDc0LjY3IDk1NC4wNSAzMDcxLjUgOTU0LjgxMkMzMDcwLjQ2IDk1NS4wNzQgMzA2OS40MiA5NTUuMzM1IDMwNjguMzUgOTU1LjYwNEMzMDQ4LjE2IDk2MC40MTUgMzAyNy44MyA5NjEuNDQ4IDMwMDcuMTQgOTYxLjQwNEMzMDA0LjY2IDk2MS40MSAzMDAyLjE3IDk2MS40MTcgMjk5OS42OCA5NjEuNDI1QzI5OTMuNjggOTYxLjQ0MSAyOTg3LjY5IDk2MS40NDMgMjk4MS43IDk2MS40MzhDMjk3Ni44MSA5NjEuNDM0IDI5NzEuOTMgOTYxLjQzNSAyOTY3LjA0IDk2MS40NEMyOTY2LjM0IDk2MS40NDEgMjk2NS42NCA5NjEuNDQyIDI5NjQuOTIgOTYxLjQ0M0MyOTYzLjQ5IDk2MS40NDQgMjk2Mi4wNiA5NjEuNDQ2IDI5NjAuNjQgOTYxLjQ0N0MyOTQ3LjMzIDk2MS40NjEgMjkzNC4wMiA5NjEuNDU2IDI5MjAuNzIgOTYxLjQ0NEMyOTA4LjYyIDk2MS40MzQgMjg5Ni41MSA5NjEuNDQ3IDI4ODQuNDEgOTYxLjQ3MUMyODcxLjkxIDk2MS40OTYgMjg1OS40IDk2MS41MDUgMjg0Ni44OSA5NjEuNDk4QzI4MzkuOTEgOTYxLjQ5NSAyODMyLjkyIDk2MS40OTcgMjgyNS45MyA5NjEuNTE1QzI3NjkuMTMgOTYxLjY0OSAyNzY5LjEzIDk2MS42NDkgMjc0NyA5NTdDMjc0NS40IDk1Ni42NjUgMjc0NS40IDk1Ni42NjUgMjc0My43NiA5NTYuMzIyQzI3MjIuNTggOTUxLjc4OCAyNzAyLjg3IDk0My45NjcgMjY4My4yNSA5MzQuOTM4QzI2ODIuNjIgOTM0LjY1MiAyNjgyIDkzNC4zNjcgMjY4MS4zNSA5MzQuMDczQzI2NjkuNDYgOTI4LjYyNiAyNjU4Ljk1IDkyMS43MjcgMjY0OC42MyA5MTMuNzVDMjY0Ny45IDkxMy4xOTQgMjY0Ny4xOCA5MTIuNjM4IDI2NDYuNDQgOTEyLjA2NUMyNjI2LjcxIDg5Ni43MjYgMjYwOC4zNiA4NzkuNTYgMjU5NCA4NTlDMjU5My40MiA4NTguMTc0IDI1OTMuNDIgODU4LjE3NCAyNTkyLjgzIDg1Ny4zMzJDMjU4NS44MyA4NDcuMjc3IDI1NzkuNjcgODM2Ljg2MiAyNTc0IDgyNkMyNTczLjU0IDgyNS4xMjggMjU3My4wOSA4MjQuMjU3IDI1NzIuNjIgODIzLjM1OUMyNTUzIDc4NS4zNDEgMjU0Ni40OCA3NDUuMzIzIDI1NDYuNiA3MDIuOTUzQzI1NDYuNjEgNjk5LjEzNSAyNTQ2LjYgNjk1LjMxNyAyNTQ2LjU5IDY5MS40OTlDMjU0Ni41OSA2ODUuMDk1IDI1NDYuNTkgNjc4LjY5MSAyNTQ2LjYxIDY3Mi4yODdDMjU0Ni42MyA2NjQuOTUgMjU0Ni42MiA2NTcuNjE0IDI1NDYuNiA2NTAuMjc4QzI1NDYuNTkgNjQzLjkwNiAyNTQ2LjU5IDYzNy41MzQgMjU0Ni42IDYzMS4xNjJDMjU0Ni42IDYyNy4zODkgMjU0Ni42IDYyMy42MTUgMjU0Ni41OSA2MTkuODQxQzI1NDYuNTQgNTk4LjcyNSAyNTQ3LjU2IDU3OC4wNDEgMjU1Mi4yNSA1NTcuMzc1QzI1NTIuNDYgNTU2LjQzMyAyNTUyLjY3IDU1NS40OTEgMjU1Mi44OSA1NTQuNTIxQzI1NTkuODQgNTI0Ljc2NSAyNTcyLjYzIDQ5NC44MTIgMjU5MS4xOCA0NzAuNDAyQzI1OTMuMDEgNDY3Ljk4NCAyNTk0LjczIDQ2NS41MDkgMjU5Ni40NCA0NjNDMjYwNi4xNyA0NDkuMDk2IDI2MTcuODggNDM1Ljc5NyAyNjMxIDQyNUMyNjMxLjk0IDQyNC4xNzQgMjYzMi44OCA0MjMuMzQ3IDI2MzMuODQgNDIyLjQ5NkMyNjQxLjc2IDQxNS41NDkgMjY1MC4wOCA0MDkuNTk0IDI2NTkgNDA0QzI2NTkuNjEgNDAzLjYxNiAyNjYwLjIyIDQwMy4yMzIgMjY2MC44NSA0MDIuODM2QzI2NjUuMTggNDAwLjEzNSAyNjY5LjU3IDM5Ny41NCAyNjc0IDM5NUMyNjc0LjYzIDM5NC42MzYgMjY3NS4yNiAzOTQuMjcxIDI2NzUuOTEgMzkzLjg5NkMyNzE3Ljg0IDM2OS45IDI3NjMuMzQgMzYyLjg0MiAyODEwLjkgMzYyLjg1NUMyODEzLjE3IDM2Mi44NTIgMjgxNS40MyAzNjIuODQ4IDI4MTcuNyAzNjIuODQ1QzI4MjMuODIgMzYyLjgzNiAyODI5LjkzIDM2Mi44MzMgMjgzNi4wNSAzNjIuODMzQzI4MzkuODkgMzYyLjgzMiAyODQzLjcyIDM2Mi44MyAyODQ3LjU2IDM2Mi44MjdDMjg2MC4yOCAzNjIuODE4IDI4NzMuMDEgMzYyLjgxNCAyODg1Ljc0IDM2Mi44MTVDMjg4Ni40MiAzNjIuODE1IDI4ODcuMTEgMzYyLjgxNSAyODg3LjgxIDM2Mi44MTVDMjg4OC44NCAzNjIuODE1IDI4ODguODQgMzYyLjgxNSAyODg5Ljg4IDM2Mi44MTVDMjkwMC45NSAzNjIuODE1IDI5MTIuMDEgMzYyLjgwNiAyOTIzLjA4IDM2Mi43OTJDMjkzNC41IDM2Mi43NzcgMjk0NS45MiAzNjIuNzcgMjk1Ny4zNSAzNjIuNzcxQzI5NjMuNzMgMzYyLjc3MSAyOTcwLjEyIDM2Mi43NjkgMjk3Ni41MSAzNjIuNzU4QzI5ODIuNTMgMzYyLjc0OCAyOTg4LjU1IDM2Mi43NDggMjk5NC41NyAzNjIuNzU1QzI5OTYuNzUgMzYyLjc1NyAyOTk4Ljk0IDM2Mi43NTQgMzAwMS4xMyAzNjIuNzQ4QzMwMjEuMSAzNjIuNjk2IDMwNDEuMjggMzYzLjI3OCAzMDYwLjg4IDM2Ny40MzhDMzA2MS45MSAzNjcuNjQyIDMwNjIuOTUgMzY3Ljg0NiAzMDY0LjAxIDM2OC4wNTdDMzA3MC44IDM2OS40MjYgMzA3Ny4yOCAzNzEuMTY4IDMwODQgMzczQzMwODQgMjQ5LjkxIDMwODQgMTI2LjgyIDMwODQgMFpNMjc0Ni44MSA1NjIuMjVDMjcyOC4yMiA1ODMuNDk1IDI3MjUuNjggNjA2LjAxNCAyNzI1LjcgNjMzLjA1MUMyNzI1LjcgNjM1LjM5NyAyNzI1LjY5IDYzNy43NDMgMjcyNS42OSA2NDAuMDg4QzI3MjUuNjggNjQ0Ljk5MSAyNzI1LjY4IDY0OS44OTQgMjcyNS42OCA2NTQuNzk3QzI3MjUuNjkgNjYxLjA0MyAyNzI1LjY3IDY2Ny4yOSAyNzI1LjY1IDY3My41MzdDMjcyNS42NCA2NzguMzc4IDI3MjUuNjMgNjgzLjIxOSAyNzI1LjY0IDY4OC4wNjFDMjcyNS42NCA2OTAuMzYyIDI3MjUuNjMgNjkyLjY2MyAyNzI1LjYyIDY5NC45NjVDMjcyNS41MiA3MjIuMDc3IDI3MzAuMTMgNzQ1Ljg4NiAyNzQ5Ljg0IDc2NS45NjFDMjc1Ni42NyA3NzIuNjU5IDI3NjQuMjUgNzc3Ljg2NSAyNzcyLjY5IDc4Mi4zMTJDMjc3My4yNiA3ODIuNjI2IDI3NzMuODQgNzgyLjk0IDI3NzQuNDMgNzgzLjI2M0MyNzg4LjUgNzkwLjI2NiAyODAzLjk3IDc5MC41ODYgMjgxOS4zMiA3OTAuNTE4QzI4MjEuNDEgNzkwLjUyMyAyODIzLjQ5IDc5MC41MyAyODI1LjU4IDc5MC41MzlDMjgzMS4xOSA3OTAuNTU3IDI4MzYuOCA3OTAuNTUgMjg0Mi40MSA3OTAuNTM3QzI4NDguMzEgNzkwLjUyNyAyODU0LjIxIDc5MC41MzcgMjg2MC4xMiA3OTAuNTQzQzI4NzAuMDIgNzkwLjU1IDI4NzkuOTMgNzkwLjU0MSAyODg5LjgzIDc5MC41MjFDMjkwMS4yNSA3OTAuNSAyOTEyLjY3IDc5MC41MDcgMjkyNC4wOSA3OTAuNTI5QzI5MzMuOTMgNzkwLjU0NyAyOTQzLjc3IDc5MC41NSAyOTUzLjYxIDc5MC41MzlDMjk1OS40NyA3OTAuNTMzIDI5NjUuMzQgNzkwLjUzMiAyOTcxLjIgNzkwLjU0NUMyOTc2LjcxIDc5MC41NTcgMjk4Mi4yMiA3OTAuNTQ5IDI5ODcuNzMgNzkwLjUyNkMyOTg5Ljc0IDc5MC41MiAyOTkxLjc1IDc5MC41MjIgMjk5My43NiA3OTAuNTMxQzMwMTguOTMgNzkwLjYzMiAzMDQwLjc2IDc4NC4yNTYgMzA1OS40NCA3NjYuNTg2QzMwODAuNzggNzQ1LjA0OSAzMDg0LjMyIDcxOS4wODggMzA4NC4zIDY5MC4wMTZDMzA4NC4zMSA2ODcuNzg4IDMwODQuMzEgNjg1LjU2MSAzMDg0LjMxIDY4My4zMzNDMzA4NC4zMiA2NzguNjggMzA4NC4zMiA2NzQuMDI3IDMwODQuMzIgNjY5LjM3NEMzMDg0LjMxIDY2My40NTYgMzA4NC4zMyA2NTcuNTM4IDMwODQuMzUgNjUxLjYyQzMwODQuMzcgNjQ3LjAyMyAzMDg0LjM3IDY0Mi40MjYgMzA4NC4zNiA2MzcuODI5QzMwODQuMzYgNjM1LjY1IDMwODQuMzcgNjMzLjQ3IDMwODQuMzggNjMxLjI5QzMwODQuNDkgNjAzLjA0MSAzMDc5LjE4IDU4MC43MzMgMzA2MCA1NTlDMzA1OS40NiA1NTguMzY0IDMwNTguOTIgNTU3LjcyOSAzMDU4LjM2IDU1Ny4wNzRDMzA0NC44NyA1NDIuMjg2IDMwMjQuMzggNTM1LjY5MiAzMDA1IDUzNEMzMDAyLjEzIDUzMy44NzQgMjk5OS4yNiA1MzMuODYgMjk5Ni4zOCA1MzMuODY2QzI5OTUuNTYgNTMzLjg2NCAyOTk0Ljc0IDUzMy44NjIgMjk5My45IDUzMy44NTlDMjk5MS4xOCA1MzMuODUzIDI5ODguNDcgNTMzLjg1NCAyOTg1Ljc1IDUzMy44NTVDMjk4My43OSA1MzMuODUyIDI5ODEuODMgNTMzLjg0OCAyOTc5Ljg3IDUzMy44NDVDMjk3NC41NyA1MzMuODM2IDI5NjkuMjcgNTMzLjgzMyAyOTYzLjk2IDUzMy44MzNDMjk2MC42NCA1MzMuODMyIDI5NTcuMzIgNTMzLjgzIDI5NTQgNTMzLjgyN0MyOTQyLjQxIDUzMy44MTggMjkzMC44MSA1MzMuODE0IDI5MTkuMjEgNTMzLjgxNUMyOTA4LjQzIDUzMy44MTUgMjg5Ny42NSA1MzMuODA1IDI4ODYuODcgNTMzLjc4OUMyODc3LjU5IDUzMy43NzYgMjg2OC4zMSA1MzMuNzcxIDI4NTkuMDMgNTMzLjc3MUMyODUzLjQ5IDUzMy43NzEgMjg0Ny45NiA1MzMuNzY5IDI4NDIuNDMgNTMzLjc1OEMyODM3LjIyIDUzMy43NDggMjgzMi4wMSA1MzMuNzQ4IDI4MjYuODEgNTMzLjc1NUMyODI0LjkgNTMzLjc1NyAyODIzIDUzMy43NTQgMjgyMS4xIDUzMy43NDhDMjc5MS41IDUzMy42NiAyNzY3Ljg5IDU0MC4xMTYgMjc0Ni44MSA1NjIuMjVaIiBmaWxsPSJibGFjayIvPg0KPHBhdGggZD0iTTIwMzYuODkgMzYyLjg1NUMyMDM5LjI3IDM2Mi44NTIgMjA0MS42NCAzNjIuODQ5IDIwNDQuMDIgMzYyLjg0NUMyMDUwLjQyIDM2Mi44MzYgMjA1Ni44MyAzNjIuODM0IDIwNjMuMjQgMzYyLjgzM0MyMDY3LjI2IDM2Mi44MzMgMjA3MS4yNyAzNjIuODMgMjA3NS4yOSAzNjIuODI4QzIwODguNjIgMzYyLjgxOSAyMTAxLjk1IDM2Mi44MTQgMjExNS4yOCAzNjIuODE1QzIxMTYuMzYgMzYyLjgxNSAyMTE2LjM2IDM2Mi44MTUgMjExNy40NSAzNjIuODE1QzIxMTguNTMgMzYyLjgxNSAyMTE4LjUzIDM2Mi44MTUgMjExOS42MyAzNjIuODE1QzIxMzEuMjIgMzYyLjgxNiAyMTQyLjgxIDM2Mi44MDYgMjE1NC40IDM2Mi43OTJDMjE2Ni4zNiAzNjIuNzc4IDIxNzguMzMgMzYyLjc3MSAyMTkwLjI5IDM2Mi43NzJDMjE5Ni45OCAzNjIuNzcyIDIyMDMuNjcgMzYyLjc2OSAyMjEwLjM3IDM2Mi43NThDMjIxNi42NyAzNjIuNzQ5IDIyMjIuOTggMzYyLjc0OSAyMjI5LjI4IDM2Mi43NTZDMjIzMS41NyAzNjIuNzU3IDIyMzMuODcgMzYyLjc1NSAyMjM2LjE2IDM2Mi43NDlDMjI1Ni40NyAzNjIuNjk4IDIyNzcuMjMgMzYzLjAxOSAyMjk3LjE5IDM2Ny4xODhDMjI5OC4yNSAzNjcuNDAyIDIyOTkuMyAzNjcuNjE1IDIzMDAuNCAzNjcuODM1QzIzNDAuNzUgMzc2LjMxMiAyMzgwLjczIDM5NC44NzUgMjQxMiA0MjJDMjQxMi44IDQyMi42OTUgMjQxMy42MSA0MjMuMzkgMjQxNC40NCA0MjQuMTA2QzI0MjUuMjMgNDMzLjYxMSAyNDM1LjEgNDQzLjcwOCAyNDQ0IDQ1NUMyNDQ0LjkzIDQ1Ni4xMiAyNDQ1Ljg2IDQ1Ny4yMzcgMjQ0Ni44IDQ1OC4zNTJDMjQ1NC44MiA0NjguMDA1IDI0NjEuNTggNDc4LjIyNSAyNDY4IDQ4OUMyNDY4LjM3IDQ4OS42MDcgMjQ2OC43NCA0OTAuMjE0IDI0NjkuMTIgNDkwLjgzOUMyNDk0LjQ5IDUzMi42OTEgMjUwMC4xNSA1ODMuMDU5IDI1MDAuMTcgNjMwLjg0QzI1MDAuMTcgNjMzLjMzNiAyNTAwLjE3IDYzNS44MzEgMjUwMC4xOCA2MzguMzI3QzI1MDAuMTggNjQzLjU0IDI1MDAuMTkgNjQ4Ljc1NCAyNTAwLjE4IDY1My45NjdDMjUwMC4xOCA2NjAuNTc2IDI1MDAuMiA2NjcuMTg1IDI1MDAuMjIgNjczLjc5NEMyNTAwLjIzIDY3OC45NDYgMjUwMC4yMyA2ODQuMDk4IDI1MDAuMjMgNjg5LjI1MUMyNTAwLjIzIDY5MS42ODMgMjUwMC4yMyA2OTQuMTE2IDI1MDAuMjQgNjk2LjU0OUMyNTAwLjMgNzE3LjIxMyAyNDk5Ljg1IDczOC4wOTMgMjQ5NS44NyA3NTguNDM4QzI0OTUuNjYgNzU5LjU0MSAyNDk1LjQ1IDc2MC42NDQgMjQ5NS4yMyA3NjEuNzhDMjQ4OC41IDc5NS4yMzQgMjQ3NS4xNiA4MjguMzQ5IDI0NTUgODU2QzI0NTQuNTkgODU2LjU1OSAyNDU0LjE5IDg1Ny4xMTcgMjQ1My43NyA4NTcuNjkyQzI0NDUuMzMgODY5LjI1OCAyNDM1LjY0IDg3OS41MzcgMjQyNS40MSA4ODkuNTI4QzI0MjMgODkxLjkgMjQyMyA4OTEuOSAyNDIxLjE4IDg5NC4zNzlDMjM4Ny40MSA5MzQuOTE2IDIzMjMuODMgOTU1LjUxNSAyMjczLjMxIDk2MC43MjFDMjI2My4yNSA5NjEuNTY5IDIyNTMuMTQgOTYxLjQxNiAyMjQzLjA1IDk2MS4zODlDMjI0MC40NSA5NjEuMzkzIDIyMzcuODQgOTYxLjM5OCAyMjM1LjI0IDk2MS40MDVDMjIyOC45NiA5NjEuNDE4IDIyMjIuNjggOTYxLjQxNSAyMjE2LjQxIDk2MS40MDZDMjIxMS4zIDk2MS4zOTkgMjIwNi4xOCA5NjEuMzk5IDIyMDEuMDcgOTYxLjQwMkMyMjAwLjM0IDk2MS40MDIgMjE5OS42IDk2MS40MDMgMjE5OC44NSA5NjEuNDAzQzIxOTcuMzYgOTYxLjQwNCAyMTk1Ljg3IDk2MS40MDUgMjE5NC4zNyA5NjEuNDA2QzIxODAuNDYgOTYxLjQxNSAyMTY2LjU1IDk2MS40MDUgMjE1Mi42NCA5NjEuMzg5QzIxNDAuNzYgOTYxLjM3NSAyMTI4Ljg3IDk2MS4zNzggMjExNi45OSA5NjEuMzkyQzIxMDMuMTIgOTYxLjQwOCAyMDg5LjI1IDk2MS40MTQgMjA3NS4zOCA5NjEuNDA1QzIwNzMuOSA5NjEuNDA0IDIwNzIuNDEgOTYxLjQwMyAyMDcwLjkzIDk2MS40MDJDMjA2OS44MyA5NjEuNDAxIDIwNjkuODMgOTYxLjQwMSAyMDY4LjcxIDk2MS40QzIwNjMuNjIgOTYxLjM5OCAyMDU4LjUzIDk2MS40MDIgMjA1My40NCA5NjEuNDA5QzIwNDYuNTUgOTYxLjQxOSAyMDM5LjY3IDk2MS40MTIgMjAzMi43OSA5NjEuMzk1QzIwMzAuMjggOTYxLjM5MSAyMDI3Ljc4IDk2MS4zOTIgMjAyNS4yNyA5NjEuMzk4QzE5OTUuODIgOTYxLjQ3IDE5NjcuODcgOTU3LjU2NiAxOTQwIDk0OEMxOTM5LjM1IDk0Ny43ODIgMTkzOC43IDk0Ny41NjMgMTkzOC4wMyA5NDcuMzM4QzE5MTEuOCA5MzguNDI0IDE4ODcuNDUgOTI1LjUyOCAxODY2IDkwOEMxODY1LjQ4IDkwNy41ODUgMTg2NC45NyA5MDcuMTcgMTg2NC40MyA5MDYuNzQyQzE4NTIuMjggODk2Ljk1MiAxODQxLjAyIDg4NS45NjcgMTgzMSA4NzRDMTgzMC4yIDg3My4wOTggMTgyOS4zOSA4NzIuMTk2IDE4MjguNTcgODcxLjI2NkMxODE2Ljc1IDg1Ny44ODYgMTgwNy4yOCA4NDIuNzc5IDE3OTkgODI3QzE3OTguNjQgODI2LjMyNiAxNzk4LjI4IDgyNS42NTEgMTc5Ny45IDgyNC45NTZDMTc3Ny42NSA3ODYuNzU0IDE3NzEuNDcgNzQzLjE0NCAxNzcxLjYgNzAwLjQ2NUMxNzcxLjYgNjk2Ljg4NiAxNzcxLjYgNjkzLjMwNyAxNzcxLjU5IDY4OS43MjhDMTc3MS41OSA2ODMuNzI1IDE3NzEuNTkgNjc3LjcyMiAxNzcxLjYxIDY3MS43MTlDMTc3MS42MiA2NjQuODU4IDE3NzEuNjIgNjU3Ljk5NiAxNzcxLjYgNjUxLjEzNUMxNzcxLjU5IDY0NS4xNiAxNzcxLjU5IDYzOS4xODYgMTc3MS41OSA2MzMuMjExQzE3NzEuNiA2MjkuNjggMTc3MS42IDYyNi4xNDggMTc3MS41OSA2MjIuNjE2QzE3NzEuNTQgNjAwLjQwOCAxNzcyLjQgNTc4LjE0NiAxNzc3LjgxIDU1Ni41QzE3NzguMiA1NTQuODk3IDE3NzguMiA1NTQuODk3IDE3NzguNTkgNTUzLjI2MUMxNzgwLjcxIDU0NC42ODQgMTc4My4yNCA1MzYuMzA2IDE3ODYuMjcgNTI4LjAwOUMxNzg2Ljk4IDUyNi4wNTMgMTc4Ny42NSA1MjQuMDg4IDE3ODguMzIgNTIyLjExOEMxNzk5LjQ5IDQ4OS45NDcgMTgxOS45NyA0NjAuMjI2IDE4NDQuNDEgNDM2LjU5NEMxODQ2LjE1IDQzNC45MTMgMTg0Ni4xNSA0MzQuOTEzIDE4NDggNDMyLjQzOEMxODUwLjk2IDQyOC44MjggMTg1NC40MiA0MjUuOTg0IDE4NTggNDIzQzE4NTguNDkgNDIyLjU3OSAxODU4Ljk5IDQyMi4xNTcgMTg1OS40OSA0MjEuNzIzQzE4NzAuMjUgNDEyLjU1OCAxODgxLjgzIDQwNS4xNTIgMTg5NCAzOThDMTg5NS4xNyAzOTcuMzA4IDE4OTUuMTcgMzk3LjMwOCAxODk2LjM2IDM5Ni42MDFDMTkzOS45NCAzNzAuODc2IDE5ODYuOTYgMzYyLjg0MiAyMDM2Ljg5IDM2Mi44NTVaTTE5NzAuNTQgNTYzLjE0OUMxOTU1LjczIDU3OS43NjEgMTk1MC44NCA2MDIuMTE3IDE5NTAuODUgNjIzLjgwMkMxOTUwLjg1IDYyNC43MjUgMTk1MC44NSA2MjUuNjQ5IDE5NTAuODQgNjI2LjZDMTk1MC44MyA2MjkuNjIzIDE5NTAuODMgNjMyLjY0NiAxOTUwLjgzIDYzNS42NjhDMTk1MC44MyA2MzcuNzkzIDE5NTAuODIgNjM5LjkxNyAxOTUwLjgyIDY0Mi4wNDJDMTk1MC44MiA2NDYuNDg2IDE5NTAuODEgNjUwLjkzIDE5NTAuODEgNjU1LjM3NEMxOTUwLjgxIDY2MS4wMzEgMTk1MC44IDY2Ni42ODggMTk1MC43OCA2NzIuMzQ1QzE5NTAuNzcgNjc2LjczMiAxOTUwLjc3IDY4MS4xMTggMTk1MC43NyA2ODUuNTA1QzE5NTAuNzcgNjg3LjU4OSAxOTUwLjc2IDY4OS42NzIgMTk1MC43NiA2OTEuNzU2QzE5NTAuNjIgNzEzLjExMyAxOTUwLjYyIDcxMy4xMTMgMTk1NS4zNyA3MzMuODEzQzE5NTYuMDQgNzM1LjY2NyAxOTU2LjA0IDczNS42NjcgMTk1Ni43MiA3MzcuNTU5QzE5NTcuMTQgNzM4LjY5NSAxOTU3LjU2IDczOS44MyAxOTU4IDc0MUMxOTU4LjMyIDc0MS45NCAxOTU4LjY0IDc0Mi44OCAxOTU4Ljk3IDc0My44NDhDMTk2NS41NyA3NjIuMjQ5IDE5ODMuNDggNzc1LjIxOCAyMDAwLjM5IDc4My40MjZDMjAxMC44MyA3ODcuOTg0IDIwMjAuODUgNzkwLjE0OCAyMDMyLjE3IDc5MC4xNTRDMjAzMy4wOSA3OTAuMTU5IDIwMzQgNzkwLjE2MyAyMDM0Ljk0IDc5MC4xNjhDMjAzOCA3OTAuMTgxIDIwNDEuMDYgNzkwLjE4NyAyMDQ0LjEyIDc5MC4xOTNDMjA0Ni4zMiA3OTAuMjAxIDIwNDguNTIgNzkwLjIwOSAyMDUwLjcxIDc5MC4yMThDMjA1Ny45MyA3OTAuMjQ0IDIwNjUuMTQgNzkwLjI2IDIwNzIuMzUgNzkwLjI3NEMyMDc0Ljg0IDc5MC4yNzkgMjA3Ny4zMyA3OTAuMjg1IDIwNzkuODIgNzkwLjI5QzIwOTAuMTggNzkwLjMxMiAyMTAwLjU1IDc5MC4zMzEgMjExMC45MSA3OTAuMzQyQzIxMTMuNTkgNzkwLjM0NSAyMTE2LjI4IDc5MC4zNDggMjExOC45NyA3OTAuMzUxQzIxMTkuNjMgNzkwLjM1MSAyMTIwLjMgNzkwLjM1MiAyMTIwLjk5IDc5MC4zNTNDMjEzMS43NyA3OTAuMzY1IDIxNDIuNTYgNzkwLjM5OSAyMTUzLjM1IDc5MC40NEMyMTY0LjQ1IDc5MC40ODMgMjE3NS41NSA3OTAuNTA2IDIxODYuNjUgNzkwLjUxMkMyMTkyLjg4IDc5MC41MTUgMjE5OS4xIDc5MC41MjcgMjIwNS4zMiA3OTAuNTZDMjIxMS4xOCA3OTAuNTkgMjIxNy4wNSA3OTAuNTk2IDIyMjIuOTEgNzkwLjU4NEMyMjI1LjA1IDc5MC41ODQgMjIyNy4xOSA3OTAuNTkyIDIyMjkuMzMgNzkwLjYxQzIyNTYuOTcgNzkwLjgyNiAyMjc4LjkzIDc4My4yNzMgMjI5OSA3NjRDMjMwMC4wNiA3NjMuMDIgMjMwMC4wNiA3NjMuMDIgMjMwMS4xNCA3NjIuMDJDMjMxNC41NCA3NDguMzUzIDIzMjAuMTQgNzI1LjgwNSAyMzIwLjE2IDcwNy4zNTJDMjMyMC4xNyA3MDYuMjkxIDIzMjAuMTcgNzA1LjIzIDIzMjAuMTggNzA0LjEzN0MyMzIwLjE5IDcwMC42MzMgMjMyMC4yIDY5Ny4xMjkgMjMyMC4yIDY5My42MjVDMjMyMC4yMSA2OTEuMTc5IDIzMjAuMjEgNjg4LjczMiAyMzIwLjIyIDY4Ni4yODZDMjMyMC4yMyA2ODEuMTU1IDIzMjAuMjQgNjc2LjAyNCAyMzIwLjI0IDY3MC44OTNDMjMyMC4yNCA2NjQuMzQ3IDIzMjAuMjcgNjU3LjgwMiAyMzIwLjMgNjUxLjI1N0MyMzIwLjMyIDY0Ni4yMDEgMjMyMC4zMiA2NDEuMTQ0IDIzMjAuMzIgNjM2LjA4N0MyMzIwLjMzIDYzMy42NzYgMjMyMC4zMyA2MzEuMjY1IDIzMjAuMzUgNjI4Ljg1NEMyMzIwLjQ4IDYwMi40NjggMjMxNi4zNCA1NzkuMjg0IDIyOTcuMzkgNTU5LjMzNkMyMjc1Ljg0IDUzOC4zMTUgMjI1MS4yNCA1MzMuNjc4IDIyMjIuMSA1MzMuNzQyQzIyMjAuMDEgNTMzLjczOSAyMjE3LjkzIDUzMy43MzUgMjIxNS44NCA1MzMuNzMxQzIyMTAuMiA1MzMuNzIyIDIyMDQuNTcgNTMzLjcyNSAyMTk4LjkzIDUzMy43MzJDMjE5My4wMSA1MzMuNzM3IDIxODcuMDkgNTMzLjczMiAyMTgxLjE3IDUzMy43MjlDMjE3MS4yMyA1MzMuNzI1IDIxNjEuMyA1MzMuNzMgMjE1MS4zNiA1MzMuNzRDMjEzOS44OSA1MzMuNzUxIDIxMjguNDMgNTMzLjc0NyAyMTE2Ljk3IDUzMy43MzZDMjEwNy4xIDUzMy43MjcgMjA5Ny4yMyA1MzMuNzI2IDIwODcuMzYgNTMzLjczMUMyMDgxLjQ4IDUzMy43MzQgMjA3NS42IDUzMy43MzQgMjA2OS43MSA1MzMuNzI4QzIwNjQuMTggNTMzLjcyMiAyMDU4LjY1IDUzMy43MjYgMjA1My4xMSA1MzMuNzM4QzIwNTEuMDkgNTMzLjc0IDIwNDkuMDcgNTMzLjc0IDIwNDcuMDUgNTMzLjczNUMyMDE2LjI2IDUzMy42NzQgMTk5Mi41IDU0MC42NjYgMTk3MC41NCA1NjMuMTQ5WiIgZmlsbD0iYmxhY2siLz4NCjxwYXRoIGQ9Ik0zMjgzIDM2My4wMDFDMzMwOS40MiAzNjIuNjAzIDMzMzUuODUgMzYyLjMwNCAzMzYyLjI4IDM2Mi4xMkMzMzc0LjU1IDM2Mi4wMzIgMzM4Ni44MiAzNjEuOTEzIDMzOTkuMDkgMzYxLjcxOEMzNDA5Ljc4IDM2MS41NDkgMzQyMC40OCAzNjEuNDM5IDM0MzEuMTggMzYxLjQwMUMzNDM2Ljg0IDM2MS4zNzkgMzQ0Mi41IDM2MS4zMjcgMzQ0OC4xNiAzNjEuMjAzQzM0NTMuNSAzNjEuMDg4IDM0NTguODMgMzYxLjA1MiAzNDY0LjE2IDM2MS4wNzhDMzQ2Ni4xMiAzNjEuMDczIDM0NjguMDcgMzYxLjA0IDM0NzAuMDIgMzYwLjk3NEMzNDgyLjA2IDM2MC41OTEgMzQ4Mi4wNiAzNjAuNTkxIDM0ODcgMzYzLjAwMUMzNDkxLjM2IDM2Ny4xMjQgMzQ5My43OSAzNzIuNDgxIDM0OTYuMSAzNzcuOTMxQzM0OTcuMzYgMzgwLjgyOCAzNDk4LjkgMzgzLjUzOSAzNTAwLjQ3IDM4Ni4yNzhDMzUwMS40OCAzODguMTYzIDM1MDIuNDkgMzkwLjA1IDM1MDMuNSAzOTEuOTM4QzM1MDQuNjEgMzk0LjAxIDM1MDUuNzMgMzk2LjA4MiAzNTA2Ljg0IDM5OC4xNTNDMzUwNy42NSAzOTkuNjQ4IDM1MDcuNjUgMzk5LjY0OCAzNTA4LjQ3IDQwMS4xNzJDMzUxMC42MSA0MDUuMTMzIDM1MTIuOCA0MDkuMDY5IDM1MTUgNDEzLjAwMUMzNTE4Ljg2IDQxOS45MDMgMzUyMi42MiA0MjYuODUyIDM1MjYuMzggNDMzLjgxM0MzNTMyLjQgNDQ0Ljk4MyAzNTM4LjY2IDQ1Ni4wMDcgMzU0NSA0NjcuMDAxQzM1NTYuMDEgNDg2LjEzIDM1NjcuMDEgNTA1LjI5IDM1NzcuMTkgNTI0Ljg3NkMzNTgwLjk4IDUzMi4xNzcgMzU4NSA1MzkuMzI4IDM1ODkuMTEgNTQ2LjQ1NEMzNTkzLjU1IDU1NC4xNjQgMzU5Ny44NSA1NjEuOTUxIDM2MDIuMTIgNTY5Ljc1MUMzNjA2Ljc1IDU3OC4xNjkgMzYxMS40MiA1ODYuNTQ0IDM2MTYuMzMgNTk0Ljc5N0MzNjE5LjkyIDYwMC44MjUgMzYyMy40MSA2MDYuOTA0IDM2MjYuODggNjEzLjAwMUMzNjI3LjQyIDYxMy45NTcgMzYyNy45NyA2MTQuOTEzIDM2MjguNTQgNjE1Ljg5OUMzNjMxLjM0IDYyMC44NDEgMzYzMy44NyA2MjUuNzggMzYzNi4xMSA2MzAuOTk5QzM2MzcuMzggNjMzLjg2NSAzNjM4LjkyIDYzNi41NDQgMzY0MC41IDYzOS4yNTFDMzY0MS4yMSA2NDAuNDczIDM2NDEuOTIgNjQxLjY5NiAzNjQyLjYyIDY0Mi45MTlDMzY0My4wMSA2NDMuNTc0IDM2NDMuMzkgNjQ0LjIyOSAzNjQzLjc4IDY0NC45MDVDMzY0Ni4wNCA2NDguNzgyIDM2NDguMjcgNjUyLjY3MiAzNjUwLjUgNjU2LjU2M0MzNjUxIDY1Ny40MzIgMzY1MS41IDY1OC4zMDEgMzY1Mi4wMSA2NTkuMTk2QzM2NTYuODIgNjY3LjYyNiAzNjYxLjQ5IDY3Ni4xMzIgMzY2Ni4xNiA2ODQuNjQxQzM2NzAuOTcgNjkzLjM5MyAzNjc1Ljg5IDcwMi4wNjQgMzY4MSA3MTAuNjQ1QzM2ODIuNzQgNzEzLjU2MiAzNjg0LjQ1IDcxNi40ODYgMzY4Ni4xMiA3MTkuNDM4QzM2ODYuNSA3MjAuMDk3IDM2ODYuODcgNzIwLjc1NiAzNjg3LjI2IDcyMS40MzRDMzY4OCA3MjMuMDAxIDM2ODggNzIzLjAwMSAzNjg4IDcyNS4wMDFDMzY4OC42NiA3MjUuMDAxIDM2ODkuMzIgNzI1LjAwMSAzNjkwIDcyNS4wMDFDMzY5MC4zOSA3MjMuOTg4IDM2OTAuMzkgNzIzLjk4OCAzNjkwLjc4IDcyMi45NTRDMzY5NC45IDcxMi45NjkgMzcwMC4xNyA3MDMuNTIgMzcwNS43MiA2OTQuMjczQzM3MTAgNjg3LjExNCAzNzEzLjk5IDY3OS44MSAzNzE4IDY3Mi41MDFDMzcyMi4zIDY2NC42NTQgMzcyNi42MSA2NTYuODE2IDM3MzEuMTkgNjQ5LjEyNkMzNzM4Ljg0IDYzNi4yNjMgMzc0Ni41MSA2MjMuMzQzIDM3NTMuMDYgNjA5Ljg3NkMzNzU3LjQxIDYwMC45MzIgMzc2Mi40MiA1OTIuMzgxIDM3NjcuNCA1ODMuNzc1QzM3NzAuMDYgNTc5LjE1NiAzNzcyLjY5IDU3NC41MTcgMzc3NS4zMSA1NjkuODc2QzM3NzUuODQgNTY4LjkzNyAzNzc2LjM3IDU2Ny45OTkgMzc3Ni45MiA1NjcuMDMyQzM3NzkuOTMgNTYxLjcwMiAzNzgyLjkyIDU1Ni4zNTkgMzc4NS44OCA1NTEuMDAxQzM3ODYuMzcgNTUwLjExIDM3ODYuMzcgNTUwLjExIDM3ODYuODcgNTQ5LjIwMkMzNzg4LjQ2IDU0Ni4zMjkgMzc5MC4wNCA1NDMuNDUzIDM3OTEuNjIgNTQwLjU3NEMzNzk0LjcgNTM1LjAwOSAzNzk3Ljg3IDUyOS41MzUgMzgwMS4yMyA1MjQuMTQxQzM4MDMuOTMgNTE5Ljc5MiAzODA2LjM4IDUxNS41MDQgMzgwOC41NiA1MTAuODc2QzM4MTUuNzMgNDk2LjEwMiAzODIzLjg4IDQ4MS42MzYgMzgzMi40NCA0NjcuNjI2QzM4MzcuNTIgNDU5LjMwMyAzODQyLjE1IDQ1MC43MzQgMzg0Ni44NCA0NDIuMTg3QzM4NTEuMTMgNDM0LjM4MSAzODU1LjQ3IDQyNi42MTMgMzg1OS44OCA0MTguODc2QzM4NjQuMTMgNDExLjQwMyAzODY4LjIxIDQwMy44NjcgMzg3Mi4xOCAzOTYuMjM3QzM4NzUuNjUgMzg5LjU4MiAzODc5LjMgMzgzLjAzNCAzODgzIDM3Ni41MDFDMzg4My41NiAzNzUuNTAyIDM4ODQuMTMgMzc0LjUwNCAzODg0LjcxIDM3My40NzVDMzg4Ni43MyAzNjkuOTE4IDM4ODguNzMgMzY2LjQwNiAzODkxIDM2My4wMDFDMzg5My43NSAzNjIuNzA2IDM4OTYuMjcgMzYyLjYxIDM4OTkuMDIgMzYyLjY0QzM4OTkuODYgMzYyLjYzNyAzOTAwLjcgMzYyLjYzNSAzOTAxLjU3IDM2Mi42MzJDMzkwNC4zOSAzNjIuNjI3IDM5MDcuMjIgMzYyLjY0NCAzOTEwLjA1IDM2Mi42NkMzOTEyLjA3IDM2Mi42NjEgMzkxNC4wOSAzNjIuNjYxIDM5MTYuMTEgMzYyLjY1OUMzOTIxLjYgMzYyLjY1OCAzOTI3LjEgMzYyLjY3NiAzOTMyLjYgMzYyLjY5N0MzOTM4LjM0IDM2Mi43MTUgMzk0NC4wOCAzNjIuNzE3IDM5NDkuODIgMzYyLjcyMUMzOTYwLjcgMzYyLjczIDM5NzEuNTcgMzYyLjc1NSAzOTgyLjQ1IDM2Mi43ODVDMzk5NC44MyAzNjIuODE4IDQwMDcuMjEgMzYyLjgzNSA0MDE5LjU5IDM2Mi44NUM0MDQ1LjA2IDM2Mi44ODEgNDA3MC41MyAzNjIuOTM0IDQwOTYgMzYzLjAwMUM0MDk1LjQxIDM2Ny41OTIgNDA5NC43NiAzNzEuMDk0IDQwOTIuNTIgMzc1LjE2MUM0MDkyIDM3Ni4xMDcgNDA5MS40OCAzNzcuMDU0IDQwOTAuOTUgMzc4LjAyOUM0MDkwLjM5IDM3OS4wMyA0MDg5LjgzIDM4MC4wMzIgNDA4OS4yNSAzODEuMDYzQzQwODguMzcgMzgyLjY1MyA0MDg4LjM3IDM4Mi42NTMgNDA4Ny40OCAzODQuMjc1QzQwODMuMTYgMzkyLjA1OSA0MDc4LjY2IDM5OS43MjYgNDA3NC4wOSA0MDcuMzYxQzQwNjkuMjEgNDE1LjU0NSA0MDY0LjYyIDQyMy44NzcgNDA2MC4wNSA0MzIuMjM2QzQwNTUuMzMgNDQwLjg0NyA0MDUwLjQ5IDQ0OS4zNjIgNDA0NS41IDQ1Ny44MTNDNDA0MS40NCA0NjQuNzAxIDQwMzcuNTggNDcxLjU5NyA0MDM0LjEgNDc4Ljc5NUM0MDI2LjQyIDQ5NC41MjggNDAxNy4yOCA1MDkuNTg0IDQwMDguNDEgNTI0LjY2N0M0MDAyLjkzIDUzNC4wMjUgMzk5Ny43IDU0My41MTMgMzk5Mi41IDU1My4wMzFDMzk4OS42NyA1NTguMjExIDM5ODYuODIgNTYzLjM1OCAzOTgzLjc1IDU2OC40MDNDMzk4MS40MSA1NzIuMjUzIDM5NzkuMzggNTc2LjEyNCAzOTc3LjQ0IDU4MC4xODhDMzk3Mi42NCA1ODkuOTg5IDM5NjcuMTggNTk5LjQwNCAzOTYxLjc3IDYwOC44NzRDMzk1OS4zMiA2MTMuMTkgMzk1Ni45MSA2MTcuNTI4IDM5NTQuNSA2MjEuODY1QzM5NDYuMDMgNjM3LjA4MyAzOTQ2LjAzIDYzNy4wODMgMzk0MS45NCA2NDMuNTYzQzM5MzQuMjUgNjU1Ljc5NyAzOTI3LjcxIDY2OC43ODEgMzkyMS4wNCA2ODEuNTlDMzkxNy4yNyA2ODguODE3IDM5MTMuMzYgNjk1Ljg5OCAzOTA5LjE3IDcwMi44OUMzOTA0Ljk2IDcwOS45NTggMzkwMS4wMiA3MTcuMTY2IDM4OTcuMDYgNzI0LjM3NkMzODkyLjUzIDczMi42MjggMzg4Ny45OSA3NDAuODY2IDM4ODMuMjUgNzQ5LjAwMUMzODgyLjgyIDc0OS43MzggMzg4Mi4zOSA3NTAuNDc2IDM4ODEuOTUgNzUxLjIzNkMzODgxLjA4IDc1Mi43MTcgMzg4MC4yMiA3NTQuMTk4IDM4NzkuMzUgNzU1LjY3OUMzODcwLjI4IDc3MS4xMjUgMzg3MC4yOCA3NzEuMTI1IDM4NjIgNzg3LjAwMUMzODU3LjYzIDc5NS45ODcgMzg1Mi42IDgwNC41NzkgMzg0Ny42IDgxMy4yMjdDMzg0NC45NCA4MTcuODQ2IDM4NDIuMzEgODIyLjQ4NSAzODM5LjY5IDgyNy4xMjZDMzgzOS4xNiA4MjguMDY2IDM4MzguNjIgODI5LjAwNSAzODM4LjA4IDgyOS45NzRDMzgzNS4wOCA4MzUuMjggMzgzMi4xMSA4NDAuNTk4IDM4MjkuMTYgODQ1LjkzQzM4MjguODQgODQ2LjUxNCAzODI4LjUxIDg0Ny4wOTggMzgyOC4xOCA4NDcuN0MzODI2LjU2IDg1MC42MyAzODI0Ljk0IDg1My41NiAzODIzLjMyIDg1Ni40OTFDMzgyMC4wMSA4NjIuNDYgMzgxNi42NCA4NjguMzcyIDM4MTMuMDYgODc0LjE4OEMzODEwLjI2IDg3OC43NjMgMzgwNy43MiA4ODMuNDI1IDM4MDUuMzggODg4LjI1MUMzNzk3LjYgOTA0LjIyNiAzNzg4LjY4IDkxOS43MzkgMzc3OS40MyA5MzQuODk5QzM3NzYuMDMgOTQwLjU1NyAzNzcyLjg4IDk0Ni4zNTMgMzc2OS42OSA5NTIuMTI2QzM3MzAuODIgMTAyMi4zNiAzNzMwLjgyIDEwMjIuMzYgMzcwNi4wOCAxMDQ4Ljc1QzM3MDAuOTEgMTA1NC4zNCAzNjk2LjIyIDEwNjAuMzcgMzY5MS42MiAxMDY2LjQ0QzM2ODQuNTggMTA3NS41MSAzNjc2LjQ0IDEwODMuNjYgMzY2OC4zOCAxMDkxLjgxQzM2NjcuNjggMTA5Mi41MiAzNjY2Ljk5IDEwOTMuMjIgMzY2Ni4yOCAxMDkzLjk1QzM2NjEuNDggMTA5OC43NSAzNjU2LjQyIDExMDIuOTMgMzY1MSAxMTA3QzM2NDkuNjMgMTEwOC4wNiAzNjQ4LjI2IDExMDkuMTIgMzY0Ni44OSAxMTEwLjE4QzM2NDMuMzEgMTExMi45NCAzNjM5LjcgMTExNS42OCAzNjM2LjA5IDExMTguNDJDMzYzNC43OSAxMTE5LjQgMzYzMy41IDExMjAuMzggMzYzMi4yMSAxMTIxLjM3QzM1OTcuMDIgMTE0OC4zNyAzNTQ4LjcyIDExNjYuMjYgMzUwNC4yNCAxMTY2LjExQzM1MDMuMDggMTE2Ni4xMSAzNTAxLjkyIDExNjYuMTEgMzUwMC43MiAxMTY2LjExQzM0OTYuOTkgMTE2Ni4xMSAzNDkzLjI2IDExNjYuMTEgMzQ4OS41MyAxMTY2LjFDMzQ4Ny4yMSAxMTY2LjEgMzQ4NC45IDExNjYuMSAzNDgyLjU5IDExNjYuMUMzNDc0LjA0IDExNjYuMDkgMzQ2NS40OSAxMTY2LjA4IDM0NTYuOTQgMTE2Ni4wNkMzNDI4LjI2IDExNjYuMDMgMzQyOC4yNiAxMTY2LjAzIDMzOTkgMTE2NkMzMzk5IDExMTEuMjIgMzM5OSAxMDU2LjQ0IDMzOTkgMTAwMEMzNDE5LjEzIDk5OS42NzEgMzQzOS4yNiA5OTkuMzQxIDM0NjAgOTk5LjAwMUMzNDcxLjE0IDk5Ny43NjMgMzQ4MS40IDk5Ni42MTQgMzQ5Mi4xMiA5OTMuODc2QzM0OTMuMzMgOTkzLjU3IDM0OTQuNTMgOTkzLjI2NCAzNDk1Ljc3IDk5Mi45NDlDMzUwNS4yNyA5OTAuNDE5IDM1MTMuNjMgOTg3LjExNiAzNTIyIDk4Mi4wMDFDMzUyMi42IDk4MS42NDIgMzUyMy4yMSA5ODEuMjg0IDM1MjMuODMgOTgwLjkxNEMzNTMyLjEyIDk3NS45NjggMzUzOS43IDk3MC4zMjIgMzU0NyA5NjQuMDAxQzM1NDcuOCA5NjMuMzIgMzU0OC42MSA5NjIuNjM5IDM1NDkuNDMgOTYxLjkzOEMzNTU2Ljc4IDk1NS41OTMgMzU2Mi43NCA5NDguMzk4IDM1NjguNzUgOTQwLjgxM0MzNTY5LjIyIDk0MC4yMTkgMzU2OS42OSA5MzkuNjI0IDM1NzAuMTggOTM5LjAxMkMzNTcyLjcxIDkzNS43ODcgMzU3NC45NiA5MzIuNTY1IDM1NzcgOTI5LjAwMUMzNTc4LjAzIDkyNy4zMyAzNTc4LjAzIDkyNy4zMyAzNTc5LjA4IDkyNS42MjZDMzU3OS44IDkyNC40MTggMzU4MC41MyA5MjMuMjEgMzU4MS4yNSA5MjIuMDAxQzM1ODEuNjMgOTIxLjM5NyAzNTgyIDkyMC43OTQgMzU4Mi4zOSA5MjAuMTczQzM1ODMuOTQgOTE3LjU0NiAzNTg1LjAxIDkxNS41OTYgMzU4NC45NSA5MTIuNTA1QzM1ODMuNyA5MDkuMjA4IDM1ODIuMjMgOTA2LjA2OSAzNTgwLjYyIDkwMi45MzhDMzU4MC4yNyA5MDIuMjQ2IDM1NzkuOTIgOTAxLjU1MyAzNTc5LjU2IDkwMC44MzlDMzU3Mi43MSA4ODcuNDU5IDM1NjUuMjYgODc0LjM5NyAzNTU3Ljc3IDg2MS4zNjVDMzU1My41MyA4NTMuOTY4IDM1NDkuMzggODQ2LjUyMiAzNTQ1LjI1IDgzOS4wNjNDMzUzOS45MSA4MjkuNDE3IDM1MzQuNDkgODE5LjgxNyAzNTI5IDgxMC4yNTdDMzUyNC4xNyA4MDEuODM1IDM1MTkuNTggNzkzLjMxNSAzNTE1LjEyIDc4NC42ODhDMzUxMC4xNSA3NzUuMDczIDM1MDQuODcgNzY1LjY5MSAzNDk5LjM4IDc1Ni4zNjJDMzQ5MS4yOCA3NDIuNTM0IDM0ODMuNDkgNzI4LjUzIDM0NzUuNzggNzE0LjQ3NkMzNDcxLjg0IDcwNy4zMDQgMzQ2Ny44NCA3MDAuMTgzIDM0NjMuNzQgNjkzLjFDMzQ2Mi4xNiA2OTAuMjkyIDM0NjAuNzEgNjg3LjQ2MyAzNDU5LjMxIDY4NC41NjNDMzQ1NC44MiA2NzUuMzkzIDM0NDkuNjEgNjY2LjU5OSAzNDQ0LjU1IDY1Ny43M0MzNDQyLjUgNjU0LjEyIDM0NDAuNDcgNjUwLjQ5OSAzNDM4LjQ0IDY0Ni44NzZDMzQzNS42MSA2NDEuODMgMzQzMi43NCA2MzYuODAzIDM0MjkuODYgNjMxLjc4NUMzNDIwLjQ3IDYxNS40MSAzNDExLjEyIDU5OC45ODIgMzQwMi4zOCA1ODIuMjUxQzMzOTguNDkgNTc0LjgxNSAzMzk0LjM3IDU2Ny41MTcgMzM5MC4yMiA1NjAuMjI0QzMzODYuMiA1NTMuMTM0IDMzODIuMjMgNTQ2LjAxMyAzMzc4LjI4IDUzOC44NzZDMzM3My45MSA1MzAuOTY0IDMzNjkuNTEgNTIzLjA3NCAzMzY0Ljg4IDUxNS4zMTNDMzM1Ny4xMSA1MDIuMjk3IDMzNDkuODQgNDg4LjkzIDMzNDMuMTkgNDc1LjMxM0MzMzQxLjA5IDQ3MS4wMzkgMzMzOC44MiA0NjYuOTk4IDMzMzYuMjggNDYyLjk3M0MzMzMyLjQgNDU2Ljc0OCAzMzI4LjgxIDQ1MC4zODUgMzMyNS4zIDQ0My45NDJDMzMyMy41NyA0NDAuNzcyIDMzMjEuODQgNDM3LjYxIDMzMjAuMSA0MzQuNDQ2QzMzMTkuNzUgNDMzLjgxMiAzMzE5LjQgNDMzLjE3OSAzMzE5LjA0IDQzMi41MjZDMzMxNS44MiA0MjYuNjYxIDMzMTIuNTUgNDIwLjgyNSAzMzA5LjI1IDQxNS4wMDFDMzMwOC43MyA0MTQuMDc2IDMzMDguMiA0MTMuMTUxIDMzMDcuNjYgNDEyLjE5OEMzMzA1LjA2IDQwNy42MTIgMzMwMi40NSA0MDMuMDM3IDMyOTkuODEgMzk4LjQ3M0MzMjk1LjEzIDM5MC4zNzYgMzI5MC40OSAzODIuMjc0IDMyODYuMjUgMzczLjkzOEMzMjg1LjkxIDM3My4yODkgMzI4NS41OCAzNzIuNjQgMzI4NS4yMyAzNzEuOTcyQzMyODMuNTcgMzY4LjYzNiAzMjgzIDM2Ni44MjIgMzI4MyAzNjMuMDAxWiIgZmlsbD0iYmxhY2siLz4NCjxwYXRoIGQ9Ik0yMzcuOTE5IDM2Mi44NzhDMjM5Ljg5NyAzNjIuODc5IDIzOS44OTcgMzYyLjg3OSAyNDEuOTE2IDM2Mi44OEMyNDMuMDE0IDM2Mi44NzkgMjQzLjAxNCAzNjIuODc5IDI0NC4xMzQgMzYyLjg3OEMyNDYuNjA0IDM2Mi44NzYgMjQ5LjA3NSAzNjIuODgyIDI1MS41NDUgMzYyLjg4N0MyNTMuMzA5IDM2Mi44ODcgMjU1LjA3MyAzNjIuODg3IDI1Ni44MzYgMzYyLjg4N0MyNjEuNjQgMzYyLjg4NiAyNjYuNDQzIDM2Mi44OTIgMjcxLjI0NyAzNjIuODk5QzI3Ni4yNjEgMzYyLjkwNSAyODEuMjc1IDM2Mi45MDYgMjg2LjI4OSAzNjIuOTA3QzI5NS43OTIgMzYyLjkxIDMwNS4yOTQgMzYyLjkxOSAzMTQuNzk2IDM2Mi45MjlDMzI1LjYxIDM2Mi45NCAzMzYuNDI1IDM2Mi45NDUgMzQ3LjI0IDM2Mi45NUMzNjkuNDkzIDM2Mi45NjEgMzkxLjc0NyAzNjIuOTc5IDQxNCAzNjMuMDAxQzQxNCAzNzAuOTIxIDQxNCAzNzguODQxIDQxNCAzODcuMDAxQzQxNi42MiAzODUuOTkgNDE5LjIzOSAzODQuOTc5IDQyMS45MzggMzgzLjkzOEM0NzEuODA4IDM2NS4zMzMgNTI0LjA1NCAzNjIuNjU2IDU3Ni42OTMgMzYyLjczMkM1ODEuNDI4IDM2Mi43MzcgNTg2LjE2MiAzNjIuNzMyIDU5MC44OTcgMzYyLjcyOUM1OTguODMxIDM2Mi43MjYgNjA2Ljc2NSAzNjIuNzMgNjE0LjY5OSAzNjIuNzRDNjIzLjc5MSAzNjIuNzUxIDYzMi44ODMgMzYyLjc0NyA2NDEuOTc2IDM2Mi43MzZDNjQ5Ljg3NyAzNjIuNzI3IDY1Ny43NzkgMzYyLjcyNiA2NjUuNjggMzYyLjczMUM2NzAuMzU4IDM2Mi43MzQgNjc1LjAzNiAzNjIuNzM1IDY3OS43MTQgMzYyLjcyOEM3MzIuMzI2IDM2Mi42NjMgNzMyLjMyNiAzNjIuNjYzIDc1NSAzNjcuMzEzQzc1Ni4xMTIgMzY3LjUzMSA3NTcuMjI0IDM2Ny43NDkgNzU4LjM3IDM2Ny45NzRDNzY4LjAzMiAzNjkuOTEzIDc3Ny41NjQgMzcyLjE1NSA3ODcgMzc1LjAwMUM3ODcuNzQxIDM3NS4yMTggNzg4LjQ4MiAzNzUuNDM2IDc4OS4yNDUgMzc1LjY2MUM4MTMuMTQ0IDM4Mi44NDIgODM2LjUxNiAzOTQuODMxIDg1NyA0MDkuMDAxQzg1OC4wMjIgNDA5LjY5MyA4NTkuMDQ1IDQxMC4zODUgODYwLjA5OCA0MTEuMDk4Qzg3OC40OTggNDIzLjk5MiA4OTUuNTA4IDQ0MC4yMTIgOTA4Ljc3NCA0NTguMzM4QzkwOS45NzkgNDU5Ljk3MiA5MTEuMjE5IDQ2MS41NzMgOTEyLjQ2OSA0NjMuMTcyQzkzMS4zNDQgNDg3LjgyNCA5NDMuNTM0IDUxOS4yNjkgOTQ5Ljc1IDU0OS41MDFDOTUwLjA0OCA1NTAuOTQgOTUwLjA0OCA1NTAuOTQgOTUwLjM1MyA1NTIuNDA4Qzk1NC40MDUgNTczLjMwNyA5NTQuMjgyIDU5NC4xNDQgOTU0LjIzMiA2MTUuMzMyQzk1NC4yMjQgNjE5Ljk4MiA5NTQuMjI3IDYyNC42MzEgOTU0LjIyOCA2MjkuMjhDOTU0LjIyOSA2MzcuMzE1IDk1NC4yMjMgNjQ1LjM0OSA5NTQuMjEyIDY1My4zODRDOTU0LjE5NSA2NjUgOTU0LjE5IDY3Ni42MTcgOTU0LjE4OCA2ODguMjMzQzk1NC4xODMgNzA3LjA4NCA5NTQuMTcgNzI1LjkzNiA5NTQuMTUxIDc0NC43ODdDOTU0LjEzMyA3NjMuMDg5IDk1NC4xMTggNzgxLjM5IDk1NC4xMSA3OTkuNjkxQzk1NC4xMDkgODAwLjgzMiA5NTQuMTA5IDgwMS45NzQgOTU0LjEwOCA4MDMuMTVDOTU0LjEwNCA4MTIuMDc5IDk1NC4xIDgyMS4wMDggOTU0LjA5NiA4MjkuOTM3Qzk1NC4wNzggODczLjYyNSA5NTQuMDM3IDkxNy4zMTMgOTU0IDk2MS4wMDFDODk0LjkzIDk2MS4wMDEgODM1Ljg2IDk2MS4wMDEgNzc1IDk2MS4wMDFDNzc0Ljk2MyA5MzUuMjU5IDc3NC45MjUgOTA5LjUxOCA3NzQuODg3IDg4Mi45OTdDNzc0Ljg1NyA4NjYuNzA0IDc3NC44MjYgODUwLjQxMiA3NzQuNzkxIDgzNC4xMkM3NzQuNzczIDgyNS41NjEgNzc0Ljc1NSA4MTcuMDAyIDc3NC43MzggODA4LjQ0M0M3NzQuNzM1IDgwNy4zNzEgNzc0LjczMyA4MDYuMjk4IDc3NC43MzEgODA1LjE5M0M3NzQuNjk2IDc4Ny44OTIgNzc0LjY3MSA3NzAuNTkxIDc3NC42NSA3NTMuMjlDNzc0LjYyOCA3MzUuNTI1IDc3NC41OTUgNzE3Ljc2IDc3NC41NTEgNjk5Ljk5NUM3NzQuNTI1IDY4OS4wMzkgNzc0LjUwNyA2NzguMDg0IDc3NC41MDEgNjY3LjEyOEM3NzQuNDk2IDY1OS42MDggNzc0LjQ3OSA2NTIuMDg4IDc3NC40NTQgNjQ0LjU2OEM3NzQuNDQxIDY0MC4yMzQgNzc0LjQzMSA2MzUuOSA3NzQuNDM1IDYzMS41NjZDNzc0LjQzOSA2MjcuNTg5IDc3NC40MjggNjIzLjYxMiA3NzQuNDA3IDYxOS42MzRDNzc0LjQwMiA2MTguMjA1IDc3NC40MDEgNjE2Ljc3NSA3NzQuNDA3IDYxNS4zNDZDNzc0LjQ4NyA1OTEuNzQ1IDc2Ny4zNTggNTcxLjgxMyA3NTAuODE3IDU1NC43MjdDNzM1Ljg2MyA1NDAuMjUxIDcxNi4xMDQgNTM0LjgyOSA2OTUuNzQyIDUzNC44NjdDNjk0Ljg0MyA1MzQuODY1IDY5My45NDMgNTM0Ljg2MiA2OTMuMDE3IDUzNC44NkM2OTAuMDIgNTM0Ljg1NCA2ODcuMDI0IDUzNC44NTQgNjg0LjAyNyA1MzQuODU1QzY4MS44NzEgNTM0Ljg1MiA2NzkuNzE1IDUzNC44NDkgNjc3LjU2IDUzNC44NDVDNjcxLjcxNCA1MzQuODM2IDY2NS44NjkgNTM0LjgzNCA2NjAuMDI0IDUzNC44MzNDNjU2LjM2NyA1MzQuODMzIDY1Mi43MTEgNTM0LjgzIDY0OS4wNTQgNTM0LjgyOEM2MzYuMjg0IDUzNC44MTkgNjIzLjUxNCA1MzQuODE0IDYxMC43NDQgNTM0LjgxNUM1OTguODYzIDUzNC44MTYgNTg2Ljk4MiA1MzQuODA1IDU3NS4xMDEgNTM0Ljc5QzU2NC44ODQgNTM0Ljc3NiA1NTQuNjY2IDUzNC43NzEgNTQ0LjQ0OCA1MzQuNzcyQzUzOC4zNTQgNTM0Ljc3MiA1MzIuMjU5IDUzNC43NjkgNTI2LjE2NCA1MzQuNzU5QzUyMC40MjcgNTM0Ljc0OSA1MTQuNjg5IDUzNC43NDkgNTA4Ljk1MiA1MzQuNzU2QzUwNi44NTUgNTM0Ljc1NyA1MDQuNzU4IDUzNC43NTUgNTAyLjY2MSA1MzQuNzQ5QzQ3Ny45MjQgNTM0LjY4MiA0NTUuNzczIDUzNy44NyA0MzcuMjMxIDU1NS43NDdDNDM2LjQ5NSA1NTYuNDkgNDM1Ljc1OCA1NTcuMjM0IDQzNSA1NTguMDAxQzQzNC4zMTYgNTU4LjY1MiA0MzMuNjMxIDU1OS4zMDMgNDMyLjkyNiA1NTkuOTczQzQxNi44MyA1NzYuMzg2IDQxMy44NTYgNTk3LjYxOCA0MTMuODQyIDYxOS41OThDNDEzLjgzNyA2MjEuMDc0IDQxMy44MzIgNjIyLjU1IDQxMy44MjcgNjI0LjAyN0M0MTMuODEzIDYyOC4wNjUgNDEzLjgwNiA2MzIuMTA0IDQxMy44IDYzNi4xNDJDNDEzLjc5MSA2NDAuNTA0IDQxMy43NzggNjQ0Ljg2NiA0MTMuNzY1IDY0OS4yMjhDNDEzLjc0MyA2NTYuNzc5IDQxMy43MjUgNjY0LjMzMSA0MTMuNzA5IDY3MS44ODJDNDEzLjY4NiA2ODIuOCA0MTMuNjU4IDY5My43MTggNDEzLjYyOSA3MDQuNjM1QzQxMy41ODEgNzIyLjM1IDQxMy41MzggNzQwLjA2NSA0MTMuNDk3IDc1Ny43NzlDNDEzLjQ1OCA3NzQuOTg1IDQxMy40MTcgNzkyLjE5IDQxMy4zNzIgODA5LjM5NUM0MTMuMzcgODEwLjQ2NyA0MTMuMzY3IDgxMS41MzkgNDEzLjM2NCA4MTIuNjQzQzQxMy4zNDMgODIxLjAyNiA0MTMuMzIxIDgyOS40MDkgNDEzLjI5OSA4MzcuNzkxQzQxMy4xOTMgODc4Ljg2MSA0MTMuMDk3IDkxOS45MzEgNDEzIDk2MS4wMDFDMzUzLjkzIDk2MS4wMDEgMjk0Ljg2IDk2MS4wMDEgMjM0IDk2MS4wMDFDMjMzLjk4IDg5MS41MDEgMjMzLjk4IDg5MS41MDEgMjMzLjk3NCA4NzAuMDA0QzIzMy45NzQgODY5LjIzNyAyMzMuOTc0IDg2OC40NzEgMjMzLjk3NCA4NjcuNjgxQzIzMy45NjcgODQxLjg4NSAyMzMuOTYyIDgxNi4wOSAyMzMuOTU4IDc5MC4yOTVDMjMzLjk1OCA3ODkuNDUzIDIzMy45NTggNzg4LjYxMiAyMzMuOTU3IDc4Ny43NDVDMjMzLjk1NCA3NjkuNDU5IDIzMy45NTIgNzUxLjE3NCAyMzMuOTQ5IDczMi44ODlDMjMzLjk0OCA3MjMuOTIyIDIzMy45NDcgNzE0Ljk1NiAyMzMuOTQ1IDcwNS45OUMyMzMuOTQ1IDcwNS4wOTcgMjMzLjk0NSA3MDQuMjA1IDIzMy45NDUgNzAzLjI4NkMyMzMuOTQxIDY3NC4zMzcgMjMzLjkzMyA2NDUuMzg5IDIzMy45MjQgNjE2LjQ0QzIzMy45MTQgNTg2LjcwNCAyMzMuOTA4IDU1Ni45NjkgMjMzLjkwNiA1MjcuMjMzQzIzMy45MDYgNTIzLjAzOCAyMzMuOTA2IDUxOC44NDMgMjMzLjkwNSA1MTQuNjQ4QzIzMy45MDUgNTEzLjgyMiAyMzMuOTA1IDUxMi45OTcgMjMzLjkwNSA1MTIuMTQ2QzIzMy45MDQgNDk4LjgyNyAyMzMuODk5IDQ4NS41MDkgMjMzLjg5MyA0NzIuMTlDMjMzLjg4NyA0NTguODE3IDIzMy44ODUgNDQ1LjQ0NCAyMzMuODg3IDQzMi4wNzFDMjMzLjg4NyA0MjQuMTE1IDIzMy44ODUgNDE2LjE1OSAyMzMuODc5IDQwOC4yMDNDMjMzLjg3NSA0MDIuMjc4IDIzMy44NzYgMzk2LjM1NCAyMzMuODc5IDM5MC40M0MyMzMuODggMzg4LjAyMSAyMzMuODc4IDM4NS42MTIgMjMzLjg3NSAzODMuMjAyQzIzMy44NzEgMzc5Ljk1MSAyMzMuODczIDM3Ni42OTkgMjMzLjg3NyAzNzMuNDQ3QzIzMy44NzQgMzcyLjQ5MiAyMzMuODcyIDM3MS41MzcgMjMzLjg2OSAzNzAuNTUzQzIzMy44ODkgMzYzLjA0NyAyMzMuODg5IDM2My4wNDcgMjM3LjkxOSAzNjIuODc4WiIgZmlsbD0iYmxhY2siLz4NCjxwYXRoIGQ9Ik0wIDBDNTguNzQgMCAxMTcuNDggMCAxNzggMEMxNzggMzE3LjEzIDE3OCA2MzQuMjYgMTc4IDk2MUMxMTkuMjYgOTYxIDYwLjUyIDk2MSAwIDk2MUMwIDY0My44NyAwIDMyNi43NCAwIDBaIiBmaWxsPSJibGFjayIvPg0KPC9nPg0KPGRlZnM+DQo8Y2xpcFBhdGggaWQ9ImNsaXAwXzI0NjZfOTQiPg0KPHJlY3Qgd2lkdGg9IjQwOTYiIGhlaWdodD0iMTE2NiIgZmlsbD0id2hpdGUiLz4NCjwvY2xpcFBhdGg+DQo8L2RlZnM+DQo8L3N2Zz4NCg=="
BODY_IMG     = "data:image/png;base64,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"

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{{ athlete_name }} — S&C Report</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Barlow+Condensed:wght@300;400;600;700;900&display=swap"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#04101E;--panel:#071828;--border:rgba(255,255,255,0.07);
  --dari:#38A3A5;--vald:#FF7A00;--arm:#EF4444;--inbody:#2563EB;--muted:#5A7A9A;}
html,body{background:var(--bg);color:#E8F0F8;font-family:'Barlow Condensed',sans-serif;}
.hdr{background:linear-gradient(135deg,#04101E,#071828);border-bottom:3px solid #E8621A;
  padding:0 24px;height:56px;display:flex;align-items:center;justify-content:space-between;}
.hdr-logo{height:40px;width:auto;border-radius:50%;}
.hdr-name{font-family:'Bebas Neue',sans-serif;font-size:28px;letter-spacing:4px;color:#fff;}
.hdr-sub{font-size:10px;color:#E8621A;letter-spacing:3px;text-transform:uppercase;text-align:center;margin-top:2px;}
.hdr-date{font-size:11px;color:var(--muted);letter-spacing:1.5px;text-align:right;}
@media print{.page-break{page-break-before:always;}}
.p1-grid{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;
  gap:8px;padding:8px;height:calc(100vh - 58px);min-height:680px;}
.card{background:var(--panel);border-radius:10px;overflow:hidden;display:flex;flex-direction:column;border:1px solid var(--border);}
.card-hdr{display:flex;align-items:center;padding:0 14px;height:48px;border-bottom:2px solid;flex-shrink:0;}
.card-hdr.dari  {border-color:var(--dari);background:rgba(56,163,165,0.15);}
.card-hdr.vald  {border-color:var(--vald);background:rgba(255,122,0,0.15);}
.card-hdr.arm   {border-color:var(--arm);background:rgba(239,68,68,0.15);}
.card-hdr.inbody{border-color:var(--inbody);background:rgba(37,99,235,0.15);}
.card-body{flex:1;padding:10px 14px;display:flex;flex-direction:column;gap:6px;overflow:hidden;}
.num-card{background:rgba(255,255,255,0.04);border:1px solid var(--border);border-radius:8px;
  padding:8px 6px 6px;text-align:center;display:flex;flex-direction:column;align-items:center;}
.nv{font-family:'Bebas Neue',sans-serif;font-size:44px;line-height:1;}
.nv.lg{font-size:52px;} .nv.sm{font-size:28px;}
.nu{font-size:11px;color:var(--muted);font-family:'Barlow Condensed';font-weight:400;}
.nl{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:2px;}
.dari .nv{color:var(--dari);} .vald .nv{color:var(--vald);} .arm .nv{color:var(--arm);} .inbody .nv{color:var(--inbody);}
.dari-layout{display:flex;gap:8px;flex:1;overflow:hidden;min-height:0;}
.dari-scores{flex:1;display:flex;flex-direction:column;gap:4px;justify-content:center;}
.sr{display:flex;align-items:center;gap:7px;}
.sn{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:0.8px;width:76px;flex-shrink:0;}
.sb{flex:1;background:rgba(255,255,255,0.06);border-radius:4px;height:5px;overflow:hidden;}
.sbf{height:100%;border-radius:4px;}
.sv{font-family:'Bebas Neue',sans-serif;font-size:20px;width:44px;text-align:right;}
.div{height:1px;background:var(--border);margin:2px 0;flex-shrink:0;}
.lbl{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:1px;flex-shrink:0;}
.p2-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:8px;}
.p2-card{background:var(--panel);border-radius:10px;border:1px solid var(--border);overflow:hidden;}
.p2-hdr{padding:0 14px;height:42px;display:flex;align-items:center;gap:8px;
  border-bottom:1px solid var(--border);font-family:'Bebas Neue',sans-serif;font-size:15px;letter-spacing:2px;color:#fff;}
.p2-body{padding:10px 14px;} .p2-body img{width:100%;height:auto;}
.cl{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin:5px 0 3px;}
.flag-panel{background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.25);border-radius:8px;margin:8px;overflow:hidden;}
.flag-hdr{background:rgba(239,68,68,0.65);padding:6px 14px;font-family:'Bebas Neue',sans-serif;font-size:15px;letter-spacing:2px;color:#fff;}
.flag-ok{padding:10px 14px;font-size:12px;color:#22c55e;}
.flag-item{padding:6px 14px;font-size:11px;color:#EF4444;}
.flag-item.improve{color:#22c55e;}
@media (max-width:768px){
  .p1-grid{grid-template-columns:1fr;grid-template-rows:auto;height:auto;min-height:unset;}
  .p2-grid{grid-template-columns:1fr !important;}
  .hdr-name{font-size:20px;letter-spacing:2px;}
  .hdr{height:auto;padding:10px 14px;flex-wrap:wrap;gap:4px;}
  .card{height:auto;overflow:visible;}
  .card-body{overflow:visible;}
  .dari-layout{flex-direction:column;overflow:visible;flex:none;}
  .dari-scan-wrap{height:280px!important;width:100%;flex-shrink:0;}
  .dari-scores{width:100%;padding-top:8px;flex:none;}
  .body-dot{width:19.5px!important;height:19.5px!important;min-width:19.5px!important;min-height:19.5px!important;max-width:19.5px!important;max-height:19.5px!important;}
  .body-dot span:first-child{font-size:8px!important;}
  .body-dot span:last-child{font-size:4px!important;}
}
</style>
</head>
<body>

<div class="hdr">
  <img class="hdr-logo" src="{{ pwrx_logo }}"/>
  <div style="text-align:center;">
    <div class="hdr-name">{{ athlete_name }}</div>
    <div class="hdr-sub">Strength &amp; Conditioning Performance Report</div>
  </div>
  <div class="hdr-date">REPORT DATE<br/>{{ report_date }}</div>
</div>

<div class="p1-grid">

  <!-- DARI -->
  <div class="card dari">
    <div class="card-hdr dari"><img src="{{ dari_logo }}" style="height:38px;width:auto;"/></div>
    <div class="card-body">
      <div class="dari-layout">
        <div class="dari-scan-wrap" style="position:relative;flex-shrink:0;display:flex;align-items:center;justify-content:center;height:100%;">
          <div style="position:relative;height:100%;max-height:280px;aspect-ratio:500/1214;">
            <img src="{{ body_img }}" style="position:absolute;top:0;left:0;width:100%;height:100%;object-fit:fill;mix-blend-mode:screen;filter:sepia(1) hue-rotate(150deg) saturate(2) brightness(0.9);"/>
            {{ body_scan_dots }}
            <div style="position:absolute;bottom:0;left:50%;transform:translateX(-50%);display:flex;gap:5px;z-index:3;white-space:nowrap;padding:2px 5px;background:rgba(4,16,30,0.75);border-radius:5px;">
              <span style="display:flex;align-items:center;gap:2px;font-size:6.5px;color:#6B8DAD;font-family:'Barlow Condensed',sans-serif;"><span style="width:6px;height:6px;border-radius:50%;background:#3B82F6;display:inline-block;"></span>0-20%</span>
              <span style="display:flex;align-items:center;gap:2px;font-size:6.5px;color:#6B8DAD;font-family:'Barlow Condensed',sans-serif;"><span style="width:6px;height:6px;border-radius:50%;background:#22c55e;display:inline-block;"></span>20-40%</span>
              <span style="display:flex;align-items:center;gap:2px;font-size:6.5px;color:#6B8DAD;font-family:'Barlow Condensed',sans-serif;"><span style="width:6px;height:6px;border-radius:50%;background:#F59E0B;display:inline-block;"></span>40-60%</span>
              <span style="display:flex;align-items:center;gap:2px;font-size:6.5px;color:#6B8DAD;font-family:'Barlow Condensed',sans-serif;"><span style="width:6px;height:6px;border-radius:50%;background:#EF4444;display:inline-block;"></span>60%+</span>
            </div>
          </div>
        </div>
        <div class="dari-scores">
          <div class="lbl">Athleticism Scores</div>
          <div class="sr"><div class="sn">Overall Score</div><div class="sb"><div class="sbf" style="width:{{ dari.current.overall }}%;background:var(--dari);"></div></div><div class="sv" style="color:var(--dari);">{{ dari.current.overall }}</div>{% if dari_prev.overall is defined %}{{ chip(dari.current.overall, dari_prev.overall)|safe }}{% endif %}</div>
          <div class="sr"><div class="sn">Functionality</div><div class="sb"><div class="sbf" style="width:{{ dari.current.functionality }}%;background:var(--dari);"></div></div><div class="sv" style="color:var(--dari);">{{ dari.current.functionality }}</div>{% if dari_prev.functionality is defined %}{{ chip(dari.current.functionality, dari_prev.functionality)|safe }}{% endif %}</div>
          <div class="sr"><div class="sn">Explosiveness</div><div class="sb"><div class="sbf" style="width:{{ dari.current.explosiveness }}%;background:var(--dari);"></div></div><div class="sv" style="color:var(--dari);">{{ dari.current.explosiveness }}</div>{% if dari_prev.explosiveness is defined %}{{ chip(dari.current.explosiveness, dari_prev.explosiveness)|safe }}{% endif %}</div>
          <div class="sr"><div class="sn">Vulnerability</div><div class="sb"><div class="sbf" style="width:{{ dari.current.athleticism }}%;background:var(--dari);"></div></div><div class="sv" style="color:var(--dari);">{{ dari.current.athleticism }}</div>{% if dari_prev.athleticism is defined %}{{ chip(dari.current.athleticism, dari_prev.athleticism)|safe }}{% endif %}</div>
          <div class="sr"><div class="sn">Dysfunction</div><div class="sb"><div class="sbf" style="width:{{ dari.current.dysfunction * 10 }}%;background:#ef4444;"></div></div><div class="sv" style="color:#ef4444;">{{ dari.current.dysfunction }}</div>{% if dari_prev.dysfunction is defined %}{{ chip(dari.current.dysfunction, dari_prev.dysfunction, invert=True)|safe }}{% endif %}</div>

        </div>
      </div>
    </div>
  </div>

  <!-- VALD -->
  <div class="card vald">
    <div class="card-hdr vald"><img src="{{ vald_logo }}" style="height:20px;width:auto;"/></div>
    <div class="card-body">
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;">
        <div class="num-card vald"><div class="nv lg">{{ vald.current.jump_height }}</div><div class="nl">Jump Height (in)</div>{% if vald.prev %}{{ chip(vald.current.jump_height, vald.prev.jump_height)|safe }}{% endif %}</div>
        <div class="num-card vald"><div class="nv lg">{{ vald.current.rsi_mod }}</div><div class="nl">RSI-Modified</div>{% if vald.prev %}{{ chip(vald.current.rsi_mod, vald.prev.rsi_mod)|safe }}{% endif %}</div>
        <div class="num-card vald"><div class="nv lg">{{ "{:,.0f}".format(vald.current.peak_power) }}</div><div class="nl">Peak Power (W)</div>{% if vald.prev %}{{ chip(vald.current.peak_power, vald.prev.peak_power)|safe }}{% endif %}</div>
      </div>
      <div class="div"></div>
      <div class="lbl">Relative Performance</div>
      <div class="sr"><div class="sn">Jump Height</div><div class="sb"><div class="sbf" style="width:{{ [vald.current.jump_height / 40 * 100, 100] | min }}%;background:var(--vald);"></div></div><div class="sv" style="color:var(--vald);">{{ vald.current.jump_height }}</div></div>
      <div class="sr"><div class="sn">RSI-Mod</div><div class="sb"><div class="sbf" style="width:{{ [vald.current.rsi_mod / 1.5 * 100, 100] | min }}%;background:var(--vald);"></div></div><div class="sv" style="color:var(--vald);">{{ vald.current.rsi_mod }}</div></div>
      <div class="sr"><div class="sn">Peak Power</div><div class="sb"><div class="sbf" style="width:{{ [vald.current.peak_power / 7000 * 100, 100] | min }}%;background:var(--vald);"></div></div><div class="sv" style="color:var(--vald);">{{ "{:.1f}".format(vald.current.peak_power / 1000) }}k</div></div>
    </div>
  </div>

  <!-- ARMCARE -->
  <div class="card arm">
    <div class="card-hdr arm"><img src="{{ armcare_logo }}" style="height:26px;width:auto;border-radius:3px;"/></div>
    <div class="card-body">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
        <div class="num-card arm"><div class="nv lg">{{ arm.current.arm_score }}</div><div class="nl">Arm Score</div>{% if arm.prev %}{{ chip(arm.current.arm_score, arm.prev.arm_score)|safe }}{% endif %}</div>
        <div class="num-card arm"><div class="nv lg">{{ arm.current.total_strength }}<span class="nu"> lbs</span></div><div class="nl">Total Strength</div>{% if arm.prev %}{{ chip(arm.current.total_strength, arm.prev.total_strength)|safe }}{% endif %}</div>
      </div>
      <div class="div"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
        <div class="num-card arm"><div class="nv lg">{{ arm.current.balance }}</div><div class="nl">Balance</div>{% if arm.prev %}{{ chip(arm.current.balance, arm.prev.balance)|safe }}{% endif %}</div>
        <div class="num-card arm"><div class="nv lg">{{ arm.current.svr }}</div><div class="nl">SVR</div>{% if arm.prev %}{{ chip(arm.current.svr, arm.prev.svr)|safe }}{% endif %}</div>
      </div>
    </div>
  </div>

  <!-- INBODY -->
  <div class="card inbody">
    <div class="card-hdr inbody"><img src="{{ inbody_logo }}" style="height:22px;width:auto;filter:brightness(0) invert(1);"/></div>
    <div class="card-body">
      {% if inbody.available %}
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
        <div class="num-card inbody"><div class="nv lg">{{ inbody.score }}<span class="nu">/100</span></div><div class="nl">InBody Score</div>{% if inbody_prev.score is defined %}{{ chip(inbody.score, inbody_prev.score)|safe }}{% endif %}</div>
        <div class="num-card inbody"><div class="nv lg">{{ inbody.weight_lbs }}<span class="nu"> lbs</span></div><div class="nl">Body Weight</div>{% if inbody_prev.weight is defined %}{{ chip(inbody.weight_lbs, inbody_prev.weight)|safe }}{% endif %}</div>
      </div>
      <div class="div"></div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;">
        <div class="num-card inbody"><div class="nv sm">{{ inbody.smm_lbs }}</div><div class="nl">SMM (lbs)</div>{% if inbody_prev.smm is defined %}{{ chip(inbody.smm_lbs, inbody_prev.smm)|safe }}{% endif %}</div>
        <div class="num-card inbody"><div class="nv sm">{{ inbody.pbf }}%</div><div class="nl">Body Fat</div>{% if inbody_prev.pbf is defined %}{{ chip(inbody.pbf, inbody_prev.pbf, invert=True)|safe }}{% endif %}</div>
        <div class="num-card inbody"><div class="nv sm">{{ inbody.bmr }}</div><div class="nl">BMR kcal</div>{% if inbody_prev.bmr is defined %}{{ chip(inbody.bmr, inbody_prev.bmr)|safe }}{% endif %}</div>
        <div class="num-card inbody"><div class="nv sm">{{ inbody.phase_angle }}°</div><div class="nl">Phase Angle</div>{% if inbody_prev.phase_angle is defined %}{{ chip(inbody.phase_angle, inbody_prev.phase_angle)|safe }}{% endif %}</div>
      </div>
      {% else %}
      <div style="color:var(--muted);font-size:12px;margin:auto;text-align:center;">No InBody data available</div>
      {% endif %}
    </div>
  </div>

</div>

<!-- PAGE 2 -->
<div class="page-break" style="border-top:3px solid #E8621A;"></div>
<div class="hdr">
  <img class="hdr-logo" src="{{ pwrx_logo }}"/>
  <div style="text-align:center;">
    <div class="hdr-name">{{ athlete_name }}</div>
    <div class="hdr-sub">Trend Analysis — Last 4 Sessions</div>
  </div>
  <div class="hdr-date">REPORT DATE<br/>{{ report_date }}</div>
</div>

<div class="p2-grid">
  <div class="p2-card">
    <div class="p2-hdr" style="border-bottom:2px solid var(--dari);"><img src="{{ dari_logo }}" style="height:20px;width:auto;"/> Dari — Score Trends</div>
    <div class="p2-body">
      <div class="cl">Athleticism / Functionality / Explosiveness</div>{{ chart_dari_trend }}
      <div class="cl">Dysfunction</div>{{ chart_dari_dysfunction }}
    </div>
  </div>
  <div class="p2-card">
    <div class="p2-hdr" style="border-bottom:2px solid var(--vald);"><img src="{{ vald_logo }}" style="height:14px;width:auto;"/> Vald — Trends</div>
    <div class="p2-body">
      <div class="cl">Jump Height (in)</div>{{ chart_vald_jump_height }}
      <div class="cl">RSI-Modified</div>{{ chart_vald_rsi }}
      <div class="cl">Peak Power (W)</div>{{ chart_vald_power }}
    </div>
  </div>
  <div class="p2-card">
    <div class="p2-hdr" style="border-bottom:2px solid var(--arm);"><img src="{{ armcare_logo }}" style="height:16px;width:auto;border-radius:2px;"/> ArmCare — Trends</div>
    <div class="p2-body">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div><div class="cl">Arm Score</div>{{ chart_arm_score }}</div>
        <div><div class="cl">Total Strength</div>{{ chart_arm_strength }}</div>
        <div><div class="cl">SVR</div>{{ chart_arm_svr }}</div>
        <div><div class="cl">Shoulder Balance</div>{{ chart_arm_balance }}</div>
      </div>
    </div>
  </div>
  <div class="p2-card">
    <div class="p2-hdr" style="border-bottom:2px solid var(--inbody);"><img src="{{ inbody_logo }}" style="height:16px;width:auto;filter:brightness(0) invert(1);"/> InBody — Body Composition</div>
    <div class="p2-body">
      {% if inbody.available %}
      <div style="display:flex;justify-content:center;margin-bottom:8px;">{{ chart_inbody_donut }}</div>
      <div class="cl">Segmental Lean Mass (lbs)</div>{{ chart_segments }}
      {% else %}
      <div style="color:var(--muted);font-size:12px;padding:20px;text-align:center;">No InBody data available</div>
      {% endif %}
    </div>
  </div>
</div>

{% if decline_flags %}
<div class="flag-panel">
  <div class="flag-hdr">⚠ Performance Flags — Threshold Changes from Previous Session</div>
  {% for f in decline_flags %}
  <div class="flag-item {{ f.trend }}">{{ f.source }} — {{ f.metric }}: {{ f.prev }} → {{ f.curr }} ({{ f.pct }})</div>
  {% endfor %}
</div>
{% else %}
<div class="flag-panel">
  <div class="flag-hdr">⚠ Performance Flags — Threshold Changes from Previous Session</div>
  <div class="flag-ok">✓ No significant changes detected across tracked metrics.</div>
</div>
{% endif %}

</body>
</html>
"""

def build_body_scan_dots(data: dict) -> str:
    joints = (data.get("dari") or {}).get("joints") or {}
    def jcolor(v):
        if not v or v == 0: return "#3B82F6"
        if v < 30:  return "#22c55e"
        if v < 60:  return "#F59E0B"
        return "#EF4444"
    positions = [
        ("RS",  26, 17, "r_shoulder"),
        ("LS",  74, 17, "l_shoulder"),
        ("US",  50, 23, "upper_spine"),
        ("ABD", 50, 40, "lower_spine"),
        ("RH",  30, 54, "r_hip"),
        ("LH",  70, 54, "l_hip"),
        ("RK",  32, 71, "r_knee"),
        ("LK",  68, 71, "l_knee"),
        ("RA",  34, 89, "r_ankle"),
        ("LA",  66, 89, "l_ankle"),
    ]
    dots = ""
    for short, x, y, key in positions:
        val = round(joints.get(key) or 0)
        color = jcolor(val)
        dots += (
            f'<div class="body-dot" style="position:absolute;left:{x}%;top:{y}%;transform:translate(-50%,-50%);'
            f'width:26px;height:26px;min-width:26px;min-height:26px;max-width:26px;max-height:26px;'
            f'border-radius:50%;background:{color};box-sizing:border-box;'
            f'border:1.5px solid rgba(255,255,255,0.5);'
            f'display:flex;flex-direction:column;align-items:center;justify-content:center;'
            f'box-shadow:0 0 8px {color}CC;z-index:3;">'
            f'<span style="font-family:Bebas Neue,sans-serif;font-size:10px;color:#fff;line-height:1;">{val}</span>'
            f'<span style="font-size:5.5px;color:rgba(255,255,255,0.9);line-height:1.3;">{short}</span></div>'
        )
    return dots



def render_report(data: dict, out_path: str):
    from jinja2 import Environment, BaseLoader
    env = Environment(loader=BaseLoader())
    template = env.from_string(TEMPLATE)

    dari_trend = data["dari"]["trend"]
    dari_prev = dari_trend[-2] if len(dari_trend) >= 2 else {}
    inbody_trend = (data.get("inbody") or {}).get("trend") or []
    inbody_prev = inbody_trend[-2] if len(inbody_trend) >= 2 else {}

    env.globals["chip"] = chip

    html = template.render(
        athlete_name   = data["athlete_name"],
        report_date    = data["report_date"],
        pwrx_logo      = PWRX_LOGO,
        dari_logo      = DARI_LOGO,
        vald_logo      = VALD_LOGO,
        armcare_logo   = ARMCARE_LOGO,
        inbody_logo    = INBODY_LOGO,
        body_img       = BODY_IMG,
        dari           = data["dari"],
        dari_prev      = dari_prev,
        vald           = data["vald"],
        arm            = data["arm"],
        inbody         = data["inbody"],
        inbody_prev    = inbody_prev,
        body_scan_dots = build_body_scan_dots(data),
        decline_flags  = build_decline_flags(data),
        # page 2 charts
        chart_dari_trend       = chart_dari_trend(data),
        chart_dari_dysfunction = chart_dari_dysfunction(data),
        chart_vald_jump_height = chart_vald_jump_height(data),
        chart_vald_rsi         = chart_vald_rsi(data),
        chart_vald_power       = chart_vald_power(data),
        chart_arm_score        = chart_arm_score(data),
        chart_arm_strength     = chart_arm_strength(data),
        chart_arm_svr          = chart_arm_svr(data),
        chart_arm_balance      = chart_arm_balance(data),
        chart_inbody_donut     = chart_inbody_donut(data),
        chart_segments         = chart_segments(data),
    )

    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ Report written → {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate S&C Performance Report")
    parser.add_argument("--athlete", default=DATA["athlete_name"], help="Athlete name (live DB lookup or fallback sample)")
    parser.add_argument("--out",     default="sc_report.html",     help="Output HTML file path")
    parser.add_argument("--sample",  action="store_true",          help="Force hardcoded sample data (no DB needed)")
    args = parser.parse_args()

    if args.sample:
        data = DATA.copy()
        data["athlete_name"] = args.athlete
    else:
        try:
            from sc_db import load_athlete_data
            print(f"Fetching data for: {args.athlete} ...")
            data = load_athlete_data(args.athlete)
        except ImportError:
            sys.exit("sc_db.py not found. Place it alongside this script.")
        except Exception as exc:
            print(f"Warning: DB fetch failed ({exc}). Falling back to sample data.")
            data = DATA.copy()
            data["athlete_name"] = args.athlete

    render_report(data, args.out)
    print(f"Report written -> {args.out}")


if __name__ == "__main__":
    main()
