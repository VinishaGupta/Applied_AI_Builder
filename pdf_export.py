from __future__ import annotations

from io import BytesIO
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from models import DDRReport, ExtractedImage
from models import ReportAsset


def build_ddr_pdf(ddr: DDRReport, inspection: ReportAsset, thermal: ReportAsset) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
        title="Detailed Diagnostic Report",
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    body_style = styles["BodyText"]
    body_style.leading = 15
    body_style.spaceAfter = 8
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#163A5F"),
        borderPadding=0,
        spaceBefore=10,
        spaceAfter=8,
    )
    subheading_style = ParagraphStyle(
        "SubHeading",
        parent=styles["Heading3"],
        textColor=colors.HexColor("#274C77"),
        spaceBefore=8,
        spaceAfter=6,
    )
    bullet_style = ParagraphStyle(
        "DDRBullet",
        parent=body_style,
        leftIndent=12,
        firstLineIndent=0,
        spaceAfter=4,
    )
    label_style = ParagraphStyle(
        "LabelStyle",
        parent=body_style,
        textColor=colors.HexColor("#163A5F"),
        fontName="Helvetica-Bold",
        spaceAfter=4,
    )

    metadata = _extract_report_metadata(inspection.text)

    story = []
    story.extend(_cover_page(metadata, title_style, body_style))
    story.append(PageBreak())

    story.extend(
        _section_block(
            "1. Introduction",
            [
                Paragraph(
                    _escape(
                        "This Detailed Diagnostic Report consolidates inspection observations and thermal findings "
                        "from the submitted documents into a structured client-ready summary."
                    ),
                    body_style,
                ),
                Paragraph(_escape(ddr.property_issue_summary), body_style),
            ],
            section_style,
        )
    )
    story.extend(
        _section_block(
            "2. General Information",
            [_general_information_table(metadata)],
            section_style,
        )
    )

    observation_blocks = []
    for index, section in enumerate(ddr.area_wise_observations, start=1):
        observation_blocks.append(Paragraph(_escape(f"3.{index} {section.title}"), subheading_style))
        for paragraph in _paragraphs_from_text(section.body, body_style, label_style, bullet_style):
            observation_blocks.append(paragraph)
        if section.images:
            observation_blocks.extend(_render_images(section.images[:2]))
        else:
            observation_blocks.append(Paragraph("Image Not Available", body_style))
        observation_blocks.append(Spacer(1, 0.1 * inch))
    story.extend(_section_block("3. Visual Observations And Readings", observation_blocks, section_style))

    story.extend(
        _section_block(
            "4. Analysis And Suggestions",
            [
                Paragraph("<b>Probable Root Cause</b>", label_style),
                Paragraph(_escape(ddr.probable_root_cause), body_style),
                Paragraph("<b>Severity Assessment</b>", label_style),
                Paragraph(_escape(ddr.severity_assessment), body_style),
                Paragraph("<b>Recommended Actions</b>", label_style),
                _bullet_list(ddr.recommended_actions, bullet_style),
            ],
            section_style,
        )
    )
    story.extend(_section_block("5. Additional Notes", [_bullet_list(ddr.additional_notes, bullet_style)], section_style))
    story.extend(
        _section_block(
            "6. Missing / Unclear Information",
            [_bullet_list(ddr.missing_or_unclear_information, bullet_style)],
            section_style,
        )
    )

    doc.build(story, onFirstPage=lambda c, d: _draw_cover_footer(c), onLaterPages=lambda c, d: _draw_page_frame(c, d, metadata))
    return buffer.getvalue()


def _section_block(title: str, content: list, heading_style: ParagraphStyle) -> list:
    heading = Paragraph(title, heading_style)
    return [heading, Spacer(1, 0.08 * inch), *content, Spacer(1, 0.18 * inch)]


