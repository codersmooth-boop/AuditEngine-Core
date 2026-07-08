"""Generate a terminal-styled PDF audit report using reportlab."""
from datetime import datetime, timezone

import io
from pypdf import PdfWriter, PdfReader
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
    """Full report = [Board Brief cover] + [Detailed Findings] + [Technical Appendix]."""
    body_bytes = _build_full_body(audit)
    cover_bytes = build_board_brief_pdf(audit)

    writer = PdfWriter()
    for src in (cover_bytes, body_bytes):
        reader = PdfReader(io.BytesIO(src))
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _build_full_body(audit: dict) -> bytes:
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

    # ---------- TECHNICAL APPENDIX ----------
    story.append(PageBreak())
    story.append(Paragraph("TECHNICAL APPENDIX", h2))

    appendix_rows = [
        ["AUDIT ID", audit.get("audit_id", "—")],
        ["CLIENT", audit.get("client_name", "—")],
        ["NACE REV. 2", f"{audit.get('nace_code','—')} · {audit.get('nace_name','—')}"],
        ["REPORTING YEAR", str(audit.get("reporting_year", "—"))],
        ["STATUS", audit.get("status", "—")],
        ["CREATED AT", str(audit.get("created_at", "—"))],
        ["COMPLETED AT", str(audit.get("completed_at", "—"))],
        ["GREENWASHING RISK", audit.get("greenwashing_risk", "—")],
        ["TOTAL FINDINGS", str(len(audit.get("findings", [])))],
        ["CRITICAL COUNT", str(audit.get("critical_findings_count", 0))],
        ["ANALYSIS ENGINE", "Claude Sonnet 4.5 (anthropic:claude-sonnet-4-5-20250929)"],
    ]
    ap_tbl = Table(appendix_rows, colWidths=[45 * mm, 130 * mm])
    ap_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), SURFACE),
        ("TEXTCOLOR", (0, 0), (0, -1), SECONDARY),
        ("TEXTCOLOR", (1, 0), (1, -1), TEXT),
        ("FONTNAME", (0, 0), (-1, -1), "Courier"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(ap_tbl)
    story.append(Spacer(1, 6 * mm))

    files = audit.get("files") or []
    story.append(Paragraph("FILES INGESTED", h2))
    if files:
        for i, fn in enumerate(files, 1):
            story.append(Paragraph(f"[{i:03d}] {fn}", mono))
    else:
        story.append(Paragraph("— no files on record —", mono_sec))

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



def build_board_brief_pdf(audit: dict) -> bytes:
    """Single-page executive Board Brief — clinical intelligence report format."""
    from datetime import datetime, timezone
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"AuditEngine Board Brief — {audit.get('client_name','')}",
    )

    WHITE_BORDER = colors.HexColor("#FFFFFF")
    mono = ParagraphStyle("mono", fontName="Courier", fontSize=8, textColor=TEXT, leading=11)
    mono_sec = ParagraphStyle("mono_sec", fontName="Courier", fontSize=7, textColor=SECONDARY, leading=10, letterSpacing=1)
    verdict = ParagraphStyle("verdict", fontName="Helvetica", fontSize=11, textColor=TEXT, leading=16)
    label = ParagraphStyle("label", fontName="Courier", fontSize=7, textColor=SECONDARY, leading=10, letterSpacing=1.4)
    metric_l = ParagraphStyle("metric_l", fontName="Courier", fontSize=18, textColor=TEXT, leading=22)

    score = int(audit.get("compliance_score", 0) or 0)
    score_color = COMPLIANT if score >= 80 else MODERATE if score >= 60 else CRITICAL
    score_hex = "#00FF41" if score >= 80 else "#FFBF00" if score >= 60 else "#FF0000"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d · %H:%M UTC")

    story = []

    # ---- TOP: Client / Date / Score ----
    top = [[
        Paragraph("<font color='#808080'>// CLIENT</font>", label),
        Paragraph("<font color='#808080'>// GENERATED</font>", label),
        Paragraph("<font color='#808080'>// CASE</font>", label),
    ], [
        Paragraph(f"<b>{audit.get('client_name','')}</b>", ParagraphStyle("client", fontName="Helvetica-Bold", fontSize=13, textColor=TEXT, leading=15)),
        Paragraph(generated, mono),
        Paragraph(audit.get("audit_id", "").upper(), mono_sec),
    ]]
    top_tbl = Table(top, colWidths=[80 * mm, 55 * mm, 43 * mm])
    top_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, WHITE_BORDER),
        ("LINEABOVE", (0, 1), (-1, 1), 0.5, WHITE_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), BLACK),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(top_tbl)
    story.append(Spacer(1, 4 * mm))

    # ---- SCORE HERO ----
    hero = [[
        Paragraph("<font color='#808080'>// COMPLIANCE SCORE</font>", label),
    ], [
        Paragraph(
            f"<font color='{score_hex}' name='Courier'><b>{score:03d}</b></font>"
            "<font color='#808080' size='10'> / 100</font>",
            ParagraphStyle("heroScore", fontName="Courier-Bold", fontSize=64, textColor=score_color, leading=68, alignment=1),
        ),
    ], [
        Paragraph(
            "MATERIALLY COMPLIANT" if score >= 80 else "PARTIAL ALIGNMENT" if score >= 60 else "NON-COMPLIANT POSTURE",
            ParagraphStyle("heroLbl", fontName="Courier-Bold", fontSize=9, textColor=score_color, leading=12, alignment=1, letterSpacing=3),
        ),
    ]]
    hero_tbl = Table(hero, colWidths=[178 * mm])
    hero_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, WHITE_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), BLACK),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 0),
        ("TOPPADDING", (0, 2), (-1, 2), 0),
        ("BOTTOMPADDING", (0, 2), (-1, 2), 10),
    ]))
    story.append(hero_tbl)
    story.append(Spacer(1, 4 * mm))

    # ---- EXECUTIVE VERDICT ----
    verdict_text = audit.get("executive_summary") or "Verdict pending."
    verdict_block = Table([
        [Paragraph("<font color='#808080'>// THE BOTTOM LINE — EXECUTIVE VERDICT</font>", label)],
        [Paragraph(verdict_text, verdict)],
    ], colWidths=[178 * mm])
    verdict_block.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, WHITE_BORDER),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, WHITE_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), BLACK),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(verdict_block)
    story.append(Spacer(1, 4 * mm))

    # ---- FINANCIAL IMPACT ----
    vas = float(audit.get("value_at_stake_eur") or 0)
    total_saving = sum(float(r.get("saving_eur") or 0) for r in (audit.get("roadmap") or []))
    total_cost = sum(float(r.get("implementation_cost_eur") or 0) for r in (audit.get("roadmap") or []))

    fin = Table([
        [
            Paragraph("<font color='#808080'>// COST OF NON-COMPLIANCE</font>", label),
            Paragraph("<font color='#808080'>// POTENTIAL SAVINGS</font>", label),
            Paragraph("<font color='#808080'>// NET RECOVERABLE</font>", label),
        ],
        [
            Paragraph(f"<font color='#FF0000'>€ {vas:,.0f}</font>", ParagraphStyle("neg", fontName="Courier-Bold", fontSize=18, textColor=CRITICAL, leading=22)),
            Paragraph(f"<font color='#00FF41'>€ {total_saving:,.0f}</font>", ParagraphStyle("pos", fontName="Courier-Bold", fontSize=18, textColor=COMPLIANT, leading=22)),
            Paragraph(f"<font color='#E8E8E8'>€ {max(total_saving - total_cost, 0):,.0f}</font>", metric_l),
        ],
        [
            Paragraph("Quantified exposure if gaps unaddressed.", mono_sec),
            Paragraph("Roadmap-projected value capture.", mono_sec),
            Paragraph(f"After € {total_cost:,.0f} implementation cost.", mono_sec),
        ],
    ], colWidths=[59.3 * mm, 59.3 * mm, 59.3 * mm])
    fin.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, WHITE_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, WHITE_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), BLACK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(fin)
    story.append(Spacer(1, 4 * mm))

    # ---- TOP 3 CRITICAL RISKS ----
    findings = audit.get("findings", []) or []
    order = {"CRITICAL": 0, "MODERATE": 1, "COMPLIANT": 2}
    top_risks = sorted(
        [f for f in findings if f.get("severity") != "COMPLIANT"],
        key=lambda f: (order.get(f.get("severity"), 9), -(f.get("impact_score") or 0)),
    )[:3]

    risk_rows = [[Paragraph("<font color='#808080'>// TOP 3 CRITICAL RISKS</font>", label)]]
    risk_tbl_hdr = Table(risk_rows, colWidths=[178 * mm])
    risk_tbl_hdr.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, WHITE_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), BLACK),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(risk_tbl_hdr)

    for i, f in enumerate(top_risks, 1):
        sev = f.get("severity", "CRITICAL")
        sev_c = _sev_color(sev)
        sev_hex = {"CRITICAL": "#FF0000", "MODERATE": "#FFBF00", "COMPLIANT": "#00FF41"}.get(sev, "#808080")
        row = Table([[
            Paragraph(f"<font color='{sev_hex}' name='Courier-Bold' size='16'>0{i}</font>", ParagraphStyle("num", fontName="Courier-Bold", fontSize=16, textColor=sev_c, leading=18)),
            [
                Paragraph(f"<b><font color='#E8E8E8'>{f.get('data_point','')}</font></b>", ParagraphStyle("dp", fontName="Helvetica-Bold", fontSize=9, textColor=TEXT, leading=12)),
                Paragraph(f.get("finding_detail", "")[:220], ParagraphStyle("dt", fontName="Helvetica", fontSize=8, textColor=TEXT, leading=11)),
            ],
            [
                Paragraph(f"<font color='{sev_hex}'>[{sev}]</font>", ParagraphStyle("sv", fontName="Courier-Bold", fontSize=7, textColor=sev_c, leading=10, letterSpacing=1.5, alignment=2)),
                Paragraph(f"<font color='#808080'>{f.get('regulatory_ref','')}</font>", ParagraphStyle("rr", fontName="Courier", fontSize=7, textColor=SECONDARY, leading=10, alignment=2)),
                Paragraph(f"<font color='#808080'>STATUS: {f.get('status','')}</font>", ParagraphStyle("st", fontName="Courier", fontSize=7, textColor=SECONDARY, leading=10, alignment=2)),
            ],
        ]], colWidths=[12 * mm, 116 * mm, 50 * mm])
        row.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, WHITE_BORDER),
            ("LINEABOVE", (0, 0), (-1, 0), 0, BLACK),
            ("BACKGROUND", (0, 0), (-1, -1), BLACK),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(row)

    story.append(Spacer(1, 4 * mm))

    # ---- TOP 3 IMMEDIATE FIXES ----
    roadmap = (audit.get("roadmap") or [])[:3]
    fx_hdr = Table([[Paragraph("<font color='#808080'>// THE ACTION PATH — TOP 3 IMMEDIATE FIXES</font>", label)]], colWidths=[178 * mm])
    fx_hdr.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, WHITE_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), BLACK),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(fx_hdr)

    for i, r in enumerate(roadmap, 1):
        row = Table([[
            Paragraph(f"<font color='#00FF41' name='Courier-Bold' size='14'>→ 0{i}</font>", ParagraphStyle("fxn", fontName="Courier-Bold", fontSize=14, textColor=COMPLIANT, leading=16)),
            [
                Paragraph(f"<b><font color='#E8E8E8'>{r.get('action','')}</font></b>", ParagraphStyle("fxa", fontName="Helvetica-Bold", fontSize=9, textColor=TEXT, leading=12)),
                Paragraph(f"<font color='#808080'>{r.get('metric_impact','')}</font>", ParagraphStyle("fxm", fontName="Courier", fontSize=7, textColor=SECONDARY, leading=10)),
            ],
            [
                Paragraph(f"<font color='#00FF41'>€ {float(r.get('saving_eur') or 0):,.0f}</font>", ParagraphStyle("fxs", fontName="Courier-Bold", fontSize=10, textColor=COMPLIANT, leading=12, alignment=2)),
                Paragraph(f"<font color='#808080'>SAVING</font>", ParagraphStyle("fxsl", fontName="Courier", fontSize=6, textColor=SECONDARY, leading=8, alignment=2)),
            ],
            [
                Paragraph(f"<font color='#FFBF00'>{int(r.get('payback_months') or 0)} MO</font>", ParagraphStyle("fxp", fontName="Courier-Bold", fontSize=10, textColor=MODERATE, leading=12, alignment=2)),
                Paragraph(f"<font color='#808080'>PAYBACK</font>", ParagraphStyle("fxpl", fontName="Courier", fontSize=6, textColor=SECONDARY, leading=8, alignment=2)),
            ],
        ]], colWidths=[16 * mm, 100 * mm, 32 * mm, 30 * mm])
        row.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, WHITE_BORDER),
            ("BACKGROUND", (0, 0), (-1, -1), BLACK),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(row)

    def _page_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BLACK)
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
        canvas.setFillColor(SECONDARY)
        canvas.setFont("Courier", 6.5)
        canvas.drawString(16 * mm, 10 * mm, "AUDITENGINE // BOARD BRIEF // CONFIDENTIAL")
        canvas.drawRightString(doc.pagesize[0] - 16 * mm, 10 * mm, "THE MIRROR OF CERTAINTY")
        # Verified evidence chain
        import hashlib as _hl
        fh = audit.get("file_hashes") or []
        composite_hash = _hl.sha256(("|".join(x.get("sha256", "") for x in fh)).encode()).hexdigest() if fh else "—"
        canvas.setFillColor(colors.HexColor("#00FF41"))
        canvas.setFont("Courier", 6.5)
        canvas.drawString(16 * mm, 6 * mm, f"VERIFIED EVIDENCE CHAIN: {composite_hash}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_page_bg, onLaterPages=_page_bg)
    return buf.getvalue()


def build_snapshot_pdf(entries: list, year: int, merkle_root: str, workspace_email: str = "") -> bytes:
    """CFO Master-Doc: yearly snapshot of the compliance ledger."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"AuditEngine Statutory Snapshot FY{year}",
    )
    WHITE = colors.HexColor("#FFFFFF")

    label = ParagraphStyle("label", fontName="Courier", fontSize=7, textColor=SECONDARY, leading=10, letterSpacing=1.4)
    mono = ParagraphStyle("mono", fontName="Courier", fontSize=8, textColor=TEXT, leading=11)
    mono_sec = ParagraphStyle("mono_sec", fontName="Courier", fontSize=7, textColor=SECONDARY, leading=10)
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=22, textColor=TEXT, leading=26)

    story = []

    # ---------- PAGE 1 · EXECUTIVE ----------
    story.append(Paragraph("<font color='#808080'>// STATUTORY AUDIT SNAPSHOT</font>", label))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(f"Workspace Compliance Posture · FY{year}", h1))
    story.append(Paragraph(f"<font color='#808080'>Workspace: {workspace_email or '—'} · Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d · %H:%M UTC')}</font>", mono_sec))
    story.append(Spacer(1, 6 * mm))

    n = len(entries)
    avg_score = int(round(sum((e["compliance_score"] or 0) for e in entries) / n)) if n else 0
    total_vas = sum((e["value_at_stake_eur"] or 0) for e in entries)
    total_crit = sum((e["critical_findings_count"] or 0) for e in entries)
    risk_dist = {"HIGH": 0, "MODERATE": 0, "LOW": 0, "NONE": 0}
    for e in entries:
        risk_dist[e.get("greenwashing_risk", "NONE")] = risk_dist.get(e.get("greenwashing_risk", "NONE"), 0) + 1
    score_hex = "#00FF41" if avg_score >= 80 else "#FFBF00" if avg_score >= 60 else "#FF0000"

    kpi = Table([[
        [Paragraph("<font color='#808080'>// AUDITS ON RECORD</font>", label),
         Paragraph(f"<font color='#E8E8E8'>{n:03d}</font>", ParagraphStyle("v", fontName="Courier-Bold", fontSize=22, textColor=TEXT, leading=26))],
        [Paragraph("<font color='#808080'>// AVG COMPLIANCE</font>", label),
         Paragraph(f"<font color='{score_hex}'>{avg_score}/100</font>", ParagraphStyle("v2", fontName="Courier-Bold", fontSize=22, leading=26))],
        [Paragraph("<font color='#808080'>// TOTAL VALUE-AT-STAKE</font>", label),
         Paragraph(f"<font color='#FF0000'>€ {total_vas:,.0f}</font>", ParagraphStyle("v3", fontName="Courier-Bold", fontSize=22, leading=26))],
        [Paragraph("<font color='#808080'>// CRITICAL FINDINGS</font>", label),
         Paragraph(f"<font color='#FFBF00'>{total_crit}</font>", ParagraphStyle("v4", fontName="Courier-Bold", fontSize=22, leading=26))],
    ]], colWidths=[44.5 * mm] * 4)
    kpi.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, WHITE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, WHITE),
        ("BACKGROUND", (0, 0), (-1, -1), BLACK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(kpi)
    story.append(Spacer(1, 6 * mm))

    # Risk breakdown
    risk_rows = [[
        Paragraph("<font color='#808080'>// GREENWASHING RISK DISTRIBUTION</font>", label),
    ]]
    risk_tbl_hdr = Table(risk_rows, colWidths=[178 * mm])
    risk_tbl_hdr.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, WHITE),
        ("BACKGROUND", (0, 0), (-1, -1), BLACK),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(risk_tbl_hdr)
    risk_body = Table([[
        Paragraph(f"<font color='#FF0000'>{risk_dist['HIGH']}</font>", ParagraphStyle("rh", fontName="Courier-Bold", fontSize=20, leading=24, alignment=1)),
        Paragraph(f"<font color='#FFBF00'>{risk_dist['MODERATE']}</font>", ParagraphStyle("rm", fontName="Courier-Bold", fontSize=20, leading=24, alignment=1)),
        Paragraph(f"<font color='#00FF41'>{risk_dist['LOW']}</font>", ParagraphStyle("rl", fontName="Courier-Bold", fontSize=20, leading=24, alignment=1)),
        Paragraph(f"<font color='#808080'>{risk_dist['NONE']}</font>", ParagraphStyle("rn", fontName="Courier-Bold", fontSize=20, leading=24, alignment=1)),
    ], [
        Paragraph("<font color='#808080'>HIGH</font>", ParagraphStyle("l1", fontName="Courier", fontSize=7, leading=10, alignment=1, letterSpacing=1.5)),
        Paragraph("<font color='#808080'>MODERATE</font>", ParagraphStyle("l2", fontName="Courier", fontSize=7, leading=10, alignment=1, letterSpacing=1.5)),
        Paragraph("<font color='#808080'>LOW</font>", ParagraphStyle("l3", fontName="Courier", fontSize=7, leading=10, alignment=1, letterSpacing=1.5)),
        Paragraph("<font color='#808080'>NONE</font>", ParagraphStyle("l4", fontName="Courier", fontSize=7, leading=10, alignment=1, letterSpacing=1.5)),
    ]], colWidths=[44.5 * mm] * 4)
    risk_body.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, WHITE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, WHITE),
        ("BACKGROUND", (0, 0), (-1, -1), BLACK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(risk_body)

    story.append(PageBreak())

    # ---------- PAGE 2 · MASTER EVIDENCE TABLE ----------
    story.append(Paragraph("<font color='#808080'>// MASTER EVIDENCE TABLE</font>", label))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(f"Ledger of Record · FY{year}", ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=16, textColor=TEXT, leading=20)))
    story.append(Spacer(1, 5 * mm))

    header = ["#", "AUDIT ID", "CLIENT", "DATE", "SCORE", "RISK", "COMPOSITE HASH (SHA-256)"]
    data = [header]
    for i, e in enumerate(entries, 1):
        h16 = (e["composite_hash"] or "")[:32] + "…" if e["composite_hash"] else "—"
        data.append([
            f"{i:03d}",
            e["audit_id"][:14],
            e["client_name"][:22],
            (e["created_at"] or "")[:10],
            f"{e['compliance_score'] if e['compliance_score'] is not None else '—'}",
            (e["greenwashing_risk"] or "—")[:4],
            h16,
        ])
    if not entries:
        data.append(["—", "—", "no completed audits on record for this year", "—", "—", "—", "—"])

    tbl = Table(data, colWidths=[10 * mm, 30 * mm, 40 * mm, 22 * mm, 14 * mm, 12 * mm, 50 * mm])
    style = [
        ("BOX", (0, 0), (-1, -1), 0.5, WHITE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, WHITE),
        ("BACKGROUND", (0, 0), (-1, -1), BLACK),
        ("TEXTCOLOR", (0, 0), (-1, 0), SECONDARY),
        ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
        ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Courier"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    # Color-code score and risk columns per row
    for i, e in enumerate(entries, 1):
        s = e["compliance_score"] or 0
        sc = colors.HexColor("#00FF41") if s >= 80 else colors.HexColor("#FFBF00") if s >= 60 else colors.HexColor("#FF0000")
        rc = {"HIGH": colors.HexColor("#FF0000"), "MODERATE": colors.HexColor("#FFBF00"), "LOW": colors.HexColor("#00FF41"), "NONE": SECONDARY}.get(e["greenwashing_risk"], SECONDARY)
        style += [("TEXTCOLOR", (4, i), (4, i), sc), ("TEXTCOLOR", (5, i), (5, i), rc), ("TEXTCOLOR", (6, i), (6, i), colors.HexColor("#00FF41"))]
    tbl.setStyle(TableStyle(style))
    story.append(tbl)

    # Certification block
    story.append(Spacer(1, 8 * mm))
    cert = Table([
        [Paragraph("<font color='#808080'>// CERTIFICATION OF INTEGRITY</font>", label)],
        [Paragraph(
            f"This Snapshot certifies that <b>{n}</b> audits recorded in the workspace for reporting year <b>FY{year}</b> "
            f"were executed by AuditEngine v1.0 (anthropic:claude-sonnet-4-5-20250929) and their evidence chains are "
            f"provable via the SHA-256 fingerprints listed above. The Master Merkle Root below binds all audit hashes "
            f"into a single tamper-evident commitment.",
            ParagraphStyle("cert", fontName="Helvetica", fontSize=9, textColor=TEXT, leading=13),
        )],
        [Paragraph(f"<font color='#00FF41' name='Courier-Bold'>MASTER MERKLE ROOT: {merkle_root}</font>",
            ParagraphStyle("mmr", fontName="Courier-Bold", fontSize=8, textColor=COMPLIANT, leading=12))],
    ], colWidths=[178 * mm])
    cert.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, WHITE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, WHITE),
        ("LINEABOVE", (0, 2), (-1, 2), 0.5, WHITE),
        ("BACKGROUND", (0, 0), (-1, -1), BLACK),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(cert)

    def _bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BLACK)
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
        canvas.setFillColor(SECONDARY)
        canvas.setFont("Courier", 6.5)
        canvas.drawString(16 * mm, 10 * mm, f"AUDITENGINE // STATUTORY SNAPSHOT // FY{year}")
        canvas.drawRightString(doc.pagesize[0] - 16 * mm, 10 * mm, f"PAGE {doc.page:02d}")
        canvas.setFillColor(colors.HexColor("#00FF41"))
        canvas.drawString(16 * mm, 6 * mm, f"MASTER MERKLE ROOT: {merkle_root}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_bg, onLaterPages=_bg)
    return buf.getvalue()

