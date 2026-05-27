import os
import datetime
from io import BytesIO
from typing import Dict, Any, List, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from propagation import compute_eirp


# Define palette colors
COLOR_PRIMARY = colors.HexColor('#1B365D')    # Deep Navy
COLOR_SECONDARY = colors.HexColor('#6B778C')  # Cool Slate Gray
COLOR_DARK = colors.HexColor('#172B4D')       # Charcoal
COLOR_LIGHT = colors.HexColor('#F4F5F7')      # Warm Off-White
COLOR_BORDER = colors.HexColor('#DFE1E6')     # Soft Gray Border

# Margin Colors
COLOR_PASS_BG = colors.HexColor('#D4EDDA')    # Light Green
COLOR_PASS_TEXT = colors.HexColor('#155724')  # Dark Green
COLOR_WARN_BG = colors.HexColor('#FFF3CD')    # Light Yellow
COLOR_WARN_TEXT = colors.HexColor('#856404')  # Dark Yellow
COLOR_FAIL_BG = colors.HexColor('#F8D7DA')    # Light Red
COLOR_FAIL_TEXT = colors.HexColor('#721C24')  # Dark Red

def draw_page_decorations(canvas, doc):
    """Draw header, footer, and borders on every page."""
    canvas.saveState()
    
    # Header
    canvas.setFont('Helvetica-Bold', 8)
    canvas.setFillColor(COLOR_PRIMARY)
    canvas.drawString(36, 755, "WIFROST TVWS COVERAGE ANALYSIS")
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(COLOR_SECONDARY)
    canvas.drawRightString(576, 755, f"Date generated: {datetime.date.today().strftime('%B %d, %Y')}")
    
    canvas.setStrokeColor(COLOR_BORDER)
    canvas.setLineWidth(0.75)
    canvas.line(36, 748, 576, 748)
    
    # Footer
    canvas.line(36, 50, 576, 50)
    canvas.drawString(36, 38, "Simulation based on Okumura-Hata + SRTM terrain. Results are indicative. Field survey recommended.")
    canvas.drawRightString(576, 38, f"Page {doc.page} of 2")
    
    canvas.restoreState()

