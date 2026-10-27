"""Streamlit interface for Resume Search.

This file contains only the user interface and application wiring. All business
logic lives in backend.py.
"""

from __future__ import annotations

import io

import streamlit as st

from backend import load_resumes
from backend import search_resumes
from backend import _prepare_export_data


def _render_results(results: dict) -> None:
    """Display ranked results, details, and a CSV download option."""
    rows: list = results["results"]
    total: int = results["total_candidates"]
    skills_requested: list = results["skills_requested"]
    min_experience: int | None = results["min_experience"]

    if not rows:
        st.info("No matching resumes were found for the current search.")
        return

    st.markdown("### Ranked Candidates")
    st.caption(f"Showing {len(rows)} of {total} uploaded resumes.")

    display_rows: list = []
    for row in rows:
        display_rows.append({
            "Candidate": f"Candidate {row['original_index'] + 1}",
            "Category": row["category"] or "Not specified",
            "Match Score": f"{row['score']:.4f}",
            "Experience": row["experience"] if row["experience"] is not None else "Not detected",
            "Matching Skills": ", ".join(row["matched_skills"]) if row["matched_skills"] else "None",
            "Missing Skills": ", ".join(row["missing_skills"]) if row["missing_skills"] else "None",
        })

    st.table(display_rows)

    st.markdown("### Resume Details")
    for row in rows:
        candidate_label: str = f"Candidate {row['original_index'] + 1}"
        score_text: str = f"Match Score: {row['score']:.4f}"
        st.markdown(f"**{candidate_label}**  {score_text}")
        st.text_area(
            "Resume Text",
            value=row["resume_text"],
            key=f"resume_{row['original_index']}",
            height=140,
        )

        if skills_requested:
            matched: str = ", ".join(row["matched_skills"]) if row["matched_skills"] else "None"
            missing: str = ", ".join(row["missing_skills"]) if row["missing_skills"] else "None"
            st.caption(f"Matching requested skills: {matched}")
            st.caption(f"Missing requested skills: {missing}")

        if min_experience is not None:
            st.caption(
                "Detected experience: "
                + (str(row["experience"]) if row["experience"] is not None else "Not detected")
            )

    export_df = _prepare_export_data(rows, total)
    if not export_df.empty:
        csv_buffer: io.StringIO = io.StringIO()
        export_df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="Download Ranked Results as CSV",
            data=csv_buffer.getvalue(),
            file_name="resume_search_results.csv",
            mime="text/csv",
        )


def _main() -> None:
    """Run the Streamlit application."""
    st.set_page_config(page_title="Resume Search", layout="wide")

    st.markdown(
        """
        <style>
        .main .block-container { padding-top: 1.5rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("Resume Search")
    st.caption(
        "Upload a resume dataset and search for candidates by job title, skills, "
        "and minimum experience."
    )

    st.markdown(
        """
        Match scores represent algorithmic text relevance only. They are **not** a
        hiring probability, a validated measure of candidate quality, or proof that a
        candidate is qualified.
        """,
        help="How to interpret match scores",
    )

    # Dataset upload
    with st.expander("Upload Resume Dataset", expanded=False):
        uploaded_file = st.file_uploader(
            "Upload CSV",
            type=["csv"],
            help="Upload a CSV containing a resume-text column (for example, "
                 "`Resume_str`) and an optional `Category` column.",
        )

        if uploaded_file is not None:
            st.success("Dataset uploaded. You can now run a search.")
            st.caption("Supported column names: Resume_str, Resume, ResumeText, Text, Content.")

    # Search form
    with st.form("search_form", clear_on_submit=False):
        st.markdown("#### Search Criteria")
        job_title = st.text_input(
            "Job Title",
            placeholder="e.g. Software Engineer",
            help="Required. Enter the role you are searching for.",
        )
        min_experience = st.selectbox(
            "Minimum Experience",
            options=["Any experience", "1 year", "2 years", "3 years", "5 years", "7 years", "10 years"],
            index=0,
            help="Optional. Candidates with unknown experience are excluded when a minimum is selected.",
        )
        skills_text = st.text_input(
            "Required Skills",
            placeholder="e.g. Python, SQL, Git",
            help="Optional. Enter skills as a comma-separated list.",
        )
        results_limit = st.selectbox(
            "Number of Results",
            options=[5, 10, 25],
            index=1,
        )

        submitted = st.form_submit_button("Search Resumes", type="primary")

    if submitted:
        if uploaded_file is None:
            st.error("Please upload a resume dataset before searching.")
            return

        if not job_title.strip():
            st.error("Job title is required.")
            return

        skills: list = []
        skills_error: str | None = None
        try:
            skills = _parse_skills(skills_text)
        except ValueError as error:
            skills_error = str(error)

        experience_value: int | None = None
        if min_experience != "Any experience":
            try:
                experience_value = int(min_experience.split()[0])
            except (ValueError, TypeError):
                st.error("Invalid minimum experience selection.")
                return

        if skills_error:
            st.error(skills_error)
            return

        with st.spinner("Matching resumes..."):
            try:
                file_bytes: bytes = uploaded_file.getvalue()
                df = load_resumes(file_bytes, uploaded_file.name)
                results = search_resumes(
                    df=df,
                    job_title=job_title.strip(),
                    skills=skills,
                    min_experience=experience_value,
                    limit=int(results_limit),
                )
                _render_results(results)
            except ValueError as error:
                st.error(f"Search failed: {error}")
            except Exception as error:
                st.error("An unexpected error occurred during the search.")
                st.exception(error)


def _parse_skills(skills_text: str) -> list:
    """Parse comma-separated skills for the UI form.

    This is a thin UI-side helper that delegates validation to the backend where
    possible. It is used only to surface user-facing errors before the search runs.
    """
    if not skills_text.strip():
        return []

    from backend import _validate_skills

    return _validate_skills(skills_text)


if __name__ == "__main__":
    _main()
