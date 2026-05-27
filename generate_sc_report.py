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
            {"session": "Sep '25", "athleticism": 84.7, "functionality": 73.2, "explosiveness": 99.4, "dysfunction": 3.1},
            {"session": "Nov '25", "athleticism": 86.0, "functionality": 79.7, "explosiveness": 95.0, "dysfunction": 2.8},
            {"session": "Dec '25", "athleticism": 85.2, "functionality": 79.6, "explosiveness": 95.1, "dysfunction": 4.2},
            {"session": "Jan '26", "athleticism": 83.3, "functionality": 74.1, "explosiveness": 97.7, "dysfunction": 5.2},
        ],
        "current": {"athleticism": 83.3, "functionality": 74.1, "explosiveness": 97.7, "dysfunction": 5.2},
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
        "weight": 207.7,
        "smm":    93.5,
        "pbf":    22.1,
        "bmi":    29.0,
        "score":  85,
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

    ax.set_ylim(65, 110)
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

    fig, ax = _make_fig(4.2, 1.1)
    ax.set_facecolor("none")

    ax.plot(x, vals, color=C["amber"], linewidth=2, marker="o", markersize=5)
    ax.fill_between(x, vals, alpha=0.15, color=C["amber"])

    ax.set_ylim(0, 10)
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
    ax.set_ylim(18, 22)
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
    ax.set_ylim(0.60, 0.85)
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
    vals = [r["peak_power"] for r in rows]
    colors = [C["blueL"]] * (len(vals) - 1) + [C["orange"]]

    fig, ax = _make_fig(4.2, 1.2)
    ax.set_facecolor("none")

    bars = ax.bar(sessions, vals, color=colors, width=0.55, zorder=2)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 30,
                f"{val:,}", ha="center", va="bottom", fontsize=6.5, color=C["greyL"])

    ax.set_ylim(5200, 6300)
    ax.tick_params(axis="x", colors=C["grey"], labelsize=7)
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
    ax.set_ylim(68, 115)
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
    ax.set_ylim(140, 230)
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
    ax.set_ylim(1.5, 2.5)
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
    ax.set_ylim(0.80, 1.15)
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


def chip(current, previous):
    if previous == 0:
        return ""
    pct   = round((current - previous) / previous * 100, 1)
    color = "#22c55e" if pct >= 0 else "#ef4444"
    bg    = "rgba(34,197,94,0.18)" if pct >= 0 else "rgba(239,68,68,0.15)"
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
  display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
  background: rgba(255,255,255,0.04); border-radius: 6px; padding: 8px 10px;
}
.pwrx-focus-num {
  width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; font-size: 11px; font-weight: 900; color: #fff;
}
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
</style>
</head>
<body>

<!-- HEADER -->
<div class="pwrx-header">
  <div style="width:160px;"></div>
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
  <div class="pwrx-panel">
    <div class="pwrx-panel-header blue">DARI — Athletic Movement</div>
    <div class="pwrx-panel-body">

      <!-- Gauges -->
      <div style="display:flex;justify-content:space-around;margin-bottom:10px;">
        {{ gauge_athleticism }}
        {{ gauge_functionality }}
        {{ gauge_explosiveness }}
        {{ gauge_dysfunction }}
      </div>

      <div class="pwrx-divider"></div>
      <div class="pwrx-section-label">Last 4 Sessions — Score Trend</div>
      {{ chart_dari_trend }}

      <div class="pwrx-divider"></div>
      <div class="pwrx-section-label">Dysfunction Score</div>
      {{ chart_dari_dysfunction }}
      <div class="pwrx-divider"></div>
      <div class="pwrx-section-label">Focus Areas</div>
      {% for i, area, color in dari_focus %}
      <div class="pwrx-focus-item" style="border:1px solid {{ color }}33;">
        <div class="pwrx-focus-num" style="background:{{ color }};">{{ i }}</div>
        <span style="font-size:10px;color:#C5D6E8;font-weight:600;">{{ area }}</span>
      </div>
      {% endfor %}
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
      <div class="pwrx-divider"></div>
      <div class="pwrx-section-label">Segmental Lean Mass (lbs)</div>
      {{ chart_segments }}
    </div>
  </div>

</div><!-- /pwrx-grid -->

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
    areas  = data["dari"]["focus_areas"]
    colors = [C["orange"], C["amber"], C["blueL"], C["purple"], C["green"]]
    return [(i + 1, area, colors[i % len(colors)]) for i, area in enumerate(areas)]


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
        {"src": "InBody",  "lbl": "Body Fat %",     "val": f'{ib["pbf"]}%',         "color": C["orange"], "chip": ""},
    ]


def render_report(data: dict, out_path: str):
    env = Environment(loader=BaseLoader())
    env.globals["C"] = type("C", (), C)()

    template = env.from_string(TEMPLATE)

    vald_c = data["vald"]["current"]
    vald_p = data["vald"]["prev"]
    arm_c  = data["arm"]["current"]
    arm_p  = data["arm"]["prev"]

    html = template.render(
        athlete_name=data["athlete_name"],
        report_date=data["report_date"],
        C=type("C", (), C)(),
        dari=data["dari"],
        vald=data["vald"],
        arm=data["arm"],
        inbody=data["inbody"],
        # gauges
        gauge_athleticism  =gauge_svg(data["dari"]["current"]["athleticism"],   100, "Athleticism",   C["orange"]),
        gauge_functionality=gauge_svg(data["dari"]["current"]["functionality"],  100, "Functionality", C["blueL"]),
        gauge_explosiveness=gauge_svg(data["dari"]["current"]["explosiveness"],  120, "Explosiveness", C["green"]),
        gauge_dysfunction  =gauge_svg(data["dari"]["current"]["dysfunction"],     15, "Dysfunction",   C["amber"]),
        # chips
        chip_jump        =chip(vald_c["jump_height"],    vald_p["jump_height"]),
        chip_power       =chip(vald_c["peak_power"],     vald_p["peak_power"]),
        chip_rsi         =chip(vald_c["rsi_mod"],        vald_p["rsi_mod"]),
        chip_arm_score   =chip(arm_c["arm_score"],       arm_p["arm_score"]),
        chip_arm_strength=chip(arm_c["total_strength"],  arm_p["total_strength"]),
        chip_arm_svr     =chip(arm_c["svr"],             arm_p["svr"]),
        # focus list
        dari_focus=build_focus_list(data),
        # charts (matplotlib base64 PNGs)
        chart_dari_trend       =chart_dari_trend(data),
        chart_dari_dysfunction =chart_dari_dysfunction(data),
        chart_vald_jump_height =chart_vald_jump_height(data),
        chart_vald_rsi         =chart_vald_rsi(data),
        chart_vald_power    =chart_vald_power(data),
        chart_arm_score     =chart_arm_score(data),
        chart_arm_strength  =chart_arm_strength(data),
        chart_arm_svr       =chart_arm_svr(data),
        chart_arm_balance   =chart_arm_balance(data),
        chart_inbody_donut  =chart_inbody_donut(data),
        chart_segments      =chart_segments(data),
        # summary
        summary_kpis=build_summary_kpis(data),
    )

    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ Report written → {out_path}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

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
