"""Resume Search Streamlit interface with a welcome-inspired visual style."""

from __future__ import annotations

import io
import streamlit as st

from backend import _prepare_export_data, load_resumes, search_resumes


def _parse_skills(skills_text: str) -> list:
    """Validate comma-separated skills with the backend helper."""
    if not skills_text.strip():
        return []
    from backend import _validate_skills
    return _validate_skills(skills_text)


def _render_results(results: dict) -> None:
    rows: list = results["results"]
    total: int = results["total_candidates"]
    skills_requested: list = results["skills_requested"]

    st.markdown("---")
    st.markdown("## Search results")
    st.caption(f"Showing {len(rows)} ranked candidates from {total:,} uploaded resumes.")
    if not rows:
        st.info("No matching resumes were found. Try broader keywords or fewer filters.")
        return

    top_score = max(float(row["score"]) for row in rows)
    average_score = sum(float(row["score"]) for row in rows) / len(rows)
    a, b, c = st.columns(3)
    a.metric("Candidates shortlisted", len(rows))
    b.metric("Top relevance score", f"{top_score:.1%}")
    c.metric("Average relevance score", f"{average_score:.1%}")
    st.caption("Scores represent text similarity to your search terms—not hiring probability or candidate quality.")

    overview = []
    for rank, row in enumerate(rows, start=1):
        overview.append({
            "Rank": rank,
            "Candidate": f"Candidate {row['original_index'] + 1}",
            "Category": row["category"] or "Not specified",
            "Relevance": f"{float(row['score']):.1%}",
            "Experience detected": f"{row['experience']} years" if row["experience"] is not None else "Not detected",
            "Skills matched": f"{len(row['matched_skills'])}/{len(skills_requested)}" if skills_requested else "Not specified",
        })
    with st.expander("Ranked overview", expanded=True):
        st.dataframe(overview, use_container_width=True, hide_index=True)

    st.markdown("### Candidate profiles")
    for rank, row in enumerate(rows, start=1):
        candidate = f"Candidate {row['original_index'] + 1}"
        score = float(row["score"])
        with st.expander(f"#{rank}  ·  {candidate}  ·  {score:.1%} relevance"):
            left, right = st.columns(2)
            with left:
                st.markdown("**Resume category**")
                st.write(row["category"] or "Not specified")
                st.markdown("**Detected experience**")
                st.write(f"{row['experience']} years" if row["experience"] is not None else "Not detected")
            with right:
                st.markdown("**Text relevance**")
                st.progress(max(0.0, min(1.0, score)))
                st.caption(f"{score:.1%} similarity score")
            if skills_requested:
                st.markdown("**Matching requested skills**")
                if row["matched_skills"]:
                    st.success(" · ".join(row["matched_skills"]))
                else:
                    st.write("No requested skills detected.")
                st.markdown("**Skills not detected**")
                if row["missing_skills"]:
                    st.warning(" · ".join(row["missing_skills"]))
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
        buffer: io.StringIO = io.StringIO()
        export_df.to_csv(buffer, index=False)
        st.download_button(
            "Download ranked results (CSV)",
            data=buffer.getvalue(),
            file_name="resume_search_results.csv",
            mime="text/csv",
            type="primary",
        )


