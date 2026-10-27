"""Business logic for Resume Search.

The backend is independent of Streamlit and contains all data processing,
matching, ranking, and export preparation logic.
"""

from __future__ import annotations

import re
from typing import List
from typing import Optional

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

REQUIRED_TEXT_COLUMN_ALT_NAMES: List[str] = ["Resume_str", "Resume", "ResumeText", "Text", "Content"]
"""Preferred and alternative resume-text column names the backend will accept."""

CATEGORY_COLUMN_NAME: str = "Category"
"""Optional category column name."""

DEFAULT_RESULTS_LIMIT: int = 10
"""Fallback limit when no limit is provided."""

SUPPORTED_EXPERIENCE_UNITS: List[str] = ["year", "years", "yr", "yrs"]
"""Time units treated as years of experience for conservative extraction."""

MIN_FILE_SIZE_BYTES: int = 1
"""Minimum acceptable file size in bytes."""

MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024
"""Reasonable maximum upload size in bytes (50 MB)."""


def _normalize_text(text: str) -> str:
    """Normalize text for matching.

    Lowercases the text, collapses whitespace, and strips surrounding whitespace.
    Non-string inputs are converted to an empty string.
    """
    if not isinstance(text, str):
        return ""
    normalized: str = re.sub(r"\s+", " ", text.lower().strip())
    return normalized


def _extract_skills(resume_text: str, skill_list: List[str]) -> List[str]:
    """Return the requested skills detected in a normalized resume.

    Matching uses a simple word-boundary check to reduce trivial substring errors
    such as matching ``Java`` inside ``JavaScript``. The method is conservative
    and does not detect synonyms, abbreviations, or skills phrased differently.
    """
    normalized_resume: str = _normalize_text(resume_text)
    found: List[str] = []
    seen: set = set()

    for raw_skill in skill_list:
        skill: str = raw_skill.strip()
        if not skill:
            continue
        normalized_skill: str = _normalize_text(skill)
        if not normalized_skill or normalized_skill in seen:
            continue
        seen.add(normalized_skill)

        # Word-boundary pattern reduces substring false positives.
        pattern: str = r"(?<![a-z0-9])" + re.escape(normalized_skill) + r"(?![a-z0-9])"
        if re.search(pattern, normalized_resume):
            found.append(skill)

    return found


def _extract_experience(resume_text: str) -> Optional[int]:
    """Extract a conservative estimate of years of experience from resume text.

    The function looks for phrases such as ``X years of experience``,
    ``X years experience``, ``X year experience``, or ``X yrs experience``.
    It deliberately avoids interpreting every number followed by ``years``,
    so graduation dates, project durations, and unrelated numbers are usually
    ignored.

    Returns ``None`` when no reliable evidence is found.
    """
    if not isinstance(resume_text, str):
        return None

    normalized: str = _normalize_text(resume_text)        # Look for an explicit experience phrase rather than any number + years.
    patterns: List[str] = [
        r"(?<!\w)(\d{1,2})\s*(years?|yrs?)\s*(of\s*)?experience\b",
        r"(?<!\w)(\d{1,2})\s*(years?|yrs?)\s*experience\b",
        r"(?<!\w)(\d{1,2})\s*year\s*experience\b",
    ]

    best: Optional[int] = None
    for pattern in patterns:
        for match in re.finditer(pattern, normalized):
            try:
                value: int = int(match.group(1))
                if value <= 0:
                    continue
                if best is None or value > best:
                    best = value
            except (ValueError, TypeError):
                continue

    return best


def _validate_job_title(job_title: str) -> str:
    """Validate and normalize a job title.

    Raises ``ValueError`` when the job title is blank or contains no usable words.
    """
    normalized: str = _normalize_text(job_title)
    if not normalized:
        raise ValueError("Job title is required and cannot be blank.")
    if not re.search(r"\w", normalized):
        raise ValueError("Job title must contain at least one usable word.")
    return normalized


