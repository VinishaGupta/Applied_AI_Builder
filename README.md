# Applied AI Builder DDR Generator

Turn an `Inspection Report` + `Thermal Report` into a client-ready DDR (Detailed Diagnostic Report) with structured findings, mapped images, and exportable PDF output.

## What This Project Does

- 📄 Extracts text and relevant visuals from inspection and thermal PDFs
- 🧠 Merges both sources into area-wise findings
- ⚠️ Flags missing details with `Not Available`
- 🔍 Surfaces simple conflict cases for manual review
- 🖼️ Places related images under the matching observation sections
- 📘 Exports a branded DDR as PDF
- 🌐 Provides a simple Streamlit interface for upload and generation
- 🤖 Optionally uses OpenAI when `OPENAI_API_KEY` is available

## DDR Output Includes

- 1. Property Issue Summary
- 2. Area-wise Observations
- 3. Probable Root Cause
- 4. Severity Assessment
- 5. Recommended Actions
- 6. Additional Notes
- 7. Missing / Unclear Information

## Project Files

- `app.py` - Streamlit UI
- `extractor.py` - PDF text and image extraction
- `models.py` - Pydantic data models
- `report_generator.py` - finding extraction, merging, and DDR content generation
- `pdf_export.py` - branded PDF rendering
- `requirements.txt` - Python dependencies

## Design Assets

- `logo.png` - header logo used in the PDF
- `A4 - 1.png` - custom front cover page
- `A4 - 2.png` - custom intro/about page

## Run Locally

Use your Windows virtual environment Python directly if needed:

```powershell
C:\venvs\applied_ai_builder\Scripts\python.exe -m pip install -r requirements.txt
C:\venvs\applied_ai_builder\Scripts\python.exe -m streamlit run app.py
```

Then open the local Streamlit URL, usually:

```text
http://localhost:8501
```

## How To Use

- 1. Upload the inspection PDF
- 2. Upload the thermal PDF
- 3. Click `Generate DDR Report`
- 4. Review the generated report in the app
- 5. Download the final PDF

## Live Demo

- 🚀 Streamlit App: `https://appliedaibuildergit-tyb7f8ctl4sfid2fim8wqo.streamlit.app/`

## Notes

- ✅ The app works without OpenAI using heuristic extraction and merge logic.
- ✅ The final PDF includes custom front pages, branded footer, TOC, image index, and DDR sections.
- ⚠️ Conflict detection is rule-based, not fully semantic.
- ⚠️ Image-to-section matching is approximate and works best on reports similar to the provided samples.
- ⚠️ `Prepared For` may appear as `Not Available` if the source PDFs do not actually contain a client name.

## Submission Tips

- 🎥 Record a 3-5 minute Loom showing:
  what you built, how it works, limitations, and next improvements
- 📁 Put your repo link, screenshots, demo output, and Loom link in one Google Drive folder
- 🧪 Include at least one generated DDR PDF in the submission folder

## Nice Next Improvements

- Better conflict detection across inspection vs thermal evidence
- More accurate image-to-observation matching
- Stronger generalization across different report templates
- Optional DOCX / JSON exports
- Better audit trail for extracted evidence
