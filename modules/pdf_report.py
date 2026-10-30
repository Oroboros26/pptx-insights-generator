"""
Branded A4 PDF report using fpdf2.

Design: Inter typography, surface-1 rounded cards, monochrome circular bullet badges,
a two-column highlights/risks block, and a full-width Watch callout. All drawing
uses fpdf2 primitives — no HTML engine — so the pipeline stays pure-Python.

Structure of the generated PDF:
  1. Header — report title, week/date meta, black rule
  2. Executive Summary — overall paragraph + two-column highlights/risks cards + watch box
  3. Slide Analysis — one card per business slide (pill label, situation, bullets)
  4. Footer (every page) — confidentiality note, page number, optional logo
"""
import os
from datetime import datetime, timedelta

from PIL import Image

from .utils import _clean, _abbrev_numbers, _parse_exec_summary, _parse_slide_insight

# Assets live one level up (in ai-ppt-automation/, not in modules/)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FONT_DIR = os.path.join(_BASE_DIR, "assets", "fonts")

# Font family names registered with fpdf2
FONT      = "Inter"           # regular + bold (style "B")
FONT_MED  = "Inter-Medium"
FONT_SEMI = "Inter-SemiBold"

# ── Design tokens — neutral black & white theme ──────────────────────────────
CLR_PRIMARY   = (26, 26, 24)     # #1a1a18 — near-black (headings, accents)
CLR_SECONDARY = (95, 94, 90)     # #5f5e5a — body text
CLR_MUTED     = (136, 135, 128)  # #888780 — meta / captions
CLR_SURFACE1  = (238, 237, 233)  # #eeede9 — card / pill background
CLR_HAIRLINE  = (215, 214, 209)  # subtle rule on white
CLR_WHITE     = (255, 255, 255)
CLR_MIDGREY   = (120, 120, 118)  # neutral badge fill for warn bullets

# Monochrome bullet badge definitions.
# Meaning is carried by the glyph (+, −, !, →), not by colour.
# Each entry: (fill_colour, glyph_colour, glyph_char, border_colour or None)
_KIND = {
    "pos":  (CLR_PRIMARY, CLR_WHITE,   "+", None),
    "neg":  (CLR_WHITE,   CLR_PRIMARY, "−", CLR_PRIMARY),  # hollow circle, minus sign
    "warn": (CLR_MIDGREY, CLR_WHITE,   "!", None),
    "act":  (CLR_PRIMARY, CLR_WHITE,   "→", None),
}

# Bullet geometry constants (all in mm)
_DOT_R   = 2.2   # circle radius
_DOT_D   = _DOT_R * 2
_DOT_COL = 7.0   # width of the badge column including gap before text
_BLH     = 5.0   # bullet line height
_BGAP    = 1.8   # vertical gap after each bullet


def _register_fonts(pdf):
    """Register Inter from assets/fonts/, or fall back to system DejaVu Sans.
    Returns True if Inter was found, False if falling back."""
    inter = {
        (FONT, ""):      "Inter-Regular.otf",
        (FONT, "B"):     "Inter-Bold.otf",
        (FONT_MED, ""):  "Inter-Medium.otf",
        (FONT_SEMI, ""): "Inter-SemiBold.otf",
    }
    if all(os.path.exists(os.path.join(_FONT_DIR, fn)) for fn in inter.values()):
        for (fam, style), fn in inter.items():
            pdf.add_font(fam, style, os.path.join(_FONT_DIR, fn))
        return True
    # Fallback: DejaVu Sans is pre-installed on most Linux Docker images
    dj   = "/usr/share/fonts/truetype/dejavu"
    reg  = os.path.join(dj, "DejaVuSans.ttf")
    bold = os.path.join(dj, "DejaVuSans-Bold.ttf")
    for fam in (FONT, FONT_MED, FONT_SEMI):
        pdf.add_font(fam, "", reg)
    pdf.add_font(FONT, "B", bold if os.path.exists(bold) else reg)
    return False


def _ensure_space(pdf, height):
    """Insert a page break if the next block of `height` mm would overflow the page."""
    if pdf.get_y() + height > pdf.h - pdf.b_margin:
        pdf.add_page()