def _paragraphs_from_text(
    text: str,
    body_style: ParagraphStyle,
    label_style: ParagraphStyle,
    bullet_style: ParagraphStyle,
) -> list:
    blocks = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("- "):
            blocks.append(Paragraph(_escape(line[2:]), bullet_style))
        elif ":" in line:
            label, value = line.split(":", 1)
            blocks.append(Paragraph(f"<b>{_escape(label)}:</b> {_escape(value.strip())}", body_style))
        else:
            blocks.append(Paragraph(_escape(line), body_style))
    return blocks


def _bullet_list(items: list[str], bullet_style: ParagraphStyle) -> ListFlowable:
    bullets = [ListItem(Paragraph(_escape(item), bullet_style)) for item in items]
    return ListFlowable(bullets, bulletType="bullet", start="circle", leftIndent=16)


def _render_images(images: list[ExtractedImage]) -> list:
    rows = []
    current_row = []
    for image in images:
        image_flowable = _image_flowable(image)
        if image_flowable:
            current_row.append(image_flowable)
    if not current_row:
        return []
    rows.append(current_row)
    table = Table(rows, colWidths=[2.45 * inch] * len(rows[0]))
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("BOX", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ]
        )
    )
    return [table]


def _image_flowable(image: ExtractedImage) -> Image | None:
    try:
        flowable = Image(BytesIO(image.bytes_data), width=2.35 * inch, height=1.8 * inch)
        return flowable
    except Exception:
        return None


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _extract_report_metadata(inspection_text: str) -> dict[str, str]:
    def capture(label: str) -> str:
        pattern = rf"{re.escape(label)}\s*:\s*(.*?)(?:\n|$)"
        match = re.search(pattern, inspection_text, flags=re.IGNORECASE)
        value = re.sub(r"\s+", " ", match.group(1)).strip() if match else ""
        return value or "Not Available"

    return {
        "prepared_for": capture("Customer Name"),
        "address": capture("Address"),
        "inspection_date": capture("Inspection Date and Time"),
        "prepared_by": capture("Inspected By"),
        "property_type": capture("Property Type"),
        "property_age": capture("Property Age (In years)"),
        "floors": capture("Floors"),
        "report_title": "Detailed Diagnostic Report",
    }


def _cover_page(metadata: dict[str, str], title_style: ParagraphStyle, body_style: ParagraphStyle) -> list:
    cover_blocks = [
        Spacer(1, 1.2 * inch),
        Paragraph(metadata["report_title"], title_style),
        Spacer(1, 0.2 * inch),
        Paragraph("Prepared from uploaded inspection and thermal assessment documents", body_style),
        Spacer(1, 0.5 * inch),
    ]
    cover_table = Table(
        [
            ["Prepared For", metadata["prepared_for"]],
            ["Address", metadata["address"]],
            ["Inspection Date", metadata["inspection_date"]],
            ["Prepared By", metadata["prepared_by"]],
            ["Property Type", metadata["property_type"]],
        ],
        colWidths=[1.7 * inch, 4.8 * inch],
    )
    cover_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    cover_blocks.append(cover_table)
    return cover_blocks


def _general_information_table(metadata: dict[str, str]) -> Table:
    table = Table(
        [
            ["Prepared For", metadata["prepared_for"]],
            ["Inspection Date", metadata["inspection_date"]],
            ["Prepared By", metadata["prepared_by"]],
            ["Property Type", metadata["property_type"]],
            ["Property Age", metadata["property_age"]],
            ["Floors", metadata["floors"]],
        ],
        colWidths=[1.8 * inch, 4.6 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF4F8")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C7D5E0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _draw_cover_footer(canvas) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawRightString(A4[0] - 40, 24, "Generated DDR")
    canvas.restoreState()


def _draw_page_frame(canvas, doc, metadata: dict[str, str]) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#163A5F"))
    canvas.setLineWidth(0.8)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(40, A4[1] - 28, metadata["report_title"])
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(A4[0] - 40, A4[1] - 28, metadata["address"][:60] or "Property")
    canvas.line(40, A4[1] - 34, A4[0] - 40, A4[1] - 34)

    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#4B5563"))
    canvas.drawString(40, 24, "Generated by Applied AI Builder")
    canvas.drawRightString(A4[0] - 40, 24, f"Page {doc.page}")
    canvas.restoreState()
