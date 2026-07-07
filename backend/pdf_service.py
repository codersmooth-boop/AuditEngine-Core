"""Generate a terminal-styled PDF audit report using reportlab."""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

BLACK = colors.HexColor("#000000")
SURFACE = colors.HexColor("#0D0D0D")
BORDER = colors.HexColor("#2A2A2A")
TEXT = colors.HexColor("#E8E8E8")
SECONDARY = colors.HexColor("#808080")
CRITICAL = colors.HexColor("#FF0000")
MODERATE = colors.HexColor("#FFBF00")
COMPLIANT = colors.HexColor("#00FF41")


def _sev_color(sev: str):
    return {"CRITICAL": CRITICAL, "MODERATE": MODERATE, "COMPLIANT": COMPLIANT}.get(sev, SECONDARY)


def build_audit_pdf(audit: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"AuditEngine — {audit.get('client_name','')}",
    )
    styles = getSampleStyleSheet()

    mono = ParagraphStyle("mono", parent=styles["Normal"], fontName="Courier", fontSize=8, textColor=TEXT, leading=11)
    mono_sec = ParagraphStyle("mono_sec", parent=mono, textColor=SECONDARY)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, textColor=TEXT, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName="Courier-Bold", fontSize=10, textColor=SECONDARY, spaceBefore=12, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["Normal"], fontName="Helvetica", fontSize=9, textColor=TEXT, leading=13)

    story = []

    # Header
    story.append(Paragraph("AUDITENGINE // COMPLIANCE REPORT", h2))
    story.append(Paragraph(audit.get("client_name", ""), h1))
    story.append(Paragraph(
        f"NACE {audit.get('nace_code','')} — {audit.get('nace_name','')} · FY{audit.get('reporting_year','')}",
        mono_sec,
    ))
    story.append(Spacer(1, 8 * mm))

    # KPI table
    score = audit.get("compliance_score", 0)
    kpi_data = [
        ["COMPLIANCE SCORE", "VALUE AT STAKE", "CRITICAL FINDINGS", "GREENWASHING RISK"],
        [f"{score}/100", f"€ {audit.get('value_at_stake_eur',0):,.0f}",
         str(audit.get("critical_findings_count", 0)),
         audit.get("greenwashing_risk", "—")],
    ]
    kpi_tbl = Table(kpi_data, colWidths=[42 * mm] * 4)
    score_color = COMPLIANT if score >= 80 else MODERATE if score >= 60 else CRITICAL
    kpi_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
        ("BACKGROUND", (0, 1), (-1, 1), BLACK),
        ("TEXTCOLOR", (0, 0), (-1, 0), SECONDARY),
        ("TEXTCOLOR", (0, 1), (-1, 1), TEXT),
        ("TEXTCOLOR", (0, 1), (0, 1), score_color),
        ("FONTNAME", (0, 0), (-1, 0), "Courier"),
        ("FONTNAME", (0, 1), (-1, 1), "Courier-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTSIZE", (0, 1), (-1, 1), 12),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 8 * mm))

    if audit.get("executive_summary"):
        story.append(Paragraph("EXECUTIVE SUMMARY", h2))
        story.append(Paragraph(audit["executive_summary"], body))

    # Findings
    story.append(Paragraph("FINDINGS", h2))
    findings = audit.get("findings", [])
    for f in findings:
        sev = f.get("severity", "MODERATE")
        header = f"[{sev}] {f.get('data_point','')} — {f.get('status','')} · {f.get('regulatory_ref','')}"
        story.append(Paragraph(header, ParagraphStyle("sev", parent=mono, textColor=_sev_color(sev), fontName="Courier-Bold")))
        story.append(Paragraph(f.get("finding_detail", ""), body))
        if f.get("recommendation"):
            story.append(Paragraph(f"→ {f['recommendation']}", mono_sec))
        story.append(Spacer(1, 3 * mm))

    story.append(PageBreak())
    story.append(Paragraph("STRATEGIC VALUE ROADMAP", h2))
    roadmap = audit.get("roadmap", [])
    if roadmap:
        data = [["#", "ACTION", "METRIC IMPACT", "€ SAVING", "COST", "PAYBACK"]]
        for i, r in enumerate(roadmap, 1):
            data.append([
                str(i),
                r.get("action", ""),
                r.get("metric_impact", ""),
                f"€ {r.get('saving_eur',0):,.0f}",
                f"€ {r.get('implementation_cost_eur',0):,.0f}",
                f"{r.get('payback_months',0)} mo",
            ])
        tbl = Table(data, colWidths=[8 * mm, 55 * mm, 40 * mm, 25 * mm, 22 * mm, 18 * mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
            ("TEXTCOLOR", (0, 0), (-1, 0), SECONDARY),
            ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
            ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Courier"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(tbl)

    def _page_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BLACK)
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
        canvas.setFillColor(SECONDARY)
        canvas.setFont("Courier", 7)
        canvas.drawString(18 * mm, 10 * mm, "AUDITENGINE // CONFIDENTIAL")
        canvas.drawRightString(doc.pagesize[0] - 18 * mm, 10 * mm, f"PAGE {doc.page:03d}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_page_bg, onLaterPages=_page_bg)
    return buf.getvalue()
