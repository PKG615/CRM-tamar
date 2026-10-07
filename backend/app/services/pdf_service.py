"""
Generates a proposal PDF on-demand (no persistent file storage needed —
the Proposal row already has everything required to rebuild it byte-for-
byte at download time). Uses reportlab's Platypus layer for a clean
invoice-style document.
"""
import io
from datetime import datetime, timedelta
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

INK = colors.HexColor("#14213D")
ACCENT = colors.HexColor("#1F6F5C")
MUTED = colors.HexColor("#5B5F5A")
BORDER = colors.HexColor("#DCDDD6")


def _money(value) -> str:
    try:
        return f"Rs. {Decimal(value):,.2f}"
    except Exception:
        return f"Rs. {value}"


def generate_proposal_pdf(proposal, lead, organization) -> bytes:
    """
    proposal: Proposal ORM row (line_items, subtotal, grand_total, terms,
              validity_days, payment_terms, proposal_number, created_at)
    lead: Lead ORM row (business_name, contact info)
    organization: Organization ORM row (name — the sender)
    Returns raw PDF bytes, ready to stream back in an HTTP response.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=22 * mm, bottomMargin=20 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("OrgName", parent=styles["Title"], fontSize=18, textColor=INK, spaceAfter=2))
    styles.add(ParagraphStyle("Muted", parent=styles["Normal"], textColor=MUTED, fontSize=9.5))
    styles.add(ParagraphStyle("SectionLabel", parent=styles["Normal"], textColor=MUTED, fontSize=8.5, spaceAfter=2))
    styles.add(ParagraphStyle("BodySmall", parent=styles["Normal"], fontSize=9.5, leading=14))

    story = []

    # ---- Header ----
    story.append(Paragraph(organization.name, styles["OrgName"]))
    story.append(Paragraph("Business Proposal", styles["Muted"]))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", color=BORDER, thickness=1))
    story.append(Spacer(1, 14))

    # ---- Proposal meta + client info, side by side ----
    created = proposal.created_at.strftime("%d %b %Y") if isinstance(proposal.created_at, datetime) else str(proposal.created_at)
    valid_until = (proposal.created_at + timedelta(days=proposal.validity_days or 30)).strftime("%d %b %Y") \
        if isinstance(proposal.created_at, datetime) else "-"

    meta_table = Table(
        [
            [
                Paragraph("PREPARED FOR", styles["SectionLabel"]),
                Paragraph("PROPOSAL DETAILS", styles["SectionLabel"]),
            ],
            [
                Paragraph(
                    f"<b>{lead.business_name}</b><br/>"
                    f"{(lead.address or '')}<br/>"
                    f"{(lead.city or '')} {(lead.state or '')}<br/>"
                    f"{(lead.phone or '')}",
                    styles["BodySmall"],
                ),
                Paragraph(
                    f"<b>Number:</b> {proposal.proposal_number}<br/>"
                    f"<b>Date:</b> {created}<br/>"
                    f"<b>Valid until:</b> {valid_until}<br/>"
                    f"<b>Status:</b> {proposal.status.value if hasattr(proposal.status, 'value') else proposal.status}",
                    styles["BodySmall"],
                ),
            ],
        ],
        colWidths=[85 * mm, 75 * mm],
    )
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))

    # ---- Line items table ----
    header = ["Service", "Qty", "Unit price", "Discount", "Tax %", "Line total"]
    rows = [header]
    for item in proposal.line_items:
        rows.append([
            item.get("service", ""),
            str(item.get("quantity", "")),
            _money(item.get("unit_price", 0)),
            _money(item.get("discount", 0)),
            f"{item.get('tax_percent', 0)}%",
            _money(item.get("line_total", 0)),
        ])

    items_table = Table(rows, colWidths=[55 * mm, 15 * mm, 28 * mm, 22 * mm, 15 * mm, 25 * mm])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAF8")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 10))

    # ---- Totals ----
    totals_table = Table(
        [
            ["Subtotal", _money(proposal.subtotal)],
            ["Grand total", _money(proposal.grand_total)],
        ],
        colWidths=[135 * mm, 25 * mm],
    )
    totals_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 11),
        ("TEXTCOLOR", (0, 1), (-1, 1), ACCENT),
        ("LINEABOVE", (0, 1), (-1, 1), 0.75, BORDER),
        ("TOPPADDING", (0, 1), (-1, 1), 8),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 20))

    # ---- Payment terms + terms & conditions ----
    if proposal.payment_terms:
        story.append(Paragraph("PAYMENT TERMS", styles["SectionLabel"]))
        story.append(Paragraph(proposal.payment_terms, styles["BodySmall"]))
        story.append(Spacer(1, 12))

    if proposal.terms:
        story.append(Paragraph("TERMS & CONDITIONS", styles["SectionLabel"]))
        story.append(Paragraph(proposal.terms.replace("\n", "<br/>"), styles["BodySmall"]))
        story.append(Spacer(1, 12))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", color=BORDER, thickness=1))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"This proposal is valid until {valid_until}. Generated by {organization.name}.",
        styles["Muted"],
    ))

    doc.build(story)
    return buf.getvalue()