def _validate_skills(skills_text: str) -> List[str]:
    """Parse and validate a comma-separated skill list.

    Returns a deduplicated list of stripped, non-empty skills.
    Raises ``ValueError`` when any skill is blank after cleaning.
    """
    if not skills_text.strip():
        return []

    parsed: List[str] = []
    raw: List[str] = skills_text.split(",")

    for item in raw:
        cleaned: str = item.strip()
        if not cleaned:
            raise ValueError("Skill list contains a blank entry.")
        normalized: str = _normalize_text(cleaned)
        if not normalized:
            raise ValueError("Skill list contains a blank entry after normalization.")
        parsed.append(cleaned)

    # Deduplicate while preserving order and original casing for display.
    deduped: List[str] = []
    seen_normalized: set = set()
    for item in parsed:
        normalized: str = _normalize_text(item)
        if normalized not in seen_normalized:
            seen_normalized.add(normalized)
            deduped.append(item)

    return deduped


def _find_resume_column(df: pd.DataFrame) -> str:
    """Return the name of the resume-text column present in the dataframe.

    Raises ``ValueError`` when no supported resume-text column is found.
    """
    for column in REQUIRED_TEXT_COLUMN_ALT_NAMES:
        if column in df.columns:
            return column
    raise ValueError(
        "CSV is missing a supported resume-text column. Expected one of: "
        + ", ".join(REQUIRED_TEXT_COLUMN_ALT_NAMES)
    )


def _is_resume_text_usable(series: pd.Series) -> bool:
    """Return True when the series contains at least one non-blank resume text."""
    for value in series.astype(str):
        if re.search(r"\w", _normalize_text(value)):
            return True
    return False


def _build_search_query(job_title: str, skills: List[str]) -> str:
    """Build the normalized search representation from the job title and skills."""
    pieces: List[str] = [_validate_job_title(job_title)]
    for skill in skills:
        pieces.append(_normalize_text(skill))
    return " ".join(pieces)


def _rank_candidates(
    search_query: str,
    resume_texts: List[str],
    min_experience: Optional[int],
    detected_experience: List[Optional[int]],
    skills: List[str],
    resume_texts_raw: List[str],
    categories: List[Optional[str]],
    original_indices: List[int],
    limit: int,
) -> List[dict]:
    """Rank candidates by text relevance and return prepared result rows.

    The score is the cosine similarity between the TF-IDF representation of the
    search query and each resume. Results are sorted by descending score with a
    stable tie-break by original dataset position.
    """
    if not resume_texts:
        return []

    # Convert any non-string resume text safely.
    safe_texts: List[str] = [str(text) if text is not None else "" for text in resume_texts]

    try:
        vectorizer: TfidfVectorizer = TfidfVectorizer(
            lowercase=False,
            token_pattern=r"(?u)\b\w+\b",
            stop_words="english",
            max_df=1.0,
            min_df=1,
        )
        tfidf_matrix = vectorizer.fit_transform(safe_texts)
        query_vector = vectorizer.transform([search_query])
        similarities = cosine_similarity(query_vector, tfidf_matrix).flatten()
    except ValueError:
        # Empty vocabulary or text with no usable terms.
        return []

    rows: List[dict] = []
    for idx, similarity in enumerate(similarities):
        resume = safe_texts[idx]
        if not re.search(r"\w", resume):
            continue

        score: float = float(similarity)

        experience = detected_experience[idx]
        if min_experience is not None and (experience is None or experience < min_experience):
            continue

        matched_skills: List[str] = _extract_skills(resume, skills) if skills else []
        missing_skills: List[str] = [s for s in skills if s not in matched_skills] if skills else []

        rows.append({
            "original_index": original_indices[idx],
            "resume_text": resume,
            "category": categories[idx],
            "score": score,
            "experience": experience,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
        })

    if not rows:
        return []

    rows.sort(key=lambda row: (-row["score"], row["original_index"]))
    return rows[:limit]