def _dot_bullet(pdf, x, y, width, text, kind):
    """Draw a circular badge + wrapped text at absolute position (x, y).
    Returns the total height consumed in mm."""
    fill, fg, ch, border = _KIND.get(kind, _KIND["pos"])
    text   = _clean(text)
    text_w = width - _DOT_COL

    pdf.set_font(FONT, "", 9)
    th = pdf.multi_cell(text_w, _BLH, text, dry_run=True, output="HEIGHT")

    # Draw the circular badge centred on the first text line
    cx, cy = x + _DOT_R, y + _BLH / 2
    pdf.set_fill_color(*fill)
    if border:
        pdf.set_draw_color(*border)
        pdf.set_line_width(0.35)
        pdf.ellipse(cx - _DOT_R, cy - _DOT_R, _DOT_D, _DOT_D, style="DF")
    else:
        pdf.ellipse(cx - _DOT_R, cy - _DOT_R, _DOT_D, _DOT_D, style="F")

    # Draw the glyph character centred inside the badge
    pdf.set_font(FONT, "B", 7)
    pdf.set_text_color(*fg)
    pdf.set_xy(cx - _DOT_R, cy - _DOT_R - 0.35)
    pdf.cell(_DOT_D, _DOT_D, ch, align="C")

    # Draw the wrapped text to the right of the badge
    pdf.set_font(FONT, "", 9)
    pdf.set_text_color(*CLR_SECONDARY)
    pdf.set_xy(x + _DOT_COL, y)
    pdf.multi_cell(text_w, _BLH, text, align="L")
    return max(th, _DOT_D) + _BGAP


def _bullet_height(pdf, text, width):
    """Dry-run a bullet to measure its height without drawing it."""
    pdf.set_font(FONT, "", 9)
    th = pdf.multi_cell(width - _DOT_COL, _BLH, _clean(text),
                        dry_run=True, output="HEIGHT")
    return max(th, _DOT_D) + _BGAP


def _paragraph_height(pdf, text, width, size=9.0, lh=5.4):
    """Dry-run a paragraph to measure its height without drawing it."""
    pdf.set_font(FONT, "", size)
    return pdf.multi_cell(width, lh, _clean(text), dry_run=True, output="HEIGHT")


def _col_content_height(pdf, width, bullets):
    """Calculate total height of a column of bullets (used to size two-column cards)."""
    h = 6.5  # title row + gap
    for text, kind in bullets:
        h += _bullet_height(pdf, text, width)
    return h


def _render_col(pdf, x, y, width, title, bullets):
    """Render a labelled column of bullets at position (x, y)."""
    pdf.set_xy(x, y)
    pdf.set_font(FONT, "B", 7.5)
    pdf.set_text_color(*CLR_PRIMARY)
    pdf.cell(width, 4, title.upper())
    cy = y + 6.5
    for text, kind in bullets:
        cy += _dot_bullet(pdf, x, cy, width, text, kind)


def _two_column_block(pdf, left_title, left_bullets, right_title, right_bullets):
    """Two equal-height surface-1 cards side by side: highlights on left, risks on right."""
    gap, pad = 6, 5
    col_w = (pdf.epw - gap) / 2
    inner = col_w - 2 * pad
    hL = _col_content_height(pdf, inner, left_bullets)
    hR = _col_content_height(pdf, inner, right_bullets)
    card_h = max(hL, hR) + 2 * pad - _BGAP
    _ensure_space(pdf, card_h + 4)

    y0 = pdf.get_y()
    xL = pdf.l_margin
    xR = pdf.l_margin + col_w + gap
    pdf.set_fill_color(*CLR_SURFACE1)
    pdf.rect(xL, y0, col_w, card_h, style="F", round_corners=True, corner_radius=3)
    pdf.rect(xR, y0, col_w, card_h, style="F", round_corners=True, corner_radius=3)
    _render_col(pdf, xL + pad, y0 + pad, inner, left_title, left_bullets)
    _render_col(pdf, xR + pad, y0 + pad, inner, right_title, right_bullets)
    pdf.set_y(y0 + card_h)


def _section_label(pdf, text, rule=False):
    """Print an uppercase section heading, optionally followed by a hairline rule."""
    pdf.set_font(FONT, "B", 8)
    pdf.set_text_color(*CLR_PRIMARY)
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 5, text.upper(), new_x="LMARGIN", new_y="NEXT")
    if rule:
        pdf.set_draw_color(*CLR_HAIRLINE)
        pdf.set_line_width(0.2)
        y = pdf.get_y() + 0.5
        pdf.line(pdf.l_margin, y, pdf.l_margin + pdf.epw, y)
        pdf.ln(3.5)


