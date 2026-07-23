"""
generate_roadmap.py
--------------------------------------------------------------------------------
PWRX Athlete Roadmap -- PNG renderer (Pillow)

Draws the 4-quadrant athlete roadmap template (Mechanical Goals / Developmental
Goals / Strength & Conditioning snapshot / Competitive Goals) as a single
2200x1700 PNG, using the same DATA dict shape returned by
sc_db.load_athlete_data() / consumed by generate_sc_report.render_report().

Goal sections (Mechanical, Developmental, Competitive) are intentionally left
blank -- coaches fill them in later in Canva. Only the Strength & Conditioning
quadrant is populated, using each athlete's most recent valid session per
source (Dari, VALD CMJ, ArmCare, InBody).

Usage:
    from generate_roadmap import render_roadmap
    render_roadmap(data, "out.png")
"""

import os
from PIL import Image, ImageDraw, ImageFont

# ─────────────────────────────────────────────────────────────────────────────
# Canvas + palette
# ─────────────────────────────────────────────────────────────────────────────

W, H = 2200, 1700

ORANGE = (244, 117, 13)
BLUE   = (127, 181, 223)
GREY   = (39, 54, 66)      # panel bg
DARK   = (37, 40, 48)      # page bg
TEXT   = (245, 247, 250)
MUTED  = (147, 164, 179)
FAINT  = (255, 255, 255, 40)          # dashed line alpha
PANEL_BORDER = (255, 255, 255, 18)
CARD_BG      = (255, 255, 255, 9)
CARD_BORDER  = (255, 255, 255, 20)

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FONT_BEBAS  = os.path.join(ASSETS, "fonts", "BebasNeue-Regular.ttf")
FONT_OSWALD = os.path.join(ASSETS, "fonts", "Oswald.ttf")
LOGO_PATH   = os.path.join(ASSETS, "logo.png")


