from __future__ import annotations

import streamlit as st

from extractor import extract_report_asset
from report_generator import build_ddr_report


st.set_page_config(page_title="AI DDR Generator", layout="wide")

st.title("AI Workflow Assignment Guide")
st.caption("Upload the inspection and thermal reports to generate a DDR draft.")

with st.sidebar:
    st.header("How It Works")
    st.write("1. Upload both PDFs.")
    st.write("2. Extract text and images.")
    st.write("3. Merge findings into a DDR.")
    st.write("4. Review and export the output.")


inspection_file = st.file_uploader("Upload Inspection Report PDF", type=["pdf"])
thermal_file = st.file_uploader("Upload Thermal Report PDF", type=["pdf"])


def render_section(title: str, body: str) -> None:
    st.subheader(title)
    st.markdown(body.replace("\n", "  \n"))


if inspection_file and thermal_file:
    if st.button("Generate DDR Report", type="primary"):
        with st.spinner("Extracting report data and generating DDR..."):
            inspection_asset = extract_report_asset(inspection_file.name, inspection_file.read())
            thermal_asset = extract_report_asset(thermal_file.name, thermal_file.read())
            ddr = build_ddr_report(inspection_asset, thermal_asset)

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
else:
    st.info("Add both PDFs to begin.")