def _exec_overall(pdf, text):
    """Render the overall paragraph with a primary-colour left accent bar."""
    text = _clean(_abbrev_numbers(text or ""))
    if not text:
        return
    tx = pdf.l_margin + 5
    tw = pdf.epw - 5
    pdf.set_font(FONT, "", 9.5)
    h = pdf.multi_cell(tw, 5.6, text, dry_run=True, output="HEIGHT")
    _ensure_space(pdf, h + 4)
    y0 = pdf.get_y()
    pdf.set_fill_color(*CLR_PRIMARY)
    pdf.rect(pdf.l_margin, y0, 1.3, h, style="F")  # accent bar
    pdf.set_xy(tx, y0)
    pdf.set_text_color(*CLR_SECONDARY)
    pdf.multi_cell(tw, 5.6, text, align="L")
    pdf.set_y(y0 + h + 5)


def _watch_box(pdf, text):
    """Render a full-width grey callout box with a black left accent bar and bold Watch: label."""
    text = _clean(_abbrev_numbers(text or ""))
    if not text:
        return
    pad  = 4
    lead = 2   # width of the black accent bar on the left edge
    inner   = pdf.epw - 2 * pad - lead
    content = "**Watch:**  " + text
    pdf.set_font(FONT, "", 9)
    try:
        h = pdf.multi_cell(inner, 5.4, content, dry_run=True, output="HEIGHT", markdown=True)
    except Exception:
        h = pdf.multi_cell(inner, 5.4, "Watch:  " + text, dry_run=True, output="HEIGHT")
        content = "Watch:  " + text
    box_h = h + 2 * pad
    _ensure_space(pdf, box_h + 4)
    y0 = pdf.get_y()
    pdf.set_fill_color(*CLR_SURFACE1)
    pdf.rect(pdf.l_margin, y0, pdf.epw, box_h, style="F", round_corners=True, corner_radius=3)
    pdf.set_fill_color(*CLR_PRIMARY)
    pdf.rect(pdf.l_margin, y0, lead, box_h, style="F")  # accent bar
    pdf.set_xy(pdf.l_margin + lead + pad, y0 + pad)
    pdf.set_text_color(*CLR_PRIMARY)
    try:
        pdf.multi_cell(inner, 5.4, content, markdown=True, align="L")
    except Exception:
        pdf.multi_cell(inner, 5.4, content, align="L")
    pdf.set_y(y0 + box_h + 5)


def _slide_block(pdf, num, parsed):
    """Render one slide's insight card: pill label, situation paragraph, bullet list."""
    situation = _abbrev_numbers(parsed.get("situation", "") or "")
    bullets   = [(_abbrev_numbers(t), "pos") for t in parsed.get("obs_pos", [])]
    bullets  += [(_abbrev_numbers(t), "neg") for t in parsed.get("obs_neg", [])]
    if parsed.get("watch"):
        bullets.append((_abbrev_numbers(parsed["watch"]), "warn"))
    if parsed.get("action"):
        bullets.append((_abbrev_numbers(parsed["action"]), "act"))

    # Estimate total block height so we can keep it on one page if it fits
    pill_h = 5.5
    total  = pill_h + 3
    if situation.strip():
        total += _paragraph_height(pdf, situation, pdf.epw) + 2
    for text, kind in bullets:
        total += _bullet_height(pdf, text, pdf.epw)
    total += 6  # separator + trailing space

    if total < (pdf.h - pdf.t_margin - pdf.b_margin):
        _ensure_space(pdf, total)

    x = pdf.l_margin

    # Slide pill label (e.g. "SLIDE 3")
    pdf.set_font(FONT_SEMI, "", 7)
    label  = f"SLIDE {num}"
    pill_w = pdf.get_string_width(label) + 8
    y      = pdf.get_y()
    pdf.set_fill_color(*CLR_SURFACE1)
    pdf.rect(x, y, pill_w, pill_h, style="F", round_corners=True, corner_radius=2.5)
    pdf.set_xy(x, y)
    pdf.set_text_color(*CLR_MUTED)
    pdf.cell(pill_w, pill_h, label, align="C")
    pdf.set_y(y + pill_h + 3)

    # Situation (📍 line)
    if situation.strip():
        pdf.set_font(FONT, "", 9)
        pdf.set_text_color(*CLR_SECONDARY)
        pdf.set_x(x)
        pdf.multi_cell(pdf.epw, 5.4, _clean(situation), align="L")
        pdf.ln(1)

    # Observation, watch, and action bullets
    cy = pdf.get_y()
    for text, kind in bullets:
        cy += _dot_bullet(pdf, x, cy, pdf.epw, text, kind)
    pdf.set_y(cy + 1)

    # Hairline separator between slides
    pdf.set_draw_color(*CLR_HAIRLINE)
    pdf.set_line_width(0.2)
    yy = pdf.get_y() + 1
    pdf.line(x, yy, x + pdf.epw, yy)
    pdf.ln(5)


