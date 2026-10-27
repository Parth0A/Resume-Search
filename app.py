"""Polished Streamlit interface for Resume Search.

UI and application wiring live here; matching and data processing stay in backend.py.
"""

from __future__ import annotations

import html
import io

import streamlit as st

from backend import _prepare_export_data, load_resumes, search_resumes


def _safe(value: object) -> str:
    """Escape values before inserting them into small HTML UI elements."""
    return html.escape(str(value))


def _render_results(results: dict) -> None:
    """Render ranked candidates, skill evidence, and CSV export."""
    rows: list = results["results"]
    total: int = results["total_candidates"]
    skills_requested: list = results["skills_requested"]
    min_experience: int | None = results["min_experience"]

    st.markdown("---")
    st.markdown("## Search results")
    st.caption(f"Showing {len(rows)} ranked candidates from {total:,} uploaded resumes.")

    if not rows:
        st.info("No matching resumes were found. Try broader keywords or fewer filters.")
        return

    top_score = max(float(row["score"]) for row in rows)
    average_score = sum(float(row["score"]) for row in rows) / len(rows)
    first_col, second_col, third_col = st.columns(3)
    first_col.metric("Candidates shortlisted", f"{len(rows):,}")
    second_col.metric("Top relevance score", f"{top_score:.1%}")
    third_col.metric("Average relevance score", f"{average_score:.1%}")
    st.caption(
        "Relevance scores show text similarity to your search terms. They are not "
        "a hiring probability or a validated measure of candidate quality."
    )

    overview = []
    for rank, row in enumerate(rows, start=1):
        overview.append({
            "Rank": rank,
            "Candidate": f"Candidate {row['original_index'] + 1}",
            "Category": row["category"] or "Not specified",
            "Relevance": f"{float(row['score']):.1%}",
            "Experience detected": (
                f"{row['experience']} years" if row["experience"] is not None else "Not detected"
            ),
            "Skills matched": f"{len(row['matched_skills'])}/{len(skills_requested)}"
            if skills_requested else "Not specified",
        })

    with st.expander("View ranked overview", expanded=True):
        st.dataframe(overview, use_container_width=True, hide_index=True)

    st.markdown("### Candidate profiles")
    st.caption("Expand a candidate to review the resume text and matching evidence.")
    for rank, row in enumerate(rows, start=1):
        candidate = f"Candidate {row['original_index'] + 1}"
        score = float(row["score"])
        with st.expander(f"#{rank}  ·  {candidate}  ·  {score:.1%} relevance"):
            left, right = st.columns([1, 1])
            with left:
                st.markdown("**Resume category**")
                st.write(row["category"] or "Not specified")
                st.markdown("**Detected experience**")
                st.write(
                    f"{row['experience']} years"
                    if row["experience"] is not None else "Not detected"
                )
            with right:
                st.markdown("**Text relevance**")
                st.progress(max(0.0, min(1.0, score)))
                st.caption(f"{score:.1%} similarity score")

            if skills_requested:
                matched = row["matched_skills"]
                missing = row["missing_skills"]
                st.markdown("**Matching requested skills**")
                if matched:
                    st.success(" · ".join(matched))
                else:
                    st.write("No requested skills detected.")
                st.markdown("**Skills not detected**")
                if missing:
                    st.warning(" · ".join(missing))
                else:
                    st.write("All requested skills were detected in the text.")

            st.markdown("**Resume text**")
            st.text_area(
                "Resume content",
                value=row["resume_text"],
                key=f"resume_{row['original_index']}",
                height=180,
                label_visibility="collapsed",
                disabled=True,
            )

    export_df = _prepare_export_data(rows, total)
    if not export_df.empty:
        csv_buffer: io.StringIO = io.StringIO()
        export_df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="Download ranked results (CSV)",
            data=csv_buffer.getvalue(),
            file_name="resume_search_results.csv",
            mime="text/csv",
            type="primary",
        )


def _parse_skills(skills_text: str) -> list:
    """Use backend validation for comma-separated skills."""
    if not skills_text.strip():
        return []
    from backend import _validate_skills
    return _validate_skills(skills_text)