def _main() -> None:
    st.set_page_config(
        page_title="Resume Search",
        page_icon="🔎",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
        .stApp { background: #f4f7fc; }
        .main .block-container { max-width: 1180px; padding-top: 1.4rem; padding-bottom: 3rem; }
        [data-testid="stSidebar"] { background: #101b31; }
        [data-testid="stSidebar"] * { color: #eef3ff; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #c7d3ee; }
        .brand-mark {
            display: flex; align-items: center; gap: 10px; padding: 8px 2px 20px;
            font-size: 1.25rem; font-weight: 800; color: white;
        }
        .brand-icon {
            display: inline-flex; align-items: center; justify-content: center;
            width: 38px; height: 38px; border-radius: 12px;
            background: linear-gradient(135deg, #4d6bff, #8c74ff);
            color: white; font-size: 1.2rem;
        }
        .brand-accent { color: #8ea6ff; }
        .side-note {
            border: 1px solid #34435f; background: #182641; border-radius: 12px;
            padding: 12px; color: #dbe5ff; font-size: .83rem; line-height: 1.5;
        }
        .hero {
            background: linear-gradient(125deg, #101b31 0%, #233b72 64%, #526fe2 100%);
            border-radius: 20px; padding: 1.8rem 2rem; color: white;
            margin-bottom: 1.6rem; box-shadow: 0 14px 35px rgba(25,43,91,.16);
        }
        .hero-kicker { color: #bdcaff; font-size: .76rem; font-weight: 750; letter-spacing: .13em; text-transform: uppercase; }
        .hero h1 { color: white; font-size: clamp(2rem, 4vw, 2.8rem); line-height: 1.12; letter-spacing: -.04em; margin: .45rem 0 .65rem; }
        .hero p { color: #e0e8ff; font-size: 1rem; line-height: 1.6; max-width: 730px; margin: 0; }
        div[data-testid="stFileUploader"] { background: white; border: 1px solid #dfe6f3; border-radius: 16px; padding: .8rem; }
        div[data-testid="stForm"] { background: white; border: 1px solid #dfe6f3; border-radius: 16px; padding: 1.2rem 1.3rem 1rem; box-shadow: 0 5px 18px rgba(22,35,70,.04); }
        div[data-testid="stMetric"] { background: white; border: 1px solid #dfe6f3; border-radius: 14px; padding: 1rem; }
        div.stButton > button, div.stFormSubmitButton > button, div.stDownloadButton > button { border-radius: 10px; font-weight: 650; min-height: 2.7rem; }
        div[data-testid="stExpander"] { background: white; border: 1px solid #dfe6f3; border-radius: 13px; overflow: hidden; }
        div[data-testid="stProgress"] > div > div { background: linear-gradient(90deg, #4865d8, #8295f4); }
        .small-note { color: #68758d; font-size: .92rem; }
        .footer-note { color: #7b869b; text-align: center; font-size: .82rem; padding-top: 1.8rem; }
        @media (max-width: 700px) {
            .main .block-container { padding: 1rem .8rem 2rem; }
            .hero { padding: 1.35rem 1.15rem; border-radius: 15px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(
            '<div class="brand-mark"><span class="brand-icon">⌕</span><span>Resume <span class="brand-accent">Search</span></span></div>',
            unsafe_allow_html=True,
        )
        st.markdown("### Workspace")
        st.markdown("🏠  **Home**")
        st.markdown("📄  Upload Resumes")
        st.markdown("🔎  Search Candidates")
        st.markdown("---")
        st.markdown(
            '<div class="side-note"><b>Simple. Focused. Useful.</b><br>Find relevant resumes, review the evidence, and export your shortlist.</div>',
            unsafe_allow_html=True,
        )
        st.caption("Prototype · CSV-based search")

    st.markdown(
        """
        <div class="hero">
          <div class="hero-kicker">Candidate discovery workspace</div>
          <h1>Find the right talent,<br>faster.</h1>
          <p>Upload your resume dataset, search by role and skills, and review ranked matches in one simple workspace.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## 1. Upload resumes")
    st.markdown(
        '<p class="small-note">Drag and drop your CSV file below. Your file should contain a resume-text column; Category is optional.</p>',
        unsafe_allow_html=True,
    )
    uploaded_file = st.file_uploader(
        "Drag and drop your resume CSV here, or browse files",
        type=["csv"],
        max_upload_size=1024,
        help="Configured upload limit: 1 GB. Very large datasets may still require substantial memory and processing time.",
    )
    if uploaded_file is not None:
        st.success(f"Dataset ready: {uploaded_file.name} · {uploaded_file.size / (1024 * 1024):.1f} MB")
        st.caption("Supported resume-text columns: Resume_str, Resume, ResumeText, Text, Content.")

    st.markdown("## 2. Search resumes")
    with st.form("search_form", clear_on_submit=False):
        role_col, exp_col, limit_col = st.columns([2, 1, 1])
        with role_col:
            job_title = st.selectbox(
                "Choose a job role *",
                [
                    "Software Engineer", "Python Developer", "Java Developer",
                    "Frontend Developer", "Backend Developer", "Full Stack Developer",
                    "Data Analyst", "Data Scientist", "Machine Learning Engineer",
                    "AI Engineer", "DevOps Engineer", "Cybersecurity Analyst",
                    "Web Developer", "Mobile App Developer", "UI / UX Designer",
                    "QA / Test Engineer", "Other / custom role",
                ],
            )
        with exp_col:
            min_experience = st.selectbox(
                "Minimum experience",
                options=["Any experience", "1 year", "2 years", "3 years", "5 years", "7 years", "10 years"],
                index=0,
                help="Unknown experience is excluded when a minimum is selected.",
            )
        with limit_col:
            results_limit = st.selectbox("Candidates to show", options=[5, 10, 25], index=1)
        skill_options = [
            "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#",
            "HTML", "CSS", "React", "Angular", "Node.js", "Django", "Flask",
            "SQL", "MySQL", "PostgreSQL", "MongoDB", "Excel", "Power BI",
            "Pandas", "NumPy", "Machine Learning", "Deep Learning", "AI",
            "TensorFlow", "PyTorch", "Git", "GitHub", "Docker", "AWS",
            "Azure", "Linux", "Cybersecurity", "Networking", "REST API",
            "Figma", "UI/UX", "Selenium", "Testing", "Communication",
        ]
        selected_skills = st.multiselect(
            "Choose skills / programming languages (optional)",
            options=skill_options,
            placeholder="Select one or more skills",
        )
        custom_skills_text = st.text_input(
            "Other skills (optional)",
            placeholder="Add skills not listed, separated by commas",
        )
        submitted = st.form_submit_button("Search resumes", type="primary", use_container_width=True)

    st.caption("* Required field. Search scores measure text relevance and do not make hiring decisions.")

    if submitted:
        if uploaded_file is None:
            st.error("Please upload a resume CSV before searching.")
            return
        if not job_title.strip():
            st.error("Enter a job title or role to start the search.")
            return
        try:
            extra_skills = _parse_skills(custom_skills_text)
            skills = list(dict.fromkeys(selected_skills + extra_skills))
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
                st.error("Something went wrong while processing this dataset. Check the CSV and available memory, then try again.")

    st.markdown(
        '<div class="footer-note">Resume Search · Review resume evidence carefully. Automated relevance scores should support—not replace—human judgment.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    _main()
