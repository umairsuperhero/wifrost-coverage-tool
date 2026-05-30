import datetime
from io import BytesIO
from typing import Dict, Any, List, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, Image, PageBreak)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, Line, PolyLine, String, Polygon, Circle
from terrain import get_profile, get_elevation
from propagation import compute_eirp

# ── Palette ────────────────────────────────────────────────────────────────────
C_NAVY     = colors.HexColor('#1B365D')
C_SLATE    = colors.HexColor('#6B778C')
C_DARK     = colors.HexColor('#172B4D')
C_OFF      = colors.HexColor('#F4F5F7')
C_BORDER   = colors.HexColor('#DFE1E6')
C_BLUE     = colors.HexColor('#2563EB')

C_PASS_BG  = colors.HexColor('#D1FAE5')
C_PASS_TX  = colors.HexColor('#065F46')
C_WARN_BG  = colors.HexColor('#FEF3C7')
C_WARN_TX  = colors.HexColor('#92400E')
C_FAIL_BG  = colors.HexColor('#FEE2E2')
C_FAIL_TX  = colors.HexColor('#991B1B')

C_EXC      = colors.HexColor('#2ecc71')   # map: excellent
C_GOOD     = colors.HexColor('#27ae60')   # map: good
C_MARG     = colors.HexColor('#f1c40f')   # map: marginal
C_NONE     = colors.HexColor('#94A3B8')   # map: no coverage

W = letter[0]   # 612 pts


# ── Style factory ──────────────────────────────────────────────────────────────
_base = getSampleStyleSheet()

def _s(name, size=9, color=None, bold=False, align=0, leading=None, space_after=0):
    return ParagraphStyle(
        name,
        parent=_base['Normal'],
        fontName='Helvetica-Bold' if bold else 'Helvetica',
        fontSize=size,
        leading=leading or round(size * 1.45),
        textColor=color or C_DARK,
        alignment=align,
        spaceAfter=space_after,
    )