def generate_pdf_report(slide_results, filename, output_path, executive_summary=""):
    """Render the full branded A4 PDF and save it to output_path."""
    from fpdf import FPDF

    LOGO_PATH = os.path.join(_BASE_DIR, "assets", "logo.png")  # optional: add your own logo here
    week_num  = datetime.now().isocalendar()[1]
    run_date  = datetime.now().strftime("%d %b %Y")

    business_slides = [
        r for r in slide_results
        if not r["insight"].strip().lower().startswith("no business data")
    ]

    # Pre-calculate logo dimensions for the footer
    _logo_w, _logo_h = 0, 10
    if os.path.exists(LOGO_PATH):
        with Image.open(LOGO_PATH) as _img:
            _iw, _ih = _img.size
        _logo_w = (_iw / _ih) * _logo_h

    today      = datetime.now()
    monday     = today - timedelta(days=today.weekday())
    sunday     = monday + timedelta(days=6)
    week_range = f"{monday.strftime('%d')}–{sunday.strftime('%d %b %Y')}"

    class _PDF(FPDF):
        def footer(self):
            self.set_y(-13)
            self.set_font(FONT, "", 7.5)
            self.set_text_color(*CLR_MUTED)
            self.cell(0, 5, f"Confidential   ·   Generated by AI   ·   {run_date}"
                            f"   ·   Page {self.page_no()}", align="L")
            if _logo_w > 0:
                self.image(LOGO_PATH, x=self.w - self.r_margin - _logo_w,
                           y=self.h - 14.5, h=_logo_h)

    pdf = _PDF(format="A4")
    _register_fonts(pdf)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()

    # ── Header ──
    pdf.set_font(FONT, "B", 21)
    pdf.set_text_color(*CLR_PRIMARY)
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 11, "Weekly Performance Report", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.5)
    pdf.set_font(FONT_MED, "", 7.5)
    pdf.set_text_color(*CLR_MUTED)
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 5, f"W{week_num}   ·   {week_range}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2.5)
    pdf.set_draw_color(*CLR_PRIMARY)
    pdf.set_line_width(0.5)
    yy = pdf.get_y()
    pdf.line(pdf.l_margin, yy, pdf.l_margin + pdf.epw, yy)
    pdf.ln(8)

    # ── Executive summary ──
    if executive_summary:
        sec = _parse_exec_summary(executive_summary)
        _section_label(pdf, "Executive Summary")
        pdf.ln(1.5)
        _exec_overall(pdf, sec.get("overall") or executive_summary)

        left   = [(t, "pos")  for t in sec.get("highlights_pos", [])[:2]]
        left  += [(t, "neg")  for t in sec.get("highlights_neg", [])[:2]]
        right  = [(t, "warn") for t in sec.get("risks", [])[:2]]
        right += [(t, "act")  for t in sec.get("priorities", [])[:2]]
        if left or right:
            _two_column_block(pdf, "Key Highlights", left, "Risks & Priorities", right)
            pdf.ln(4)
        if sec.get("watch"):
            _watch_box(pdf, sec["watch"])

    # ── Per-slide analysis cards ──
    if business_slides:
        pdf.ln(2)
        _section_label(pdf, "Slide Analysis", rule=True)
        empty_count = len(slide_results) - len(business_slides)
        if empty_count:
            noun = "slide" if empty_count == 1 else "slides"
            verb = "was"   if empty_count == 1 else "were"
            pdf.set_font(FONT, "", 8)
            pdf.set_text_color(*CLR_MUTED)
            pdf.set_x(pdf.l_margin)
            pdf.cell(0, 5, f"{empty_count} {noun} contained no business data and {verb} omitted.",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        for r in business_slides:
            parsed = _parse_slide_insight(r["insight"], r["slide_num"])
            _slide_block(pdf, r["slide_num"], parsed)

    pdf.output(output_path)
    print(f"[PDF] Saved: {output_path}")