def _prepare_export_data(results: List[dict], total_candidates: int) -> pd.DataFrame:
    """Prepare a clean, exportable dataframe from ranked results.

    The export includes useful match information without duplicating the full
    dataset. Resume text is included for traceability.
    """
    if not results:
        return pd.DataFrame()

    records: List[dict] = []
    for result in results:
        records.append({
            "Candidate": f"Candidate {result['original_index'] + 1}",
            "Original Index": result["original_index"],
            "Category": result["category"] or "Not specified",
            "Match Score": round(result["score"], 4),
            "Detected Experience": result["experience"] if result["experience"] is not None else "Not detected",
            "Matching Skills": ", ".join(result["matched_skills"]) if result["matched_skills"] else "None",
            "Missing Skills": ", ".join(result["missing_skills"]) if result["missing_skills"] else "None",
            "Resume Text": result["resume_text"],
        })

    return pd.DataFrame(records, columns=list(records[0].keys()))


def load_resumes(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Load and validate a resume dataset CSV.

    Returns the validated dataframe. Raises ``ValueError`` for invalid or unusable
    datasets.
    """
    if not file_bytes or len(file_bytes) < MIN_FILE_SIZE_BYTES:
        raise ValueError("Uploaded file is empty.")

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            "Uploaded file exceeds the maximum allowed size of 50 MB."
        )

    try:
        df: pd.DataFrame = pd.read_csv(
            pd.io.common.BytesIO(file_bytes),
            dtype=str,
            on_bad_lines="skip",
        )
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(
                pd.io.common.BytesIO(file_bytes),
                dtype=str,
                encoding="latin-1",
                on_bad_lines="skip",
            )
        except Exception as read_error:
            raise ValueError(
                "Unable to read the uploaded CSV. It may be corrupted or use an "
                "unsupported encoding."
            ) from read_error
    except Exception as read_error:
        raise ValueError(
            "Unable to read the uploaded CSV. It may be malformed or unsupported."
        ) from read_error

    if df.empty:
        raise ValueError("The CSV file contains no rows.")

    resume_column: str = _find_resume_column(df)
    if not _is_resume_text_usable(df[resume_column]):
        raise ValueError(
            "The CSV contains a resume-text column, but every resume value is blank "
            "or lacks usable text."
        )

    return df


def search_resumes(
    df: pd.DataFrame,
    job_title: str,
    skills: List[str],
    min_experience: Optional[int],
    limit: int,
) -> dict:
    """Run a resume search against the provided dataset.

    Returns a dictionary with the ranked results and supporting information.
    Raises ``ValueError`` for invalid search input or matching failures.
    """
    if limit < 1:
        raise ValueError("Result limit must be at least 1.")

    search_query: str = _build_search_query(job_title, skills)

    resume_column: str = _find_resume_column(df)
    resume_texts_raw: List[str] = df[resume_column].fillna("").astype(str).tolist()

    category_column: Optional[str] = CATEGORY_COLUMN_NAME if CATEGORY_COLUMN_NAME in df.columns else None
    categories: List[Optional[str]] = (
        df[category_column].fillna("").astype(str).tolist() if category_column else ["Not specified"] * len(df)
    )

    original_indices: List[int] = list(range(len(df)))

    detected_experience: List[Optional[int]] = [
        _extract_experience(text) for text in resume_texts_raw
    ]

    results: List[dict] = _rank_candidates(
        search_query=search_query,
        resume_texts=resume_texts_raw,
        min_experience=min_experience,
        detected_experience=detected_experience,
        skills=skills,
        resume_texts_raw=resume_texts_raw,
        categories=categories,
        original_indices=original_indices,
        limit=limit,
    )

    total_candidates: int = len(df)

    return {
        "results": results,
        "total_candidates": total_candidates,
        "search_query": search_query,
        "skills_requested": skills,
        "min_experience": min_experience,
    }