# ── Page decorations ───────────────────────────────────────────────────────────
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self.draw_page_number(page_count)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont('Helvetica', 7)
        self.setFillColor(C_SLATE)
        self.drawRightString(W - 36, 32, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def _draw_chrome(canvas, doc):
    canvas.saveState()

    # Header bar
    canvas.setFillColor(C_NAVY)
    canvas.rect(0, letter[1] - 34, W, 34, fill=1, stroke=0)
    canvas.setFont('Helvetica-Bold', 9)
    canvas.setFillColor(colors.white)
    canvas.drawString(36, letter[1] - 21, "WiFrost  ·  TVWS RF Coverage Analysis")
    canvas.setFont('Helvetica', 9)
    canvas.drawRightString(W - 36, letter[1] - 21,
                           datetime.date.today().strftime('%B %d, %Y'))

    # Footer
    canvas.setStrokeColor(C_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(36, 44, W - 36, 44)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(C_SLATE)
    canvas.drawString(36, 32,
        "Model: Okumura-Hata + SRTM terrain. For pre-sales planning only. "
        "Field validation recommended before deployment.")

    canvas.restoreState()


# ── Legend helper ──────────────────────────────────────────────────────────────
def _legend():
    """Returns a Table row showing signal quality colour swatches + labels."""
    items = [
        (C_EXC,  "Excellent  ≥ −65 dBm"),
        (C_GOOD, "Good  −65 to −75"),
        (C_MARG, "Marginal  −75 to −85"),
        (C_NONE, "Below threshold"),
    ]
    cells, widths = [], []
    for c, lbl in items:
        cells.append("")           # swatch
        cells.append(f" {lbl}  ") # label
        widths += [11, 110]

    tbl = Table([cells], colWidths=widths, rowHeights=[11])
    st = []
    for i, (c, _) in enumerate(items):
        ci = i * 2
        st += [
            ('BACKGROUND', (ci, 0), (ci, 0), c),
            ('FONTSIZE',   (ci+1, 0), (ci+1, 0), 7.5),
            ('TEXTCOLOR',  (ci+1, 0), (ci+1, 0), C_DARK),
            ('VALIGN',     (ci, 0),   (ci+1, 0), 'MIDDLE'),
            ('LEFTPADDING',  (ci, 0), (ci, 0), 0),
            ('RIGHTPADDING', (ci, 0), (ci, 0), 0),
        ]
    tbl.setStyle(TableStyle(st))
    return tbl


# ── Margin colour helper ───────────────────────────────────────────────────────
def _mc(margin_db):
    if margin_db >= 10.0:
        return C_PASS_BG, C_PASS_TX
    if margin_db >= 3.0:
        return C_WARN_BG, C_WARN_TX
    return C_FAIL_BG, C_FAIL_TX


def build_pdf_terrain_profile_drawing(
    terrain_grid: Any,
    bts_lat: float, bts_lon: float, bts_height_m: float,
    rx_lat: float, rx_lon: float, rx_height_m: float,
    f_mhz: float, cpe_name: str = "CPE", n_points: int = 100
) -> Drawing:
    """Returns a ReportLab vector Drawing of the terrain cross-section with Fresnel zones."""
    import math

    # Get profile data
    profile = get_profile(terrain_grid, bts_lat, bts_lon, rx_lat, rx_lon, n_points)
    if not profile:
        return Drawing(540, 160)

    distances = [p[0] for p in profile]
    elevations = [p[1] for p in profile]
    total_dist = distances[-1] if distances[-1] > 0 else 1.0

    bts_elev = get_elevation(terrain_grid, bts_lat, bts_lon)
    rx_elev = get_elevation(terrain_grid, rx_lat, rx_lon)
    H_tx = bts_elev + bts_height_m
    H_rx = rx_elev + rx_height_m

    los_heights = [H_tx + (d / total_dist) * (H_rx - H_tx) for d in distances]

    fresnel_upper, fresnel_lower = [], []
    for d in distances:
        d2 = total_dist - d
        if d > 0 and d2 > 0 and f_mhz > 0:
            r1 = 17.3 * math.sqrt((d * d2) / (f_mhz * total_dist))
            idx = distances.index(d)
            fresnel_upper.append(los_heights[idx] + r1)
            fresnel_lower.append(los_heights[idx] - r1)
        else:
            los_h = los_heights[distances.index(d)]
            fresnel_upper.append(los_h)
            fresnel_lower.append(los_h)

    # Scaling calculations for drawing
    dw, dh = 540.0, 170.0
    pad_left, pad_right, pad_top, pad_bottom = 45.0, 15.0, 15.0, 25.0
    plot_w = dw - pad_left - pad_right
    plot_h = dh - pad_top - pad_bottom

    # Find elevation bounds
    all_y = elevations + [H_tx, H_rx] + fresnel_upper + fresnel_lower
    min_y = max(0.0, min(all_y) - 10.0)
    max_y = max(all_y) + 10.0
    y_span = max_y - min_y if max_y > min_y else 10.0

    def to_plot_coords(dist, elev):
        x = pad_left + (dist / total_dist) * plot_w
        y = pad_bottom + ((elev - min_y) / y_span) * plot_h
        return x, y

    drawing = Drawing(dw, dh)

    # Background Box
    drawing.add(Rect(pad_left, pad_bottom, plot_w, plot_h, fillColor=colors.HexColor('#F8F9FA'), strokeColor=colors.HexColor('#E5E7EB'), strokeWidth=1))

    # Grid lines (elevations)
    n_ticks = 5
    for i in range(n_ticks):
        elev_tick = min_y + (i / (n_ticks - 1)) * y_span
        _, y_pos = to_plot_coords(0, elev_tick)
        drawing.add(Line(pad_left, y_pos, dw - pad_right, y_pos, strokeColor=colors.HexColor('#E5E7EB'), strokeWidth=0.5))
        drawing.add(String(pad_left - 8, y_pos - 3, f"{elev_tick:.0f}m", fontName='Helvetica', fontSize=7, textAnchor='end', fillColor=colors.HexColor('#4B5563')))

    # Grid lines (distances)
    for i in range(5):
        dist_tick = (i / 4) * total_dist
        x_pos, _ = to_plot_coords(dist_tick, min_y)
        drawing.add(Line(x_pos, pad_bottom, x_pos, dh - pad_top, strokeColor=colors.HexColor('#E5E7EB'), strokeWidth=0.5))
        drawing.add(String(x_pos, pad_bottom - 10, f"{dist_tick:.1f} km", fontName='Helvetica', fontSize=7, textAnchor='middle', fillColor=colors.HexColor('#4B5563')))

    # Draw 1st Fresnel zone band (sky blue)
    fresnel_points = []
    for d, fu in zip(distances, fresnel_upper):
        fresnel_points.extend(to_plot_coords(d, fu))
    for d, fl in zip(reversed(distances), reversed(fresnel_lower)):
        fresnel_points.extend(to_plot_coords(d, fl))
    drawing.add(Polygon(fresnel_points, fillColor=colors.HexColor('#E0F2FE'), strokeColor=colors.HexColor('#BAE6FD'), strokeWidth=0.5))

    # Draw Terrain (filled beige)
    terrain_points = []
    x_start, y_base = to_plot_coords(0, min_y)
    terrain_points.extend([x_start, y_base])
    for d, elev in zip(distances, elevations):
        terrain_points.extend(to_plot_coords(d, elev))
    x_end, _ = to_plot_coords(total_dist, min_y)
    terrain_points.extend([x_end, y_base])
    drawing.add(Polygon(terrain_points, fillColor=colors.HexColor('#EFEAE4'), strokeColor=colors.HexColor('#8B5A2B'), strokeWidth=1.5))

    # Line of Sight line (dashed royal blue)
    x_tx, y_tx = to_plot_coords(0, H_tx)
    x_rx, y_rx = to_plot_coords(total_dist, H_rx)
    drawing.add(Line(x_tx, y_tx, x_rx, y_rx, strokeColor=colors.HexColor('#2563EB'), strokeWidth=1.5, strokeDashArray=[4, 4]))

    # BTS antenna pole & emitter
    x_bts_g, y_bts_g = to_plot_coords(0, bts_elev)
    drawing.add(Line(x_bts_g, y_bts_g, x_tx, y_tx, strokeColor=colors.HexColor('#1E293B'), strokeWidth=2))
    drawing.add(Circle(x_tx, y_tx, 3.5, fillColor=colors.HexColor('#DC2626'), strokeColor=colors.HexColor('#1E293B'), strokeWidth=0.5))

    # CPE antenna pole & receiver
    x_cpe_g, y_cpe_g = to_plot_coords(total_dist, rx_elev)
    drawing.add(Line(x_cpe_g, y_cpe_g, x_rx, y_rx, strokeColor=colors.HexColor('#1E293B'), strokeWidth=2))
    drawing.add(Circle(x_rx, y_rx, 3.5, fillColor=colors.HexColor('#10B981'), strokeColor=colors.HexColor('#1E293B'), strokeWidth=0.5))

    # Labels
    drawing.add(String(x_tx + 6, y_tx + 5, "BTS", fontName='Helvetica-Bold', fontSize=8, fillColor=colors.HexColor('#1E293B')))
    drawing.add(String(x_rx - 6, y_rx + 5, cpe_name, fontName='Helvetica-Bold', fontSize=8, textAnchor='end', fillColor=colors.HexColor('#1E293B')))

    return drawing


# ── Main entry point ───────────────────────────────────────────────────────────
def generate_pdf_report(
    output_stream: BytesIO,
    project_name: str,
    prepared_by: str,
    coverage_grid: Any,
    equipment_bts: Any,
    equipment_cpe: Any,
    model_name: str,
    environment: str,
    conclusion_text: str,
    # enriched data from the API
    stats: Optional[Dict[str, Any]] = None,
    three_scenarios: Optional[Dict[str, Any]] = None,
    cpe_results: Optional[List[Dict[str, Any]]] = None,
    frequency_mhz: float = 600.0,
    # legacy / technical-page values
    edge_loss_db: float = 0.0,
    edge_rssi_dbm: float = 0.0,
    edge_margin_db: float = 0.0,
    system_margin_db: float = 18.0,
    shadowing_margin_90_db: float = 0.0,
    clutter_db: float = 0.0,
    diffraction_db: float = 0.0,
    edge_rssi_realistic_dbm: Optional[float] = None,
    edge_rssi_pessimistic_dbm: Optional[float] = None,
    all_sites_comparison: Optional[List[Dict[str, Any]]] = None,
    terrain_grid: Optional[Any] = None,
) -> None:

    if stats is None:
        stats = coverage_grid.stats

    doc = SimpleDocTemplate(
        output_stream,
        pagesize=letter,
        leftMargin=36, rightMargin=36,
        topMargin=56, bottomMargin=64,
    )

    story = []

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 1 — Business overview
    # ══════════════════════════════════════════════════════════════════════════

    # Project title + meta line
    story.append(Paragraph("Coverage Analysis Report", _s('T', 20, C_NAVY, bold=True, leading=24)))
    story.append(Paragraph(
        f"<b>Project:</b> {project_name} &nbsp;|&nbsp; "
        f"<b>Frequency:</b> {frequency_mhz:.0f} MHz &nbsp;|&nbsp; "
        f"<b>Model:</b> {model_name} &nbsp;|&nbsp; "
        f"<b>Environment:</b> {environment.replace('_', ' ').title()} &nbsp;|&nbsp; "
        f"<b>Prepared by:</b> {prepared_by}",
        _s('Meta', 8, C_SLATE, leading=12),
    ))
    story.append(Spacer(1, 10))

    # Coverage map (preserving aspect ratio)
    from heatmap import coverage_to_image
    rssi_arr = coverage_grid.rssi_array
    nrows_grid, ncols_grid = rssi_arr.shape
    aspect = nrows_grid / ncols_grid
    map_w = 390.0
    map_h = round(map_w * aspect)
    if map_h > 310.0:
        map_h = 310.0
        map_w = round(map_h / aspect)
    map_img = Image(BytesIO(coverage_to_image(coverage_grid)), width=map_w, height=map_h)
    map_img.hAlign = 'LEFT'

    # KPI cards (right column)
    def _kpi(label, value):
        return [
            [Paragraph(label, _s(f'KL{label}', 7, C_SLATE, bold=True, align=1))],
            [Paragraph(value,  _s(f'KV{label}', 17, C_NAVY, bold=True, align=1, leading=21))],
        ]

    kpi_rows = (
        _kpi("COVERAGE AREA",       f"{stats.get('coverage_pct', 0)}%")        + [[Spacer(1,5)]] +
        _kpi("GOOD SIGNAL (≥−75)",  f"{stats.get('good_pct', 0)}%")            + [[Spacer(1,5)]] +
        _kpi("AVG RSSI (COVERED)",  f"{stats.get('avg_rssi', 0)} dBm")         + [[Spacer(1,5)]] +
        _kpi("MAX RANGE",           f"{stats.get('max_range_km', 0)} km")      + [[Spacer(1,5)]] +
        _kpi("STUDY AREA",          f"{stats.get('total_area_km2', 0)} km²")
    )
    kpi_tbl = Table(kpi_rows, colWidths=[128])
    _kpi_bg = []
    for row_idx in [0, 3, 6, 9, 12]:   # label+value pairs (spacers at 2,5,8,11)
        _kpi_bg += [
            ('BACKGROUND', (0, row_idx),   (0, row_idx+1), C_OFF),
            ('BOX',        (0, row_idx),   (0, row_idx+1), 0.5, C_BORDER),
            ('TOPPADDING', (0, row_idx),   (0, row_idx+1), 3),
            ('BOTTOMPADDING', (0, row_idx),(0, row_idx+1), 3),
        ]
    kpi_tbl.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER')] + _kpi_bg))

    map_kpi = Table([[map_img, kpi_tbl]], colWidths=[400, 136])
    map_kpi.setStyle(TableStyle([
        ('VALIGN', (0,0),(-1,-1), 'TOP'),
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('RIGHTPADDING', (0,0),(-1,-1), 0),
    ]))
    story.append(map_kpi)
    story.append(Spacer(1, 5))
    story.append(_legend())
    story.append(Spacer(1, 12))

    # Scenario comparison cards
    if three_scenarios:
        story.append(Paragraph("Coverage Scenario Comparison",
                               _s('SH', 11, C_NAVY, bold=True, space_after=4)))

        sc = three_scenarios
        scenarios = [
            ("BEST CASE",      colors.HexColor('#16A34A'), sc.get('best', {})),
            ("REALISTIC",      C_BLUE,                     sc.get('realistic', {})),
            ("CONSERVATIVE",   colors.HexColor('#D97706'), sc.get('conservative', {})),
        ]

        def _sc_col(title, hdr_color, data):
            rows = [[Paragraph(title, _s(f'SCH{title}', 8, colors.white, bold=True, align=1))]]
            metrics = [
                ("COVERAGE AREA", f"{data.get('coverage_pct', 0)}%"),
                ("GOOD SIGNAL",   f"{data.get('good_pct', 0)}%"),
                ("AVG RSSI",      f"{data.get('avg_rssi', 0)} dBm"),
            ]
            for i, (lbl, val) in enumerate(metrics):
                bg = C_OFF if i % 2 == 0 else colors.white
                rows.append([Paragraph(lbl, _s(f'SL{title}{i}', 7, C_SLATE, align=1))])
                rows.append([Paragraph(val, _s(f'SV{title}{i}', 13, C_NAVY, bold=True, align=1, leading=17))])
            t = Table(rows, colWidths=[172])
            st = [
                ('BACKGROUND',    (0,0), (-1,0), hdr_color),
                ('TOPPADDING',    (0,0), (-1,0), 6),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ]
            for j in range(1, len(rows), 2):
                bg = C_OFF if ((j-1)//2) % 2 == 0 else colors.white
                st += [
                    ('BACKGROUND',    (0,j), (-1,j+1), bg),
                    ('BOX',           (0,j), (-1,j+1), 0.5, C_BORDER),
                    ('TOPPADDING',    (0,j), (-1,j+1), 3),
                    ('BOTTOMPADDING', (0,j), (-1,j+1), 3),
                ]
            t.setStyle(TableStyle(st))
            return t

        sc_cols = [_sc_col(t, c, d) for t, c, d in scenarios]
        sc_outer = Table([[sc_cols[0], Spacer(6,1), sc_cols[1], Spacer(6,1), sc_cols[2]]],
                         colWidths=[172, 6, 172, 6, 172])
        sc_outer.setStyle(TableStyle([
            ('VALIGN',       (0,0),(-1,-1), 'TOP'),
            ('LEFTPADDING',  (0,0),(-1,-1), 0),
            ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ]))
        story.append(sc_outer)
        story.append(Spacer(1, 12))

    # Executive summary
    story.append(Paragraph("Executive Summary",
                            _s('ESH', 11, C_NAVY, bold=True, space_after=4)))
    es_tbl = Table([[Paragraph(conclusion_text,
                               _s('ES', 9, C_DARK, leading=14))]],
                   colWidths=[540])
    es_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), C_OFF),
        ('BOX',           (0,0),(-1,-1), 1, C_NAVY),
        ('TOPPADDING',    (0,0),(-1,-1), 10),
        ('BOTTOMPADDING', (0,0),(-1,-1), 10),
        ('LEFTPADDING',   (0,0),(-1,-1), 14),
        ('RIGHTPADDING',  (0,0),(-1,-1), 14),
    ]))
    story.append(es_tbl)

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 2 — CPE site analysis
    # ══════════════════════════════════════════════════════════════════════════
    if cpe_results:
        story.append(PageBreak())
        story.append(Paragraph("Client Site Coverage Analysis",
                               _s('P2T', 18, C_NAVY, bold=True, leading=22)))

        pass_count = sum(1 for c in cpe_results if c.get('margin_db', -999) >= 3.0)
        total = len(cpe_results)
        story.append(Paragraph(
            f"<b>{pass_count} of {total}</b> client sites achieve reliable coverage "
            f"(link margin ≥ 3 dB). &nbsp; "
            f"<font color='#065F46'><b>PASS</b></font> ≥ 10 dB margin &nbsp; · &nbsp; "
            f"<font color='#92400E'><b>MARGINAL</b></font> 3–10 dB &nbsp; · &nbsp; "
            f"<font color='#991B1B'><b>FAIL</b></font> &lt; 3 dB",
            _s('P2S', 9, C_DARK, leading=14),
        ))
        story.append(Spacer(1, 10))

        # Table
        col_w = [155, 62, 62, 70, 82, 109]
        hdr = [
            Paragraph("<b>Site Name</b>",     _s('CH0', 8, colors.white, bold=True)),
            Paragraph("<b>Dist (km)</b>",     _s('CH1', 8, colors.white, bold=True, align=1)),
            Paragraph("<b>Elevation (m)</b>", _s('CH2', 8, colors.white, bold=True, align=1)),
            Paragraph("<b>RSSI (dBm)</b>",    _s('CH3', 8, colors.white, bold=True, align=1)),
            Paragraph("<b>Link Margin</b>",   _s('CH4', 8, colors.white, bold=True, align=1)),
            Paragraph("<b>Status</b>",        _s('CH5', 8, colors.white, bold=True, align=1)),
        ]
        rows = [hdr]
        row_styles = [
            ('BACKGROUND',    (0,0), (-1,0), C_NAVY),
            ('TOPPADDING',    (0,0), (-1,0), 6),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('GRID',          (0,0), (-1,-1), 0.5, C_BORDER),
            ('TOPPADDING',    (0,1), (-1,-1), 4),
            ('BOTTOMPADDING', (0,1), (-1,-1), 4),
        ]

        for i, cpe in enumerate(cpe_results):
            margin = cpe.get('margin_db', -999)
            rssi   = cpe.get('rssi_dbm', -999)
            bg, tx = _mc(margin)

            raw = cpe.get('status', '')
            if margin >= 10.0:
                status_str, s_col = 'PASS',     C_PASS_TX
            elif margin >= 3.0:
                status_str, s_col = 'MARGINAL', C_WARN_TX
            else:
                status_str, s_col = 'FAIL',     C_FAIL_TX

            row = [
                Paragraph(cpe.get('name', ''), _s(f'RN{i}', 8.5)),
                Paragraph(f"{cpe.get('distance_km', 0):.2f}",
                          _s(f'RD{i}', 8.5, align=1)),
                Paragraph(f"{cpe.get('elevation_m', 0):.0f}",
                          _s(f'RE{i}', 8.5, align=1)),
                Paragraph(f"{rssi:.1f}",
                          _s(f'RR{i}', 8.5, align=1)),
                Paragraph(f"{margin:+.1f} dB",
                          _s(f'RM{i}', 8.5, bold=True, align=1)),
                Paragraph(status_str,
                          _s(f'RS{i}', 8.5, s_col, bold=True, align=1)),
            ]
            rows.append(row)
            # Colour the RSSI + margin + status columns
            row_styles.append(('BACKGROUND', (3, i+1), (5, i+1), bg))

        cpe_tbl = Table(rows, colWidths=col_w)
        cpe_tbl.setStyle(TableStyle(row_styles))
        story.append(cpe_tbl)

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 3 — Technical: link budget + simulation params
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("Technical: System Link Budget",
                           _s('P3T', 18, C_NAVY, bold=True, leading=22)))
    story.append(Paragraph(
        "RF link budget at the coverage-area edge. All signal levels in dBm.",
        _s('P3S', 8.5, C_SLATE, leading=12),
    ))
    story.append(Spacer(1, 10))

    eirp_bts = compute_eirp(equipment_bts.tx_power_dbm,
                             equipment_bts.antenna_gain_dbi,
                             equipment_bts.cable_loss_db)
    eirp_cpe = compute_eirp(equipment_cpe.tx_power_dbm,
                             equipment_cpe.antenna_gain_dbi,
                             equipment_cpe.cable_loss_db)

    real_rssi = edge_rssi_realistic_dbm if edge_rssi_realistic_dbm is not None else edge_rssi_dbm
    # Pessimistic RSSI: add clutter and additional 2 dB for interference/aging margin
    _INTERFERENCE_AGING_DB = 2.0
    pess_rssi = (edge_rssi_pessimistic_dbm if edge_rssi_pessimistic_dbm is not None
                 else edge_rssi_dbm - clutter_db - _INTERFERENCE_AGING_DB)
    real_margin = real_rssi - equipment_cpe.receiver_sensitivity_dbm
    pess_margin = pess_rssi - equipment_cpe.receiver_sensitivity_dbm

    r_bg, _ = _mc(real_margin)
    p_bg, _ = _mc(pess_margin)

    def _lr(param, bts_v, cpe_v, note, bold=False):
        s_p = _s(f'LBP{param}', 8.5, bold=bold)
        s_v = _s(f'LBV{param}', 8.5, bold=bold, align=1)
        s_n = _s(f'LBN{param}', 8, C_SLATE)
        return [Paragraph(f"<b>{param}</b>" if bold else param, s_p),
                Paragraph(f"<b>{bts_v}</b>" if bold else str(bts_v), s_v),
                Paragraph(f"<b>{cpe_v}</b>" if bold else str(cpe_v), s_v),
                Paragraph(note, s_n)]

    lb_rows = [
        [Paragraph("<b>Parameter</b>",   _s('LH0', 8.5, colors.white, bold=True)),
         Paragraph("<b>BTS (TX)</b>",    _s('LH1', 8.5, colors.white, bold=True, align=1)),
         Paragraph("<b>CPE (RX)</b>",    _s('LH2', 8.5, colors.white, bold=True, align=1)),
         Paragraph("<b>Notes</b>",       _s('LH3', 8.5, colors.white, bold=True))],
        _lr("Model",
            f"{equipment_bts.manufacturer} {equipment_bts.model_name}",
            f"{equipment_cpe.manufacturer} {equipment_cpe.model_name}",
            "TVWS equipment"),
        _lr("TX Power",
            f"{equipment_bts.tx_power_dbm} dBm",
            f"{equipment_cpe.tx_power_dbm} dBm",
            "Transmitter output"),
        _lr("Antenna Gain",
            f"{equipment_bts.antenna_gain_dbi} dBi",
            f"{equipment_cpe.antenna_gain_dbi} dBi",
            "Antenna gain"),
        _lr("Cable & Connector Loss",
            f"{equipment_bts.cable_loss_db} dB",
            f"{equipment_cpe.cable_loss_db} dB",
            "Feeder + connectors"),
        _lr("EIRP",
            f"{eirp_bts:.1f} dBm",
            f"{eirp_cpe:.1f} dBm",
            "TX Power + Gain − Cable Loss", bold=True),
        _lr("Path Loss (base)",
            "—", f"{edge_loss_db:.1f} dB",
            f"{model_name}  ({environment})"),
        _lr("Terrain Diffraction",
            "—", f"{diffraction_db:.1f} dB",
            "Deygout multi-knife-edge (≤ 30 dB)"),
        _lr("Clutter Loss",
            "—", f"{clutter_db:.1f} dB",
            f"Land-use clutter  ({environment})"),
        _lr("Shadowing Margin",
            "—", f"{shadowing_margin_90_db:.1f} dB",
            "Log-normal, 90 % location probability"),
        _lr("System Margin",
            "—", f"{system_margin_db:.1f} dB",
            "Fading + interference + hardware aging"),
        _lr("RSSI — Optimistic",
            "—", f"{edge_rssi_dbm:.1f} dBm",
            "Base path loss + diffraction only", bold=True),
        _lr("RSSI — Realistic",
            "—", f"{real_rssi:.1f} dBm",
            "Adds shadowing margin + system margin", bold=True),
        _lr("Rx Sensitivity",
            f"{equipment_bts.receiver_sensitivity_dbm:.1f} dBm",
            f"{equipment_cpe.receiver_sensitivity_dbm:.1f} dBm",
            "Minimum signal for demodulation"),
        _lr("Link Margin (Realistic)",
            "—", f"{real_margin:+.1f} dB",
            "Target ≥ +3 dB  (green ≥ 10, amber 3–10, red < 3)", bold=True),
        _lr("Link Margin (Pessimistic)",
            "—", f"{pess_margin:+.1f} dB",
            "Adds clutter + 95 % shadowing margin", bold=True),
    ]

    lb_tbl = Table(lb_rows, colWidths=[162, 108, 108, 162])
    lb_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), C_NAVY),
        ('TOPPADDING',    (0,0), (-1,0), 6),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING',    (0,1), (-1,-1), 3),
        ('BOTTOMPADDING', (0,1), (-1,-1), 3),
        ('GRID',          (0,0), (-1,-1), 0.5, C_BORDER),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, C_OFF]),
        # Colour the margin rows
        ('BACKGROUND',    (0, len(lb_rows)-2), (-1, len(lb_rows)-2), r_bg),
        ('BACKGROUND',    (0, len(lb_rows)-1), (-1, len(lb_rows)-1), p_bg),
    ]))
    story.append(lb_tbl)

    # Simulation parameters summary
    story.append(Spacer(1, 16))
    story.append(Paragraph("Simulation Parameters",
                           _s('SPH', 11, C_NAVY, bold=True, space_after=4)))
    param_rows = [
        [Paragraph("<b>Parameter</b>", _s('SPH0', 8.5, colors.white, bold=True)),
         Paragraph("<b>Value</b>",     _s('SPH1', 8.5, colors.white, bold=True))],
        ["Frequency",          f"{frequency_mhz:.0f} MHz"],
        ["Propagation model",  model_name],
        ["Environment",        environment.replace('_', ' ').title()],
        ["BTS antenna height", f"{equipment_bts.antenna_height_default_m} m"],
        ["CPE antenna height", f"{equipment_cpe.antenna_height_default_m} m"],
        ["System margin",      f"{system_margin_db} dB"],
        ["Shadowing std dev",  f"{4.0 if 'open' in environment else (6.0 if 'suburban' in environment else 8.0)} dB"],
    ]
    for i in range(1, len(param_rows)):
        param_rows[i] = [Paragraph(str(param_rows[i][0]), _s(f'PR{i}0', 8.5)),
                         Paragraph(str(param_rows[i][1]), _s(f'PR{i}1', 8.5))]

    param_tbl = Table(param_rows, colWidths=[200, 340])
    param_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), C_NAVY),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('GRID',          (0,0), (-1,-1), 0.5, C_BORDER),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, C_OFF]),
    ]))
    story.append(param_tbl)

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 4 — Terrain Elevation Profile (between BTS and worst CPE / edge)
    # ══════════════════════════════════════════════════════════════════════════
    if terrain_grid and not terrain_grid.is_flat:
        story.append(PageBreak())
        story.append(Paragraph("Terrain Elevation Profile Analysis",
                               _s('P4T', 18, C_NAVY, bold=True, leading=22)))
        
        # Decide which end point to use for the cross-section
        rx_name = "CPE (Cell Edge)"
        # Default to 45 degree NE cell edge point
        edge_dist_km = max(0.5, stats.get("max_range_km", 5.0))
        import math as _math
        edge_bearing_rad = _math.radians(45.0)
        rx_lat = coverage_grid.bts_site.latitude + (edge_dist_km / 111.32) * _math.cos(edge_bearing_rad)
        rx_lon = coverage_grid.bts_site.longitude + (edge_dist_km / (111.32 * _math.cos(_math.radians(coverage_grid.bts_site.latitude)))) * _math.sin(edge_bearing_rad)
        
        # If there are CPEs, choose the worst client site (lowest link margin) to analyze
        if cpe_results and len(cpe_results) > 0:
            sorted_cpe = sorted(cpe_results, key=lambda x: x.get('margin_db', 999))
            worst_cpe = sorted_cpe[0]
            rx_name = worst_cpe.get('name', 'CPE')
            rx_lat = worst_cpe.get('lat', rx_lat)
            rx_lon = worst_cpe.get('lon', rx_lon)
            
        story.append(Paragraph(
            f"Cross-section showing 1st Fresnel zone clearance at {frequency_mhz:.0f} MHz between BTS and <b>{rx_name}</b>.",
            _s('P4S', 9, C_DARK, leading=14),
        ))
        story.append(Spacer(1, 10))
        
        # Create and add the vector profile drawing
        profile_drawing = build_pdf_terrain_profile_drawing(
            terrain_grid=terrain_grid,
            bts_lat=coverage_grid.bts_site.latitude,
            bts_lon=coverage_grid.bts_site.longitude,
            bts_height_m=equipment_bts.antenna_height_default_m,
            rx_lat=rx_lat,
            rx_lon=rx_lon,
            rx_height_m=equipment_cpe.antenna_height_default_m,
            f_mhz=frequency_mhz,
            cpe_name=rx_name
        )
        story.append(profile_drawing)
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            "<b>Interpretative Note:</b> The 1st Fresnel zone represents the RF energy cylinder between antennas. "
            "Obstacles penetrating this zone introduce diffraction attenuation. "
            "The shaded area indicates terrain elevation from global SRTM data.",
            _s('P4N', 8, C_SLATE, leading=12),
        ))

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 5 — Equipment Specifications & Methodology
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("Equipment Specifications & Assumptions",
                           _s('P5T', 18, C_NAVY, bold=True, leading=22)))
    story.append(Paragraph(
        "Standard TVWS network equipment specifications deployed in this simulation.",
        _s('P5S', 9, C_SLATE, leading=14),
    ))
    story.append(Spacer(1, 10))
    
    spec_headers = [
        Paragraph("<b>Specification</b>", _s('SHH0', 8.5, colors.white, bold=True)),
        Paragraph("<b>BTS (Base Station)</b>", _s('SHH1', 8.5, colors.white, bold=True)),
        Paragraph("<b>CPE (Customer Terminal)</b>", _s('SHH2', 8.5, colors.white, bold=True)),
        Paragraph("<b>Remarks</b>", _s('SHH3', 8.5, colors.white, bold=True))
    ]
    
    spec_rows = [
        spec_headers,
        [Paragraph("Equipment Model", _s('SP0', 8.5)),
         Paragraph("WiFrost LT100B", _s('SPV1', 8.5)),
         Paragraph("WiFrost LT100C", _s('SPV2', 8.5)),
         Paragraph("Standard TVWS family", _s('SPR3', 8.5))],
        [Paragraph("Frequency Range", _s('SP0', 8.5)),
         Paragraph(f"{equipment_bts.freq_min_mhz}–{equipment_bts.freq_max_mhz} MHz", _s('SPV1', 8.5)),
         Paragraph(f"{equipment_cpe.freq_min_mhz}–{equipment_cpe.freq_max_mhz} MHz", _s('SPV2', 8.5)),
         Paragraph("UHF TV White Space bands", _s('SPR3', 8.5))],
        [Paragraph("Maximum Tx Power", _s('SP0', 8.5)),
         Paragraph(f"{equipment_bts.tx_power_dbm} dBm", _s('SPV1', 8.5)),
         Paragraph(f"{equipment_cpe.tx_power_dbm} dBm", _s('SPV2', 8.5)),
         Paragraph("FCC/MinTIC certified limits", _s('SPR3', 8.5))],
        [Paragraph("Antenna Gain", _s('SP0', 8.5)),
         Paragraph(f"{equipment_bts.antenna_gain_dbi} dBi", _s('SPV1', 8.5)),
         Paragraph(f"{equipment_cpe.antenna_gain_dbi} dBi", _s('SPV2', 8.5)),
         Paragraph("BTS sector panel / CPE panel", _s('SPR3', 8.5))],
        [Paragraph("Cable & Connector Loss", _s('SP0', 8.5)),
         Paragraph(f"{equipment_bts.cable_loss_db} dB", _s('SPV1', 8.5)),
         Paragraph(f"{equipment_cpe.cable_loss_db} dB", _s('SPV2', 8.5)),
         Paragraph("Standard RF jumpers & pigtails", _s('SPR3', 8.5))],
        [Paragraph("Receiver Sensitivity", _s('SP0', 8.5)),
         Paragraph(f"{equipment_bts.receiver_sensitivity_dbm} dBm", _s('SPV1', 8.5)),
         Paragraph(f"{equipment_cpe.receiver_sensitivity_dbm} dBm", _s('SPV2', 8.5)),
         Paragraph("MCS0 threshold (minimum sync)", _s('SPR3', 8.5))],
        [Paragraph("Horizontal Beamwidth", _s('SP0', 8.5)),
         Paragraph(f"{getattr(equipment_bts, 'beamwidth_h_deg', 65.0)}° sector", _s('SPV1', 8.5)),
         Paragraph(f"{getattr(equipment_cpe, 'beamwidth_h_deg', 60.0)}° panel", _s('SPV2', 8.5)),
         Paragraph("Directional coverage pattern", _s('SPR3', 8.5))],
    ]
    
    spec_table = Table(spec_rows, colWidths=[140, 120, 120, 160])
    spec_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_NAVY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, C_OFF]),
    ]))
    story.append(spec_table)
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("<b>Model Methodology & Assumptions</b>",
                           _s('AssTitle', 10, C_NAVY, bold=True, space_after=4)))
    story.append(Paragraph(
        "1. <b>Empirical Propagation:</b> We employ the Okumura-Hata empirical path loss model, which is optimized for UHF frequencies. "
        "A location-based clutter attenuation offset is applied based on the land environment chosen (Urban, Suburban, Rural).<br/>"
        "2. <b>Terrain Profile Fading:</b> Knife-edge diffraction attenuation is modeled recursively using the Deygout algorithm (capped at 30 dB total attenuation). "
        "Terrain profiles are built dynamically from SRTM 30m resolution topographic maps.<br/>"
        "3. <b>Fading & Shadowing Margins:</b> Location probability is set to 90% (shadowing standard deviation is environment-dependent, typically 4–8 dB). "
        "An additional system margin (default 18 dB) is included to protect against multi-path fading, vegetation growth, and RF noise.<br/>"
        "4. <b>Pessimistic Scenario:</b> Incorporates a pessimistic clutter attenuation and a 95% location confidence margin, "
        "offering a conservative baseline for high-reliability links.",
        _s('AssContent', 8.5, C_DARK, leading=13)
    ))

    doc.build(story, onFirstPage=_draw_chrome, onLaterPages=_draw_chrome, canvasmaker=NumberedCanvas)