def _oswald(size, weight="Regular"):
    f = ImageFont.truetype(FONT_OSWALD, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def _bebas(size):
    return ImageFont.truetype(FONT_BEBAS, size)


# ─────────────────────────────────────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _rounded_rect(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _dashed_hline(draw, x0, x1, y, dash=10, gap=8, fill=FAINT, width=3):
    x = x0
    while x < x1:
        xe = min(x + dash, x1)
        draw.line([(x, y), (xe, y)], fill=fill, width=width)
        x += dash + gap


def _text(draw, xy, s, font, fill=TEXT, anchor="la", tracking=0):
    """Draw text with optional letter-spacing (tracking, in px)."""
    if not tracking:
        draw.text(xy, s, font=font, fill=fill, anchor=anchor)
        return
    # manual letter-spaced draw (anchor only supported for the whole block's
    # left edge here; used for uppercase labels which are left/center anchored)
    x, y = xy
    total_w = 0
    widths = []
    for ch in s:
        w = draw.textlength(ch, font=font)
        widths.append(w)
        total_w += w + tracking
    total_w -= tracking

    if anchor[0] == "m":
        x -= total_w / 2
    elif anchor[0] == "r":
        x -= total_w

    va = anchor[1] if len(anchor) > 1 else "a"
    for ch, w in zip(s, widths):
        draw.text((x, y), ch, font=font, fill=fill, anchor="l" + va)
        x += w + tracking


def _fmt(val, decimals=1, suffix=""):
    try:
        v = float(val)
    except (TypeError, ValueError):
        return "--"
    if decimals == 0:
        return f"{int(round(v))}{suffix}"
    return f"{v:.{decimals}f}{suffix}"


# ─────────────────────────────────────────────────────────────────────────────
# Main render
# ─────────────────────────────────────────────────────────────────────────────

def render_roadmap(data: dict, out_path: str, athlete_name: str = None, season: str = None):
    img = Image.new("RGB", (W, H), DARK)
    draw = ImageDraw.Draw(img, "RGBA")

    pad_x, pad_top, pad_bottom = 84, 68, 60

    # ── Header ──────────────────────────────────────────────────────────────
    header_bottom = 236  # y of the orange divider line

    logo_size = 128
    logo_y = pad_top
    if os.path.exists(LOGO_PATH):
        logo = Image.open(LOGO_PATH).convert("RGBA").resize((logo_size, logo_size))
        img.paste(logo, (pad_x, logo_y), logo)

    title_x = pad_x + logo_size + 36
    _text(draw, (title_x, logo_y + 6), "PWRX PERFORMANCE",
          _oswald(26, "SemiBold"), fill=BLUE, tracking=8)
    _text(draw, (title_x, logo_y + 40), "ATHLETE ROADMAP", _bebas(88), fill=TEXT)

    # header-right: Athlete / Season fields
    field_w = 340
    gap = 68
    field2_x = W - pad_x - field_w
    field1_x = field2_x - gap - field_w
    field_label_y = logo_y + 18
    field_line_y = logo_y + 78

    name_val = (athlete_name or data.get("athlete_name") or "").upper()
    season_val = (season or "").upper()

    _text(draw, (field1_x, field_label_y), "ATHLETE", _oswald(22, "SemiBold"), fill=MUTED, tracking=5)
    if name_val:
        _text(draw, (field1_x, field_line_y - 34), name_val, _oswald(26, "Medium"), fill=TEXT)
    _dashed_hline(draw, field1_x, field1_x + field_w, field_line_y)

    _text(draw, (field2_x, field_label_y), "SEASON / DATE", _oswald(22, "SemiBold"), fill=MUTED, tracking=5)
    if season_val:
        _text(draw, (field2_x, field_line_y - 34), season_val, _oswald(26, "Medium"), fill=TEXT)
    _dashed_hline(draw, field2_x, field2_x + field_w, field_line_y)

    draw.line([(pad_x, header_bottom), (W - pad_x, header_bottom)], fill=ORANGE, width=6)

    # ── Grid ────────────────────────────────────────────────────────────────
    grid_top = header_bottom + 44
    grid_bottom = H - pad_bottom - 48   # leave room for footer
    grid_gap = 36
    col_w = (W - pad_x * 2 - grid_gap) / 2
    row_h = (grid_bottom - grid_top - grid_gap) / 2

    q1_box = (pad_x, grid_top, pad_x + col_w, grid_top + row_h)
    q2_box = (pad_x + col_w + grid_gap, grid_top, W - pad_x, grid_top + row_h)
    q3_box = (pad_x, grid_top + row_h + grid_gap, pad_x + col_w, grid_bottom)
    q4_box = (pad_x + col_w + grid_gap, grid_top + row_h + grid_gap, W - pad_x, grid_bottom)

    _draw_quadrant_frame(draw, q1_box, ORANGE, "01", "MECHANICAL GOALS")
    _draw_quadrant_frame(draw, q2_box, BLUE, "02", "DEVELOPMENTAL GOALS")
    _draw_quadrant_frame(draw, q3_box, ORANGE, "03", "STRENGTH & CONDITIONING")
    _draw_quadrant_frame(draw, q4_box, BLUE, "04", "COMPETITIVE / IN-SEASON GOALS")

    _draw_dev_split(draw, q2_box)
    _draw_sc_snapshot(draw, img, q3_box, data)

    # ── Footer ──────────────────────────────────────────────────────────────
    footer_y = H - pad_bottom + 4
    _text(draw, (pad_x, footer_y), "PWRX ATHLETE DEVELOPMENT ROADMAP — TEMPLATE",
          _oswald(19), fill=(255, 255, 255, 70), tracking=1)
    fnote = "FOR COACH USE — EDIT IN CANVA"
    fw = draw.textlength(fnote, font=_oswald(19))
    _text(draw, (W - pad_x - fw, footer_y), fnote, _oswald(19), fill=(255, 255, 255, 70), tracking=1)

    img.save(out_path, "PNG")
    return out_path


def _draw_quadrant_frame(draw, box, accent, tag, title):
    x0, y0, x1, y1 = box
    _rounded_rect(draw, box, radius=20, fill=GREY + (255,), outline=PANEL_BORDER, width=2)
    # accent top stripe (clipped to rounded corners via a simple top rect)
    draw.rounded_rectangle((x0, y0, x1, y0 + 24), radius=20, fill=accent)
    draw.rectangle((x0, y0 + 12, x1, y0 + 16), fill=accent)  # square off the bottom of the stripe

    header_y = y0 + 36
    tag_font = _oswald(24, "Bold")
    tag_w = draw.textlength(tag, font=tag_font) + 32
    tag_h = 44
    _rounded_rect(draw, (x0 + 44, header_y, x0 + 44 + tag_w, header_y + tag_h), radius=8, fill=accent)
    _text(draw, (x0 + 44 + tag_w / 2, header_y + tag_h / 2), tag, tag_font,
          fill=DARK, anchor="mm")

    _text(draw, (x0 + 44 + tag_w + 20, header_y + tag_h / 2), title, _bebas(48),
          fill=TEXT, anchor="lm")


def _draw_dev_split(draw, box):
    x0, y0, x1, y1 = box
    content_top = y0 + 116
    mid_x = (x0 + x1) / 2
    divider_x = mid_x
    pad_inner = 44

    _text(draw, (x0 + pad_inner, content_top), "ATHLETE GOALS",
          _oswald(25, "SemiBold"), fill=BLUE, tracking=4)
    _text(draw, (divider_x + pad_inner / 2, content_top), "COACH GOALS",
          _oswald(25, "SemiBold"), fill=ORANGE, tracking=4)

    draw.line([(divider_x, content_top), (divider_x, y1 - 36)], fill=PANEL_BORDER, width=2)


# ─────────────────────────────────────────────────────────────────────────────
# S&C snapshot (bottom-left quadrant)
# ─────────────────────────────────────────────────────────────────────────────

def _draw_sc_snapshot(draw, img, box, data):
    x0, y0, x1, y1 = box
    content_top = y0 + 108
    content_bottom = y1 - 40
    content_left = x0 + 44
    content_right = x1 - 44
    gap = 20

    col_w = (content_right - content_left - gap) / 2
    row_h = (content_bottom - content_top - gap) / 2

    dari_box = (content_left, content_top, content_left + col_w, content_top + row_h)
    vald_box = (content_left + col_w + gap, content_top, content_right, content_top + row_h)
    arm_box  = (content_left, content_top + row_h + gap, content_left + col_w, content_bottom)
    ib_box   = (content_left + col_w + gap, content_top + row_h + gap, content_right, content_bottom)

    dari = data.get("dari", {})
    dari_current = dari.get("current", {})
    dari_has_data = data.get("data_coverage", {}).get("dari", 0) > 0

    vald = data.get("vald", {}).get("current", {})
    vald_has_data = data.get("data_coverage", {}).get("vald", 0) > 0

    arm = data.get("arm", {}).get("current", {})
    arm_has_data = data.get("data_coverage", {}).get("armcare", 0) > 0

    inbody = data.get("inbody", {})
    ib_has_data = inbody.get("available", False)

    _sc_card_frame(draw, dari_box, "DARI MOTION", BLUE)
    if dari_has_data:
        _draw_dari_card(draw, dari_box, dari, dari_current)
    else:
        _sc_no_data(draw, dari_box)

    _sc_card_frame(draw, vald_box, "VALD FORCEDECKS", ORANGE)
    if vald_has_data:
        _draw_stat_pair(draw, vald_box,
                         _fmt(vald.get("peak_power"), 0), "W", "PEAK POWER",
                         _fmt(vald.get("jump_height"), 1), "in", "JUMP HEIGHT")
    else:
        _sc_no_data(draw, vald_box)

    _sc_card_frame(draw, arm_box, "ARMCARE", BLUE)
    if arm_has_data:
        _draw_stat_pair(draw, arm_box,
                         _fmt(arm.get("arm_score"), 1), "", "ARM SCORE",
                         _fmt(arm.get("total_strength"), 1), "lb", "TOTAL STRENGTH")
    else:
        _sc_no_data(draw, arm_box)

    _sc_card_frame(draw, ib_box, "INBODY", ORANGE)
    if ib_has_data:
        _draw_stat_trio(draw, ib_box,
                         _fmt(inbody.get("score"), 0), "", "SCORE",
                         _fmt(inbody.get("weight"), 1), "lb", "WEIGHT",
                         _fmt(inbody.get("pbf"), 1), "%", "BODY FAT")
    else:
        _sc_no_data(draw, ib_box)


def _sc_card_frame(draw, box, label, dot_color):
    x0, y0, x1, y1 = box
    _rounded_rect(draw, box, radius=14, fill=CARD_BG, outline=CARD_BORDER, width=2)
    cx, cy = x0 + 24, y0 + 20
    r = 5
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=dot_color)
    _text(draw, (cx + 12, y0 + 18), label, _oswald(20, "SemiBold"), fill=MUTED, tracking=3.6)