def _main() -> None:
    """Run the Resume Search application."""
    st.set_page_config(
        page_title="Resume Search",
        page_icon="🔎",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown(
        """
        <style>
        :root { color-scheme: light; }
        .stApp { background: #f5f7fb; }
        .main .block-container {
            max-width: 1180px;
            padding-top: 1.6rem;
            padding-bottom: 3rem;
        }
        [data-testid="stHeader"] { background: rgba(245,247,251,.9); }
        .hero {
            background: linear-gradient(125deg, #101b3d 0%, #243d79 62%, #526de0 100%);
            border-radius: 22px;
            padding: 2rem 2.1rem;
            color: white;
            margin-bottom: 1.15rem;
            box-shadow: 0 14px 35px rgba(26,43,91,.16);
        }
        .hero-kicker {
            color: #bfcaff;
            font-size: .78rem;
            font-weight: 700;
            letter-spacing: .14em;
            text-transform: uppercase;
            margin-bottom: .6rem;
        }
        .hero h1 {
            color: white;
            font-size: clamp(2rem, 4vw, 3rem);
            line-height: 1.1;
            letter-spacing: -.04em;
            margin: 0 0 .7rem 0;
        }
        .hero p {
            color: #e0e7ff;
            font-size: 1.02rem;
            line-height: 1.65;
            max-width: 700px;
            margin: 0;
        }
        div[data-testid="stForm"], div[data-testid="stFileUploader"] {
            border-radius: 16px;
        }
        div[data-testid="stForm"] {
            background: white;
            border: 1px solid #e4e9f3;
            padding: 1.25rem 1.3rem 1rem 1.3rem;
            box-shadow: 0 5px 18px rgba(22,35,70,.045);
        }
        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid #e4e9f3;
            border-radius: 14px;
            padding: 1rem 1.1rem;
        }
        div[data-testid="stMetricLabel"] { color: #58647b; }
        div.stButton > button, div.stFormSubmitButton > button,
        div.stDownloadButton > button {
            border-radius: 10px;
            font-weight: 650;
            min-height: 2.75rem;
        }
        div[data-testid="stExpander"] {
            background: white;
            border: 1px solid #e4e9f3;
            border-radius: 13px;
            overflow: hidden;
        }
        div[data-testid="stProgress"] > div > div {
            background: linear-gradient(90deg, #4865d8, #7b8ff2);
        }
        .section-note { color: #66728a; font-size: .94rem; }
        .footer-note {
            color: #7a8498;
            text-align: center;
            font-size: .82rem;
            padding-top: 1.5rem;
        }
        @media (max-width: 700px) {
            .main .block-container { padding: 1rem .8rem 2rem .8rem; }
            .hero { padding: 1.5rem 1.2rem; border-radius: 16px; }
        }
        </style>
        <div class="hero">
            <div class="hero-kicker">Candidate discovery workspace</div>
            <h1>Find the right resume.<br>Faster.</h1>
            <p>Search your resume dataset by role, skills, and experience. Review ranked results
            with clear evidence before making your own decisions.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## 1 · Upload your dataset")
    st.markdown(
        '<p class="section-note">Start with a CSV file containing resume text. '
        'A <code>Category</code> column is optional.</p>',
        unsafe_allow_html=True,
    )
    uploaded_file = st.file_uploader(
        "Choose a resume CSV",
        type=["csv"],
        max_upload_size=1024,
        help=(
            "Configured upload limit: 1 GB. Very large datasets may still require "
            "substantial memory and processing time."
        ),
    )
    if uploaded_file is not None:
        st.success(f"Ready to search: {uploaded_file.name} · {uploaded_file.size / (1024 * 1024):.1f} MB")
        st.caption("Resume text columns supported: Resume_str, Resume, ResumeText, Text, Content.")

    st.markdown("## 2 · Define your search")
    with st.form("search_form", clear_on_submit=False):
        role_col, experience_col, limit_col = st.columns([2, 1, 1])
        with role_col:
            job_title = st.text_input(
                "Job title or role *",
                placeholder="e.g. Software Engineer",
                help="Required. Use a clear job title to rank relevant resume text.",
            )
        with experience_col:
            min_experience = st.selectbox(
                "Minimum experience",
                options=["Any experience", "1 year", "2 years", "3 years", "5 years", "7 years", "10 years"],
                index=0,
                help="Unknown experience is excluded when a minimum is selected.",
            )
        with limit_col:
            results_limit = st.selectbox("Candidates to show", options=[5, 10, 25], index=1)

        skills_text = st.text_input(
            "Required skills",
            placeholder="Python, SQL, Git",
            help="Optional. Separate skills with commas.",
        )
        submitted = st.form_submit_button("Search resumes", type="primary", use_container_width=True)

    st.caption("* Required field. This prototype ranks text relevance; it does not make hiring decisions.")

    if submitted:
        if uploaded_file is None:
            st.error("Please upload a resume CSV before searching.")
            return
        if not job_title.strip():
            st.error("Enter a job title or role to start the search.")
            return

        try:
            skills = _parse_skills(skills_text)
            experience_value: int | None = None
            if min_experience != "Any experience":
                experience_value = int(min_experience.split()[0])
        except (ValueError, TypeError) as error:
            st.error(str(error) or "Please check your search criteria.")
            return

        with st.spinner("Reading resumes and ranking matches…"):
            try:
                df = load_resumes(uploaded_file.getvalue(), uploaded_file.name)
                results = search_resumes(
                    df=df,
                    job_title=job_title.strip(),
                    skills=skills,
                    min_experience=experience_value,
                    limit=int(results_limit),
                )
                _render_results(results)
            except ValueError as error:
                st.error(f"Could not complete the search: {error}")
            except Exception:
                st.error(
                    "Something went wrong while processing this dataset. Check that the CSV "
                    "is valid and that enough memory is available, then try again."
                )

    st.markdown(
        '<div class="footer-note">Resume Search · Review resume evidence carefully. '
        'Automated relevance scores should support—not replace—human judgment.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    _main()
