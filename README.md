# Resume Search

A Streamlit application for searching and ranking resumes from a CSV dataset using text
relevance matching with TF-IDF and cosine similarity.

## Access

- **PowerShell:** `.\start_app.bat`
- **Manual (PowerShell):** `.\\.venv\Scripts\Activate.ps1; python -m streamlit run app.py`
- **Manual (cmd):** `call .venv\Scripts\activate.bat && python -m streamlit run app.py`

The application opens at `http://localhost:8501`.

If PowerShell script execution is blocked, use the included batch launcher instead:

```powershell
start_app.bat
```

Or run the venv Python directly:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Dataset

Upload a CSV file through the interface. The application supports the Kaggle Resume
Dataset format with a resume-text column named `Resume_str` and an optional `Category`
column.

Dataset source: https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset

If your CSV uses a different resume-text column name, the application will try common
alternatives automatically.

## How matching works

The application builds a search query from the job title and any supplied skills, then
compares it with each resume using TF-IDF vectorization and cosine similarity.

The match score represents algorithmic text relevance only. It is not a hiring
probability, a validated measure of candidate quality, or proof that a candidate is
qualified.

If skills are provided, the application reports which requested skills were detected in
each resume and which were not.

## Experience extraction

Experience is extracted conservatively from resume text. Only clearly interpretable
evidence is recognized. Graduation years, project durations, training periods, and
unrelated numbers are intentionally ignored.

If no reliable evidence is found, the result shows `Not detected`. When a minimum
experience filter is applied, candidates with unknown experience are excluded rather
than treated as meeting the requirement.

## Testing

```powershell
python -m pytest -q
```

## Limitations

- Text-based matching cannot detect synonyms, abbreviations, or skills expressed in
  unusual ways.
- Simple word-boundary matching reduces obvious substring errors but does not eliminate
  all of them.
- Experience extraction is heuristic and limited.
- Results depend entirely on the uploaded dataset.

## Troubleshooting

- If the app does not start, confirm the virtual environment was created and the
  dependencies installed successfully.
- If a CSV upload fails, check that the file contains a resume-text column with usable
  text and that it is a valid CSV.
- If scores look unusual, confirm that the job title and skills are meaningful search
  terms and that the uploaded resumes contain usable text.
