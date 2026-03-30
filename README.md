# Applied AI Builder Assignment

This project generates a draft DDR (Detailed Diagnostic Report) from:

- an inspection report PDF
- a thermal report PDF

## What it does

- extracts text and embedded images from both PDFs
- identifies issue-related observations
- merges inspection and thermal evidence into area-wise findings
- generates a DDR-style output in Streamlit
- optionally uses OpenAI when `OPENAI_API_KEY` is available

## Files

- `app.py`: Streamlit UI
- `extractor.py`: PDF text and image extraction
- `models.py`: Pydantic models
- `report_generator.py`: heuristic + optional LLM DDR generation

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notes

- The current version is designed as a solid first pass for the assignment.
- If no API key is provided, the app still works with heuristic extraction and merge logic.
- The next iteration should tune prompts and merge rules against the real sample PDFs:
  `Sample Report.pdf`, `Thermal Images.pdf`, and `Main DDR.pdf`.