def _sc_no_data(draw, box):
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + 10
    _text(draw, (cx, cy), "NO DATA YET", _oswald(20, "Medium"), fill=MUTED, anchor="mm", tracking=2)


def _draw_dari_card(draw, box, dari, current):
    x0, y0, x1, y1 = box
    body_top = y0 + 56
    body_bottom = y1 - 20
    mid_y = (body_top + body_bottom) / 2

    main_x = x0 + 24
    overall = _fmt(current.get("overall"), 1)
    _text(draw, (main_x, mid_y - 6), overall, _bebas(88), fill=TEXT, anchor="lm")
    ov_w = draw.textlength(overall, font=_bebas(88))
    _text(draw, (main_x, mid_y + 46), "OVERALL", _oswald(18, "SemiBold"), fill=ORANGE, tracking=3)

    divider_x = main_x + max(ov_w, 170) + 24
    draw.line([(divider_x, body_top), (divider_x, body_bottom)], fill=PANEL_BORDER, width=2)

    subs_x = divider_x + 24
    subs_right = x1 - 24
    rows = [
        ("Function", _fmt(dari.get("current", {}).get("functionality"), 1)),
        ("Explosive", _fmt(dari.get("current", {}).get("explosiveness"), 1)),
        ("Dysfunction", _fmt(dari.get("current", {}).get("dysfunction"), 1)),
        ("Vulnerability", _fmt(dari.get("percentiles", {}).get("vulnerability"), 1)),
    ]
    n = len(rows)
    row_span = (body_bottom - body_top) / n
    for i, (lbl, val) in enumerate(rows):
        ry = body_top + row_span * i + row_span / 2
        _text(draw, (subs_x, ry), lbl, _oswald(20), fill=MUTED, anchor="lm")
        _text(draw, (subs_right, ry), val, _oswald(26, "SemiBold"), fill=TEXT, anchor="rm")


