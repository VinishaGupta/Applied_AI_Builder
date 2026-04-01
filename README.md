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