def generate_pdf_report(output_stream: BytesIO,
                        project_name: str,
                        prepared_by: str,
                        coverage_grid: Any,
                        equipment_bts: Any,
                        equipment_cpe: Any,
                        model_name: str,
                        environment: str,
                        edge_loss_db: float,
                        edge_rssi_dbm: float,
                        edge_margin_db: float,
                        conclusion_text: str,
                        all_sites_comparison: Optional[List[Dict[str, Any]]] = None,
                        system_margin_db: float = 18.0,
                        shadowing_margin_90_db: float = 0.0,
                        clutter_db: float = 0.0,
                        diffraction_db: float = 0.0,
                        edge_rssi_realistic_dbm: Optional[float] = None,
                        edge_rssi_pessimistic_dbm: Optional[float] = None) -> None:
    """
    Generate a 2-page PDF report.
    - Page 1: Metadata, Coverage Map image, Stats Summary, Recommendation.
    - Page 2: Link Budget Table, Site Comparison Table, Footer.
    """
    # 1. Setup Document
    # Letter size: 612 x 792 points. Usable width: 540 points (left/right margin 36).
    doc = SimpleDocTemplate(
        output_stream,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=54,
        bottomMargin=65
    )
    
    # 2. Setup Styles
    styles = getSampleStyleSheet()
    
    # Custom Styles
    style_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=COLOR_PRIMARY
    )
    
    style_subtitle = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=COLOR_SECONDARY
    )
    
    style_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=COLOR_PRIMARY,
        spaceAfter=6
    )
    
    style_body = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=COLOR_DARK
    )
    
    style_body_bold = ParagraphStyle(
        'BodyBold',
        parent=style_body,
        fontName='Helvetica-Bold'
    )
    
    style_conclusion = ParagraphStyle(
        'Conclusion',
        parent=style_body,
        fontSize=9.5,
        leading=14,
        textColor=COLOR_DARK
    )
    
    style_stat_label = ParagraphStyle(
        'StatLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=COLOR_SECONDARY,
        alignment=1 # Center
    )
    
    style_stat_val = ParagraphStyle(
        'StatValue',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=COLOR_PRIMARY,
        alignment=1 # Center
    )
    
    story = []
    
    # ================= PAGE 1 =================
    
    # Header: Title + Logo Placeholder
    # Logo Table
    logo_data = [
        [
            Paragraph(f"<b>WiFrost RF Planning Report</b>", style_title),
            Table([["WIFROST LOGO"]], colWidths=[110], rowHeights=[35], 
                  style=TableStyle([
                      ('BACKGROUND', (0,0), (-1,-1), COLOR_PRIMARY),
                      ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
                      ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                      ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                      ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                      ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
                      ('FONTSIZE', (0,0), (-1,-1), 8),
                  ]))
        ]
    ]
    
    header_table = Table(logo_data, colWidths=[420, 120])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(header_table)
    
    # Metadata Block
    meta_text = f"<b>Project:</b> {project_name} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Prepared For:</b> WiFrost Reseller Network &nbsp;&nbsp;|&nbsp;&nbsp; <b>Prepared By:</b> {prepared_by}"
    story.append(Paragraph(meta_text, style_subtitle))
    story.append(Spacer(1, 10))
    
    # Generate static map PNG bytes
    from heatmap import coverage_to_image
    img_bytes = coverage_to_image(coverage_grid)
    img_flow = Image(BytesIO(img_bytes), width=420, height=315) # Maintain 4:3 aspect ratio
    img_flow.hAlign = 'CENTER'
    
    # Layout Map & Stats Side-by-Side
    # Left side: Map. Right side: KPI Stats Cards.
    stats = coverage_grid.stats
    
    stat_cards_data = [
        [Paragraph("COVERAGE AREA", style_stat_label)],
        [Paragraph(f"{stats['coverage_pct']}%", style_stat_val)],
        [Spacer(1, 5)],
        [Paragraph("GOOD SIGNAL", style_stat_label)],
        [Paragraph(f"{stats['good_pct']}%", style_stat_val)],
        [Spacer(1, 5)],
        [Paragraph("AVG SIGNAL (RSSI)", style_stat_label)],
        [Paragraph(f"{stats['avg_rssi']} dBm", style_stat_val)],
        [Spacer(1, 5)],
        [Paragraph("MAX RANGE", style_stat_label)],
        [Paragraph(f"{stats['max_range_km']} km", style_stat_val)]
    ]
    
    stats_table = Table(stat_cards_data, colWidths=[100])
    stats_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BACKGROUND', (0,0), (0,1), COLOR_LIGHT),
        ('BACKGROUND', (0,3), (0,4), COLOR_LIGHT),
        ('BACKGROUND', (0,6), (0,7), COLOR_LIGHT),
        ('BACKGROUND', (0,9), (0,10), COLOR_LIGHT),
        ('BOX', (0,0), (0,1), 0.5, COLOR_BORDER),
        ('BOX', (0,3), (0,4), 0.5, COLOR_BORDER),
        ('BOX', (0,6), (0,7), 0.5, COLOR_BORDER),
        ('BOX', (0,9), (0,10), 0.5, COLOR_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    
    # Place map and stats side-by-side
    layout_data = [
        [img_flow, stats_table]
    ]
    layout_table = Table(layout_data, colWidths=[430, 110])
    layout_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(layout_table)
    story.append(Spacer(1, 10))
    
    # Recommendation Box
    story.append(Paragraph("Executive Summary & Recommendation", style_heading))
    
    rec_box_data = [[
        Paragraph(conclusion_text, style_conclusion)
    ]]
    rec_table = Table(rec_box_data, colWidths=[540])
    rec_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, COLOR_PRIMARY),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(rec_table)
    
    # End of Page 1
    story.append(PageBreak())
    
    # ================= PAGE 2 =================
    
    story.append(Paragraph("System Link Budget Configuration", style_heading))
    story.append(Paragraph("This budget represents signal levels at the edge of the service area.", style_subtitle))
    story.append(Spacer(1, 8))
    
    # Determine Margin Colors based on realistic margin (green >10 dB, amber 3-10 dB, red <3 dB)
    margin_bg = COLOR_PASS_BG
    margin_text_col = COLOR_PASS_TEXT
    margin_status = "PASS (≥ +10 dB)"
    if edge_margin_db < 3.0:
        margin_bg = COLOR_FAIL_BG
        margin_text_col = COLOR_FAIL_TEXT
        margin_status = "FAIL — CRITICAL (< +3 dB)"
    elif edge_margin_db < 10.0:
        margin_bg = COLOR_WARN_BG
        margin_text_col = COLOR_WARN_TEXT
        margin_status = "MARGINAL (+3 to +10 dB)"
        
    style_pass_fail = ParagraphStyle(
        'PassFailStyle',
        parent=style_body,
        fontName='Helvetica-Bold',
        textColor=margin_text_col
    )
    
    eirp_bts = compute_eirp(equipment_bts.tx_power_dbm,
                             equipment_bts.antenna_gain_dbi,
                             equipment_bts.cable_loss_db)
    eirp_cpe = compute_eirp(equipment_cpe.tx_power_dbm,
                             equipment_cpe.antenna_gain_dbi,
                             equipment_cpe.cable_loss_db)

    # Realistic margin: edge_rssi_dbm already includes shadowing + system margin from caller
    # Pessimistic margin uses edge_rssi_pessimistic if provided
    realistic_rssi = edge_rssi_realistic_dbm if edge_rssi_realistic_dbm is not None else edge_rssi_dbm
    pessimistic_rssi = edge_rssi_pessimistic_dbm if edge_rssi_pessimistic_dbm is not None else (edge_rssi_dbm - clutter_db - 2.0)
    realistic_margin = realistic_rssi - equipment_cpe.receiver_sensitivity_dbm
    pessimistic_margin = pessimistic_rssi - equipment_cpe.receiver_sensitivity_dbm

    def _margin_color(m):
        if m >= 10.0:
            return COLOR_PASS_BG
        elif m >= 3.0:
            return COLOR_WARN_BG
        return COLOR_FAIL_BG

    link_budget_data = [
        [
            Paragraph("<b>Parameter</b>", style_body_bold),
            Paragraph("<b>Transmitter (BTS)</b>", style_body_bold),
            Paragraph("<b>Receiver (CPE)</b>", style_body_bold),
            Paragraph("<b>Notes</b>", style_body_bold)
        ],
        [
            Paragraph("Model & Manufacturer", style_body),
            Paragraph(f"{equipment_bts.manufacturer} {equipment_bts.model_name}", style_body),
            Paragraph(f"{equipment_cpe.manufacturer} {equipment_cpe.model_name}", style_body),
            Paragraph("TVWS equipment specs", style_body)
        ],
        [
            Paragraph("TX Power", style_body),
            Paragraph(f"{equipment_bts.tx_power_dbm} dBm", style_body),
            Paragraph(f"{equipment_cpe.tx_power_dbm} dBm", style_body),
            Paragraph("Transmitter output power", style_body)
        ],
        [
            Paragraph("Antenna Gain", style_body),
            Paragraph(f"{equipment_bts.antenna_gain_dbi} dBi", style_body),
            Paragraph(f"{equipment_cpe.antenna_gain_dbi} dBi", style_body),
            Paragraph("BTS sector panel / CPE integrated", style_body)
        ],
        [
            Paragraph("Cable & Connector Loss", style_body),
            Paragraph(f"{equipment_bts.cable_loss_db} dB", style_body),
            Paragraph(f"{equipment_cpe.cable_loss_db} dB", style_body),
            Paragraph("Coaxial jumper and connectors", style_body)
        ],
        [
            Paragraph("<b>EIRP</b>", style_body_bold),
            Paragraph(f"<b>{eirp_bts:.1f} dBm</b>", style_body_bold),
            Paragraph(f"<b>{eirp_cpe:.1f} dBm</b>", style_body_bold),
            Paragraph("TX Power + Gain − Cable Loss", style_body)
        ],
        [
            Paragraph("Free-Space Path Loss (base)", style_body),
            Paragraph("—", style_body),
            Paragraph(f"{edge_loss_db:.1f} dB", style_body),
            Paragraph(f"{model_name} ({environment})", style_body)
        ],
        [
            Paragraph("Terrain Diffraction Loss", style_body),
            Paragraph("—", style_body),
            Paragraph(f"{diffraction_db:.1f} dB", style_body),
            Paragraph("Deygout multi-knife-edge (≤30 dB)", style_body)
        ],
        [
            Paragraph("Environment Clutter Loss", style_body),
            Paragraph("—", style_body),
            Paragraph(f"{clutter_db:.1f} dB", style_body),
            Paragraph(f"Terrain/land-use correction ({environment})", style_body)
        ],
        [
            Paragraph("Shadowing Margin (90% loc.)", style_body),
            Paragraph("—", style_body),
            Paragraph(f"{shadowing_margin_90_db:.1f} dB", style_body),
            Paragraph("Log-normal σ · z(0.90)", style_body)
        ],
        [
            Paragraph("System Margin", style_body),
            Paragraph("—", style_body),
            Paragraph(f"{system_margin_db:.1f} dB", style_body),
            Paragraph("Fade+body+cable aging+interference", style_body)
        ],
        [
            Paragraph("<b>RSSI (Optimistic)</b>", style_body_bold),
            Paragraph("—", style_body),
            Paragraph(f"<b>{edge_rssi_dbm:.1f} dBm</b>", style_body_bold),
            Paragraph("Median signal, no margins applied", style_body)
        ],
        [
            Paragraph("<b>RSSI (Realistic)</b>", style_body_bold),
            Paragraph("—", style_body),
            Paragraph(f"<b>{realistic_rssi:.1f} dBm</b>", style_body_bold),
            Paragraph("Base + diffraction + shadowing + sys margin", style_body)
        ],
        [
            Paragraph("Receiver Sensitivity", style_body),
            Paragraph(f"{equipment_bts.receiver_sensitivity_dbm:.1f} dBm", style_body),
            Paragraph(f"{equipment_cpe.receiver_sensitivity_dbm:.1f} dBm", style_body),
            Paragraph("Minimum for reliable demodulation", style_body)
        ],
        [
            Paragraph("<b>Link Margin (Realistic)</b>", style_body_bold),
            Paragraph("—", style_body),
            Paragraph(f"<b>{realistic_margin:.1f} dB</b>", style_body_bold),
            Paragraph("Target: ≥ +3 dB (green ≥10, amber 3–10, red <3)", style_body)
        ],
        [
            Paragraph("<b>Link Margin (Pessimistic)</b>", style_body_bold),
            Paragraph("—", style_body),
            Paragraph(f"<b>{pessimistic_margin:.1f} dB</b>", style_body_bold),
            Paragraph("Includes clutter + 95% shadowing margin", style_body)
        ],
        [
            Paragraph("<b>Link Status</b>", style_body_bold),
            Paragraph("—", style_body),
            Paragraph(f"<b>{margin_status}</b>", style_pass_fail),
            Paragraph("Based on realistic margin", style_body)
        ]
    ]

    lb_table = Table(link_budget_data, colWidths=[160, 110, 110, 160])

    # Build row-level color styles
    n_rows = len(link_budget_data)
    realistic_row = 14   # 0-indexed: "Link Margin (Realistic)"
    pessimistic_row = 15
    realistic_bg = _margin_color(realistic_margin)
    pessimistic_bg = _margin_color(pessimistic_margin)

    lb_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
        ('TOPPADDING', (0, 1), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        # Color the margin rows
        ('BACKGROUND', (0, realistic_row), (-1, realistic_row), realistic_bg),
        ('BACKGROUND', (0, pessimistic_row), (-1, pessimistic_row), pessimistic_bg),
    ]))
    
    # Change text color of header row in TableStyle
    # ReportLab Table handles Paragraph colors inside the ParagraphStyle, so we wrapped them in <b>
    story.append(lb_table)
    story.append(Spacer(1, 15))
    
    # Site Comparison Table (If multiple sites were compared)
    if all_sites_comparison:
        story.append(Paragraph("Alternative Site Comparison", style_heading))
        story.append(Paragraph("Comparison of all candidate BTS locations mapped in the KMZ project file.", style_subtitle))
        story.append(Spacer(1, 8))
        
        # Table Columns: Site Name | Coverage % | Good Signal % | Max Range (km) | Recommendation
        comp_headers = [
            Paragraph("<b>Site Name</b>", style_body_bold),
            Paragraph("<b>Coverage %</b>", style_body_bold),
            Paragraph("<b>Good Signal %</b>", style_body_bold),
            Paragraph("<b>Max Range</b>", style_body_bold),
            Paragraph("<b>Result</b>", style_body_bold)
        ]
        
        comp_data = [comp_headers]
        for site in all_sites_comparison:
            is_best = site.get('is_best', False)
            style_site_name = style_body_bold if is_best else style_body
            rec_text = "<b>Recommended (Best)</b>" if is_best else "Alternative Site"
            
            comp_data.append([
                Paragraph(site['name'], style_site_name),
                Paragraph(f"{site['coverage_pct']}%", style_body),
                Paragraph(f"{site['good_pct']}%", style_body),
                Paragraph(f"{site['max_range_km']} km", style_body),
                Paragraph(rec_text, style_body)
            ])
            
        comp_table = Table(comp_data, colWidths=[160, 80, 95, 90, 115])
        
        # Style table
        t_style = [
            ('BACKGROUND', (0,0), (-1,0), COLOR_PRIMARY),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('TOPPADDING', (0,0), (-1,0), 6),
            ('BOTTOMPADDING', (0,1), (-1,-1), 4),
            ('TOPPADDING', (0,1), (-1,-1), 4),
            ('GRID', (0,0), (-1,-1), 0.5, COLOR_BORDER),
        ]
        
        # Highlight the best site row
        for idx, site in enumerate(all_sites_comparison):
            if site.get('is_best', False):
                t_style.append(('BACKGROUND', (0, idx + 1), (-1, idx + 1), COLOR_LIGHT))
                
        comp_table.setStyle(TableStyle(t_style))
        story.append(comp_table)
        
    # Build Document
    doc.build(
        story, 
        onFirstPage=draw_page_decorations, 
        onLaterPages=draw_page_decorations
    )
