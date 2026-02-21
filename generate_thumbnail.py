"""Generate SteuerPP app thumbnail (Concept B – Balkendiagramm)."""

from PIL import Image, ImageDraw, ImageFont

# ── Canvas ────────────────────────────────────────────────────────────────────
W, H = 512, 512
RADIUS = 40  # rounded-corner radius

# ── Brand colours (taken directly from the app) ───────────────────────────────
GREEN_DARK  = (46, 125, 50)    # #2e7d32  – header + primary bars
GREEN_MID   = (76, 175, 80)    # #4caf50  – bar highlight
ORANGE      = (245, 124, 0)    # #f57c00  – accent bar + € symbol
BG_WHITE    = (255, 255, 255)
BG_LIGHT    = (245, 248, 245)  # very faint green-white canvas
TEXT_DARK   = (33, 33, 33)
TEXT_MUTED  = (100, 110, 100)
AXIS_COLOR  = (200, 210, 200)
SHADOW      = (0, 0, 0, 30)

# ── Fonts ─────────────────────────────────────────────────────────────────────
FONT_SFNS  = "/System/Library/Fonts/SFNS.ttf"
FONT_HELVT = "/System/Library/Fonts/Helvetica.ttc"

def load_font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_SFNS, size)
    except Exception:
        return ImageFont.truetype(FONT_HELVT, size)

# ── Helper: rounded-rectangle mask ────────────────────────────────────────────
def rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)

# ── Build image ───────────────────────────────────────────────────────────────
img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 1. Background card (rounded, light)
rounded_rect(draw, (0, 0, W, H), RADIUS, BG_LIGHT)

# 2. Green header band (schmaler, gerade Unterkante)
HEADER_H = 105
rounded_rect(draw, (0, 0, W, HEADER_H + RADIUS), RADIUS, GREEN_DARK)
draw.rectangle([0, HEADER_H, W, HEADER_H + RADIUS], fill=GREEN_DARK)

# 3. "SteuerPP" title in header
font_title = load_font(58)
draw.text((38, 16), "SteuerPP", font=font_title, fill=BG_WHITE)

# 4. Subtitle line under title
font_sub = load_font(18)
draw.text((40, 76), "Steuerrechner für Portfolio Performance", font=font_sub, fill=(180, 230, 180))

# 6. Bar chart
CHART_LEFT   = 50
CHART_RIGHT  = W - 50
CHART_BOTTOM = 390
CHART_TOP    = 165

bar_data = [
    ("ETF 1", 0.40, GREEN_MID),
    ("ETF 2", 0.60, GREEN_MID),
    ("ETF 3", 0.55, GREEN_MID),
    ("ETF 4", 0.80, GREEN_MID),
    ("ETF 5", 1.00, ORANGE),   # tallest bar in orange (accent)
]

n_bars   = len(bar_data)
gap      = 14
total_w  = CHART_RIGHT - CHART_LEFT
bar_w    = (total_w - gap * (n_bars - 1)) // n_bars
max_h    = CHART_BOTTOM - CHART_TOP

# x-axis
draw.line([(CHART_LEFT - 6, CHART_BOTTOM), (CHART_RIGHT + 6, CHART_BOTTOM)],
          fill=AXIS_COLOR, width=2)

for i, (label, ratio, color) in enumerate(bar_data):
    bx0 = CHART_LEFT + i * (bar_w + gap)
    bx1 = bx0 + bar_w
    bh  = int(ratio * max_h)
    by0 = CHART_BOTTOM - bh
    by1 = CHART_BOTTOM

    # bar shadow (subtle)
    draw.rectangle([bx0 + 3, by0 + 3, bx1 + 3, by1], fill=(0, 0, 0, 18))
    # bar body
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=6, fill=color)

    # small top highlight
    draw.rounded_rectangle([bx0, by0, bx1, by0 + 8], radius=6,
                           fill=tuple(min(c + 50, 255) for c in color))

# 7. Euro symbol – orange, top-right of chart area
font_euro = load_font(56)
draw.text((CHART_RIGHT - 52, CHART_TOP - 6), "€", font=font_euro, fill=ORANGE)

# 8. Bottom accent bar – rounded bottom corners (matching card), straight top edge
FOOTER_BAR_Y = H - 72
rounded_rect(draw, (0, FOOTER_BAR_Y, W, H), RADIUS, GREEN_DARK)          # rounds all 4
draw.rectangle([0, FOOTER_BAR_Y, W, FOOTER_BAR_Y + RADIUS], fill=GREEN_DARK)  # flatten top

# 9. Footer label – drawn AFTER bar, in white, vertically centred inside it
font_footer = load_font(20)
footer_text = "Kapitalertragssteuer  ·  FIFO  ·  Vorabpauschale"
bbox = font_footer.getbbox(footer_text)
text_w = bbox[2] - bbox[0]
text_x = (W - text_w) // 2          # horizontally centred
text_y = FOOTER_BAR_Y + (H - FOOTER_BAR_Y - 24) // 2  # vertically centred
draw.text((text_x, text_y), footer_text, font=font_footer, fill=(200, 235, 200))

# ── Save ──────────────────────────────────────────────────────────────────────
out = "assets/thumbnail.png"
import os; os.makedirs("assets", exist_ok=True)
img.save(out, "PNG")
print(f"Saved → {out}  ({W}×{H} px)")
