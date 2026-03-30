from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from models import DDRReport, ExtractedImage
from models import ReportAsset


PROJECT_ROOT = Path(__file__).resolve().parent
LOGO_PATH = PROJECT_ROOT / "logo.png"


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
    story.extend(_toc_page(ddr, section_style, body_style))
    story.append(PageBreak())
    story.extend(_images_index_page(ddr, section_style, body_style))
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


def _toc_page(ddr: DDRReport, section_style: ParagraphStyle, body_style: ParagraphStyle) -> list:
    items = [
        ("SECTION 1 INTRODUCTION", "4"),
        ("SECTION 2 GENERAL INFORMATION", "4"),
        ("SECTION 3 VISUAL OBSERVATIONS AND READINGS", "5"),
        ("SECTION 4 ANALYSIS AND SUGGESTIONS", "6"),
        ("SECTION 5 ADDITIONAL NOTES", "6"),
        ("SECTION 6 MISSING / UNCLEAR INFORMATION", "7"),
        ("IMAGES", "3"),
    ]
    blocks = [
        Paragraph("Table of Content", section_style),
        Spacer(1, 0.12 * inch),
    ]
    for title, page_no in items:
        blocks.append(Paragraph(_toc_line(title, page_no), body_style))
        if "VISUAL OBSERVATIONS" in title:
            for index, section in enumerate(ddr.area_wise_observations, start=1):
                blocks.append(Paragraph(_toc_line(f"3.{index} {section.title}", "5"), _small_toc_style()))
    return blocks


def _images_index_page(ddr: DDRReport, section_style: ParagraphStyle, body_style: ParagraphStyle) -> list:
    blocks = [
        Paragraph("Images", section_style),
        Spacer(1, 0.12 * inch),
    ]
    image_counter = 1
    for section in ddr.area_wise_observations:
        if not section.images:
            continue
        caption = _image_index_caption(section.title, section.body)
        blocks.append(Paragraph(_toc_line(f"IMAGE {image_counter}: {caption}", "5"), body_style))
        image_counter += 1
    if image_counter == 1:
        blocks.append(Paragraph("Image index not available.", body_style))
    return blocks


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


def _small_toc_style() -> ParagraphStyle:
    styles = getSampleStyleSheet()
    return ParagraphStyle(
        "SmallTOC",
        parent=styles["BodyText"],
        fontSize=9,
        leading=11,
        leftIndent=18,
        spaceAfter=4,
    )


def _draw_cover_footer(canvas) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawRightString(A4[0] - 40, 24, "Generated DDR")
    canvas.restoreState()


def _draw_page_frame(canvas, doc, metadata: dict[str, str]) -> None:
    canvas.saveState()
    _draw_header_logo(canvas)
    canvas.setStrokeColor(colors.HexColor("#D5DCE3"))
    canvas.setLineWidth(0.8)
    canvas.line(40, A4[1] - 48, A4[0] - 40, A4[1] - 48)

    footer_y = 24
    canvas.setStrokeColor(colors.HexColor("#D5DCE3"))
    canvas.line(40, 36, A4[0] - 40, 36)
    canvas.setFillColor(colors.blue)
    canvas.setFont("Helvetica-Oblique", 11)
    canvas.drawString(40, footer_y, "www.urbaroof.in")

    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.setFont("Times-BoldItalic", 12)
    canvas.drawCentredString((A4[0] / 2) - 18, footer_y, "UrbanRoof Private Limited")

    canvas.setFillColor(colors.HexColor("#4B4B4B"))
    canvas.setFont("Helvetica", 11)
    canvas.drawRightString(A4[0] - 52, footer_y, "Page")
    canvas.setFont("Helvetica", 15)
    canvas.drawRightString(A4[0] - 40, footer_y, str(doc.page))
    canvas.restoreState()


def _draw_header_logo(canvas) -> None:
    if LOGO_PATH.exists():
        try:
            canvas.drawImage(
                str(LOGO_PATH),
                40,
                A4[1] - 48,
                width=130,
                height=34,
                preserveAspectRatio=True,
                mask="auto",
            )
            return
        except Exception:
            pass

    icon_x = 44
    icon_y = A4[1] - 26
    canvas.setLineWidth(12)
    canvas.setLineCap(1)
    canvas.setStrokeColor(colors.HexColor("#F6A127"))
    canvas.line(icon_x, icon_y, icon_x + 18, icon_y + 18)
    canvas.line(icon_x + 18, icon_y + 18, icon_x + 38, icon_y - 2)
    canvas.line(icon_x + 10, icon_y - 10, icon_x + 28, icon_y + 8)
    canvas.line(icon_x + 28, icon_y + 8, icon_x + 48, icon_y - 12)

    canvas.setFillColor(colors.HexColor("#2F2F35"))
    canvas.setFont("Helvetica-Bold", 20)
    canvas.drawString(102, A4[1] - 34, "UrbanRoof")


def _toc_line(title: str, page_no: str) -> str:
    clean_title = _escape(title.upper())
    dots = "." * max(10, 120 - len(title))
    return f"{clean_title}{dots}{page_no}"


def _image_index_caption(title: str, body: str) -> str:
    observation = title
    for line in body.splitlines():
        if line.lower().startswith("observation:"):
            observation = line.split(":", 1)[1].strip()
            break
    return observation.upper()