def _draw_stat_pair(draw, box, val1, unit1, lbl1, val2, unit2, lbl2):
    x0, y0, x1, y1 = box
    body_top = y0 + 56
    body_bottom = y1 - 20
    mid_y = (body_top + body_bottom) / 2
    mid_x = (x0 + x1) / 2

    draw.line([(mid_x, body_top), (mid_x, body_bottom)], fill=PANEL_BORDER, width=2)

    _stat_block(draw, ((x0, body_top, mid_x, body_bottom)), val1, unit1, lbl1, mid_y)
    _stat_block(draw, ((mid_x, body_top, x1, body_bottom)), val2, unit2, lbl2, mid_y)


def _draw_stat_trio(draw, box, val1, unit1, lbl1, val2, unit2, lbl2, val3, unit3, lbl3):
    x0, y0, x1, y1 = box
    body_top = y0 + 56
    body_bottom = y1 - 20
    mid_y = (body_top + body_bottom) / 2
    third = (x1 - x0) / 3

    x_a, x_b, x_c = x0, x0 + third, x0 + 2 * third
    draw.line([(x_b, body_top), (x_b, body_bottom)], fill=PANEL_BORDER, width=2)
    draw.line([(x_c, body_top), (x_c, body_bottom)], fill=PANEL_BORDER, width=2)

    _stat_block(draw, (x_a, body_top, x_b, body_bottom), val1, unit1, lbl1, mid_y, size=48)
    _stat_block(draw, (x_b, body_top, x_c, body_bottom), val2, unit2, lbl2, mid_y, size=48)
    _stat_block(draw, (x_c, body_top, x1, body_bottom), val3, unit3, lbl3, mid_y, size=48)


def _stat_block(draw, box, val, unit, label, mid_y, size=60):
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    val_font = _bebas(size)
    unit_font = _oswald(int(size * 0.4), "Medium")

    val_w = draw.textlength(val, font=val_font)
    unit_w = draw.textlength(" " + unit, font=unit_font) if unit else 0
    total_w = val_w + unit_w
    start_x = cx - total_w / 2

    _text(draw, (start_x, mid_y - 8), val, val_font, fill=TEXT, anchor="lm")
    if unit:
        _text(draw, (start_x + val_w + 6, mid_y + 4), unit, unit_font, fill=MUTED, anchor="lm")

    _text(draw, (cx, mid_y + size * 0.55), label, _oswald(17, "Medium"),
          fill=MUTED, anchor="mm", tracking=2.4)


if __name__ == "__main__":
    # Quick manual test with sample data
    sample = {
        "athlete_name": "Sample Athlete",
        "dari": {
            "current": {"overall": 82.72, "functionality": 71.28, "explosiveness": 97.76, "dysfunction": 3.6},
            "percentiles": {"vulnerability": 31.2},
        },
        "vald": {"current": {"peak_power": 5790, "jump_height": 19.8}},
        "arm": {"current": {"arm_score": 94.6, "total_strength": 177.9}},
        "inbody": {"available": True, "score": 94, "weight": 194.5, "pbf": 13.4},
        "data_coverage": {"dari": 4, "vald": 4, "armcare": 4, "inbody": 2},
    }
    render_roadmap(sample, "/tmp/roadmap_test.png", athlete_name="Sample Athlete", season="2026")
    print("wrote /tmp/roadmap_test.png")
