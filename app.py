from __future__ import annotations

from pathlib import Path

import streamlit as st

from extractor import extract_report_asset
from pdf_export import build_ddr_pdf
from report_generator import build_ddr_report


st.set_page_config(page_title="AI DDR Generator", layout="wide")

st.title("AI Workflow Assignment Guide")
st.caption("Upload the inspection and thermal reports to generate a DDR draft.")

PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLE_INSPECTION = PROJECT_ROOT / "Sample Report.pdf"
SAMPLE_THERMAL = PROJECT_ROOT / "Thermal Images.pdf"
REFERENCE_DDR = PROJECT_ROOT / "Main DDR.pdf"

with st.sidebar:
    st.header("How It Works")
    st.write("1. Upload both PDFs.")
    st.write("2. Extract text and images.")
    st.write("3. Merge findings into a DDR.")
    st.write("4. Review and export the output.")


inspection_file = st.file_uploader("Upload Inspection Report PDF", type=["pdf"])
thermal_file = st.file_uploader("Upload Thermal Report PDF", type=["pdf"])


def load_workspace_pdf(path: Path):
    if path.exists():
        return path.name, path.read_bytes()
    return None, None


def as_markdown_report(ddr) -> str:
    lines = [
        "# Detailed Diagnostic Report",
        "",
        "## Property Issue Summary",
        ddr.property_issue_summary,
        "",
        "## Area-wise Observations",
    ]
    for section in ddr.area_wise_observations:
        lines.extend(
            [
                f"### {section.title}",
                section.body,
                "",
            ]
        )
    lines.extend(
        [
            "## Probable Root Cause",
            ddr.probable_root_cause,
            "",
            "## Severity Assessment",
            ddr.severity_assessment,
            "",
            "## Recommended Actions",
        ]
    )
    lines.extend(f"- {action}" for action in ddr.recommended_actions)
    lines.extend(["", "## Additional Notes"])
    lines.extend(f"- {note}" for note in ddr.additional_notes)
    lines.extend(["", "## Missing / Unclear Information"])
    lines.extend(f"- {item}" for item in ddr.missing_or_unclear_information)
    return "\n".join(lines)


def render_section(title: str, body: str) -> None:
    st.subheader(title)
    st.markdown(body.replace("\n", "  \n"))


sample_mode = st.checkbox("Use bundled sample PDFs from the project folder", value=False)

inspection_name = inspection_file.name if inspection_file else None
inspection_bytes = inspection_file.read() if inspection_file else None
thermal_name = thermal_file.name if thermal_file else None
thermal_bytes = thermal_file.read() if thermal_file else None

if sample_mode:
    if not inspection_bytes:
        inspection_name, inspection_bytes = load_workspace_pdf(SAMPLE_INSPECTION)
    if not thermal_bytes:
        thermal_name, thermal_bytes = load_workspace_pdf(SAMPLE_THERMAL)

reference_name, reference_bytes = load_workspace_pdf(REFERENCE_DDR)

if inspection_bytes and thermal_bytes:
    source_label = "bundled sample PDFs" if sample_mode and not inspection_file and not thermal_file else "uploaded PDFs"
    st.caption(f"Using {source_label} for this run.")
    if st.button("Generate DDR Report", type="primary"):
        with st.spinner("Extracting report data and generating DDR..."):
            inspection_asset = extract_report_asset(inspection_name or "Inspection Report.pdf", inspection_bytes)
            thermal_asset = extract_report_asset(thermal_name or "Thermal Report.pdf", thermal_bytes)
            reference_asset = (
                extract_report_asset(reference_name or "Main DDR.pdf", reference_bytes)
                if reference_bytes
                else None
            )
            ddr = build_ddr_report(inspection_asset, thermal_asset, reference_asset)
            markdown_output = as_markdown_report(ddr)
            pdf_output = build_ddr_pdf(ddr, inspection_asset, thermal_asset)

        st.success("DDR report generated.")

        st.header("Property Issue Summary")
        st.write(ddr.property_issue_summary)

        st.header("Area-wise Observations")
        for section in ddr.area_wise_observations:
            render_section(section.title, section.body)
            if section.images:
                image_columns = st.columns(min(2, len(section.images)))
                for index, image in enumerate(section.images[:2]):
                    with image_columns[index]:
                        st.image(
                            image.bytes_data,
                            caption=image.caption or f"{section.title} reference",
                            use_container_width=True,
                        )
            else:
                st.caption("Image Not Available")

        st.header("Probable Root Cause")
        st.write(ddr.probable_root_cause)

        st.header("Severity Assessment")
        st.write(ddr.severity_assessment)

        st.header("Recommended Actions")
        for action in ddr.recommended_actions:
            st.write(f"- {action}")

        st.header("Additional Notes")
        for note in ddr.additional_notes:
            st.write(f"- {note}")

        st.header("Missing / Unclear Information")
        for item in ddr.missing_or_unclear_information:
            st.write(f"- {item}")

        st.download_button(
            "Download DDR as Markdown",
            data=markdown_output,
            file_name="generated_ddr.md",
            mime="text/markdown",
        )
        st.download_button(
            "Download DDR as PDF",
            data=pdf_output,
            file_name="generated_ddr.pdf",
            mime="application/pdf",
        )
else:
    st.info("Upload both PDFs to begin. If you want a demo run, enable sample mode to use the bundled assignment files.")
