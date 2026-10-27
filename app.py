"""Resume Search Streamlit interface with a welcome-inspired visual style."""

from __future__ import annotations

import io
import streamlit as st

from backend import _prepare_export_data, load_resumes, search_resumes
from ai_features import GeminiConfigurationError, analyze_resume, analyze_skill_gap, generate_job_description


def _parse_skills(skills_text: str) -> list:
    """Validate comma-separated skills with the backend helper."""
    if not skills_text.strip():
        return []
    from backend import _validate_skills
    return _validate_skills(skills_text)


def _render_results(results: dict) -> None:
    """Render ranked candidates in a polished, evidence-first results workspace."""
    from html import escape

    rows: list = results["results"]
    total: int = results["total_candidates"]
    skills_requested: list = results["skills_requested"]

    st.markdown(
        """
        <div class="section-heading">
          <div class="section-eyebrow">MATCHING REPORT</div>
          <h2>Candidate shortlist</h2>
          <p>Ranked by text relevance to your selected role and skills.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Showing {len(rows)} ranked candidates from {total:,} uploaded resumes.")
    if not rows:
        st.info("No matching resumes were found. Try broader keywords or fewer filters.")
        return

    top_score = max(float(row["score"]) for row in rows)
    average_score = sum(float(row["score"]) for row in rows) / len(rows)
    a, b, c = st.columns(3)
    a.metric("Shortlisted", f"{len(rows):,}", help="Candidates returned by the current search.")
    b.metric("Top relevance", f"{top_score:.1%}", help="Highest text-similarity score in this shortlist.")
    c.metric("Average relevance", f"{average_score:.1%}", help="Mean text-similarity score for the displayed candidates.")
    st.caption("Relevance is text similarity—not hiring probability, candidate quality, or a recommendation to hire.")

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
    with st.expander("View ranked table", expanded=False):
        st.dataframe(overview, use_container_width=True, hide_index=True)

    st.markdown("### Ranked candidates")
    for rank, row in enumerate(rows, start=1):
        candidate = f"Candidate {row['original_index'] + 1}"
        score = max(0.0, min(1.0, float(row["score"])))
        category = escape(str(row["category"] or "Not specified"))
        experience = f"{row['experience']} years" if row["experience"] is not None else "Not detected"
        skills_summary = (
            f"{len(row['matched_skills'])} of {len(skills_requested)} requested skills detected"
            if skills_requested else "No required skills filter"
        )
        st.markdown(
            f"""
            <div class="candidate-card">
              <div class="candidate-card-top">
                <div class="candidate-rank">#{rank:02d}</div>
                <div class="candidate-identity">
                  <div class="candidate-name">{escape(candidate)}</div>
                  <div class="candidate-meta">{category} <span class="meta-dot">•</span> {escape(experience)}</div>
                </div>
                <div class="score-badge">{score:.1%}<span> match</span></div>
              </div>
              <div class="candidate-progress"><span style="width:{score * 100:.2f}%"></span></div>
              <div class="candidate-footnote">{escape(skills_summary)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        left, right = st.columns([1, 1], gap="large")
        with left:
            st.markdown("**Matching requested skills**")
            if skills_requested and row["matched_skills"]:
                st.markdown(
                    " ".join(f'<span class="skill-chip">{escape(str(skill))}</span>' for skill in row["matched_skills"]),
                    unsafe_allow_html=True,
                )
            elif skills_requested:
                st.write("No requested skills detected.")
            else:
                st.caption("Add skills to your search to see skill-level matches.")
        with right:
            if skills_requested:
                st.markdown("**Skills not detected**")
                if row["missing_skills"]:
                    st.markdown(
                        " ".join(f'<span class="skill-chip skill-chip-muted">{escape(str(skill))}</span>' for skill in row["missing_skills"]),
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("All requested skills were detected in the text.")
            else:
                st.markdown("**Candidate category**")
                st.write(row["category"] or "Not specified")
        with st.expander(f"Review resume text · {candidate}", expanded=False):
            st.text_area(
                "Resume content",
                value=str(row["resume_text"]),
                key=f"resume_{row['original_index']}",
                height=180,
                label_visibility="collapsed",
                disabled=True,
            )
        st.markdown('<div class="candidate-divider"></div>', unsafe_allow_html=True)

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
        :root {
          --rs-navy: #142b59;
          --rs-navy-deep: #0e1c38;
          --rs-blue: #3156a6;
          --rs-sky: #edf5ff;
          --rs-border: #cbd7ea;
          --rs-text: #172642;
          --rs-muted: #66758e;
          --rs-surface: #ffffff;
        }
        .stApp { background: #f6f8fc; color: var(--rs-text); }
        .main .block-container { max-width: 1320px; padding: 1.5rem 2rem 3rem; }
        [data-testid="stSidebar"] { background: var(--rs-navy-deep); border-right: 1px solid #263b62; }
        [data-testid="stSidebar"] * { color: #eef3ff; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #c5d2ec; }
        [data-testid="stSidebar"] button { border-color: #41557a !important; }
        .brand-mark { display:flex; align-items:center; gap:10px; padding:8px 2px 22px; font-size:1.22rem; font-weight:800; color:#fff; }
        .brand-icon { display:inline-flex; align-items:center; justify-content:center; width:38px; height:38px; border-radius:12px; background:#fff; color:var(--rs-navy) !important; font-size:1.25rem; }
        .brand-accent { color:#9eb8ff; }
        .side-note { border:1px solid #344766; background:#152744; border-radius:14px; padding:13px; color:#dbe5ff; font-size:.83rem; line-height:1.55; }
        .hero { background:linear-gradient(115deg,#101e3a 0%,#1b3569 68%,#3156a6 100%); border:1px solid #294578; border-radius:22px; padding:2rem 2.2rem; color:#fff; margin:0 0 2rem; box-shadow:0 16px 38px rgba(20,43,89,.12); }
        .hero-kicker,.section-eyebrow { color:#b9ccff; font-size:.72rem; font-weight:800; letter-spacing:.15em; text-transform:uppercase; }
        .hero h1 { color:#fff; font-size:clamp(2.1rem,4vw,3.1rem); line-height:1.08; letter-spacing:-.045em; margin:.65rem 0 .8rem; }
        .hero p { color:#e1eaff; font-size:1rem; line-height:1.7; max-width:760px; margin:0; }
        .section-heading { margin:.3rem 0 1rem; }
        .section-heading .section-eyebrow { color:#4969a8; margin-bottom:.35rem; }
        .section-heading h2 { color:var(--rs-navy); font-size:1.65rem; letter-spacing:-.025em; margin:0 0 .25rem; }
        .section-heading p { color:var(--rs-muted); margin:0; }
        h2,h3 { color:var(--rs-navy); letter-spacing:-.02em; }
        p,.stCaption { color:var(--rs-muted); }
        div[data-testid="stForm"] { background:#fff !important; border:1px solid var(--rs-border) !important; border-radius:20px !important; padding:1.3rem 1.4rem 1.1rem !important; box-shadow:0 8px 24px rgba(20,43,89,.045) !important; }
        div[data-testid="stFileUploader"] { background:transparent !important; border:1.5px dashed #8299bf !important; border-radius:18px !important; padding:1rem !important; }
        div[data-testid="stFileUploader"] section { background:#fff !important; border:0 !important; border-radius:12px !important; }
        div[data-testid="stMetric"] { background:#fff !important; border:1px solid #d7e0ef !important; border-radius:16px !important; padding:1rem 1.1rem !important; box-shadow:0 6px 20px rgba(20,43,89,.035) !important; }
        div[data-testid="stMetricLabel"] { color:#66758e !important; font-weight:650; }
        div[data-testid="stMetricValue"] { color:var(--rs-navy) !important; font-weight:800; }
        div[data-testid="stExpander"] { background:#fff !important; border:1px solid #d7e0ef !important; border-radius:14px !important; overflow:hidden; }
        div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input, div[data-testid="stSelectbox"] [data-baseweb="select"] > div { background:#fff !important; color:var(--rs-text) !important; border:1px solid #c8d4e7 !important; border-radius:11px !important; min-height:2.7rem; }
        div[data-testid="stMultiSelect"] [data-baseweb="select"] > div { background:var(--rs-sky) !important; color:var(--rs-text) !important; border:1px solid #9bb5dc !important; border-radius:12px !important; min-height:2.8rem; }
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] { background:var(--rs-navy) !important; border:1px solid var(--rs-navy) !important; border-radius:999px !important; }
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] * { color:#fff !important; fill:#fff !important; }
        div.stButton > button, div.stFormSubmitButton > button, div.stDownloadButton > button { border:1px solid #b8c8e0 !important; border-radius:11px !important; font-weight:700; min-height:2.75rem; box-shadow:none !important; }
        div.stFormSubmitButton > button[kind="primary"], div.stDownloadButton > button[kind="primary"] { background:var(--rs-navy) !important; color:#fff !important; border-color:var(--rs-navy) !important; }
        div.stButton > button:hover, div.stFormSubmitButton > button:hover, div.stDownloadButton > button:hover { border-color:var(--rs-blue) !important; color:var(--rs-blue) !important; }
        .candidate-card { border:1px solid #cbd7ea; border-radius:17px; background:#fff; padding:1.15rem 1.25rem .95rem; margin:.8rem 0 .65rem; box-shadow:0 7px 22px rgba(20,43,89,.045); }
        .candidate-card-top { display:flex; align-items:center; gap:14px; }
        .candidate-rank { display:flex; align-items:center; justify-content:center; flex:0 0 44px; height:44px; border-radius:13px; background:#edf3ff; color:var(--rs-navy); font-size:.95rem; font-weight:850; }
        .candidate-identity { min-width:0; flex:1; }
        .candidate-name { color:var(--rs-navy); font-size:1.08rem; font-weight:800; }
        .candidate-meta { color:#66758e; font-size:.85rem; margin-top:3px; }
        .meta-dot { padding:0 5px; color:#9aa9c1; }
        .score-badge { white-space:nowrap; background:#edf5ff; border:1px solid #c7d9f5; color:var(--rs-navy); padding:8px 11px; border-radius:12px; font-weight:850; }
        .score-badge span { font-size:.72rem; font-weight:650; }
        .candidate-progress { height:5px; background:#e9eef7; border-radius:99px; overflow:hidden; margin:1rem 0 .7rem; }
        .candidate-progress span { display:block; height:100%; border-radius:99px; background:linear-gradient(90deg,#18396f,#527ac0); }
        .candidate-footnote { color:#66758e; font-size:.8rem; }
        .skill-chip { display:inline-block; background:#142b59; color:#fff; border:1px solid #142b59; border-radius:999px; padding:4px 10px; margin:0 5px 5px 0; font-size:.78rem; font-weight:650; }
        .skill-chip-muted { background:#f2f5fa; color:#52617b; border-color:#d8e0ec; }
        .candidate-divider { height:1px; background:#e3e9f3; margin:1.2rem 0; }
        div[data-testid="stProgress"] > div > div { background:linear-gradient(90deg,#18396f,#547dbb); }
        .small-note { color:#66758e; font-size:.93rem; }
        .footer-note { color:#7b869b; text-align:center; font-size:.82rem; padding-top:1.8rem; }
        @media(max-width:800px) { .main .block-container { padding:1rem .8rem 2rem; } .hero { padding:1.4rem; border-radius:16px; } .candidate-card { padding:1rem; } .score-badge { padding:6px 8px; } }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Real local SQLite account authentication.
    from auth import authenticate_user, initialize_auth_db, register_user
    initialize_auth_db()

    if "resume_search_signed_in" not in st.session_state:
        st.session_state["resume_search_signed_in"] = False

    if not st.session_state["resume_search_signed_in"]:
        st.markdown(
            """
            <style>
            .main .block-container { max-width: 1240px; padding-top: 2rem; padding-bottom: 1.5rem; }
            [data-testid="stSidebar"] { display: none; }
            .login-brand-panel { min-height: 590px; padding: 2.5rem 2rem; border-radius: 24px; background: linear-gradient(145deg,#101b31 0%,#243c75 62%,#526fe2 100%); color: white; display:flex; flex-direction:column; justify-content:center; }
            .login-logo { display:inline-flex; align-items:center; justify-content:center; width:54px; height:54px; border-radius:16px; background:linear-gradient(135deg,#4d6bff,#8c74ff); color:#fff; font-size:1.65rem; font-weight:800; margin-bottom:1.7rem; }
            .login-eyebrow { color:#c3d0ff; text-transform:uppercase; letter-spacing:.15em; font-weight:800; font-size:.75rem; }
            .login-title { font-size:clamp(2.4rem,4vw,3.8rem); line-height:1.05; letter-spacing:-.05em; color:#fff; font-weight:850; margin:.7rem 0 1rem; }
            .login-copy { color:#e0e8ff; font-size:1.03rem; line-height:1.75; }
            .login-benefit { color:#f0f3ff; font-size:.94rem; margin-top:1.15rem; }
            .login-heading { color:#14213b; font-size:2rem; font-weight:800; letter-spacing:-.04em; margin:.5rem 0 .2rem; }
            .login-muted { color:#71809a; font-size:.94rem; margin-bottom:1.3rem; }
            div[data-testid="stForm"] { background:#fff; border:1px solid #e1e7f2; border-radius:20px; padding:1.25rem 1.35rem; box-shadow:0 18px 48px rgba(30,48,90,.07); }
            div.stButton > button, div.stFormSubmitButton > button { min-height:2.8rem; border-radius:10px; font-weight:700; }
            .login-foot { color:#8a95a8; text-align:center; font-size:.8rem; margin-top:1.2rem; }
            @media(max-width:760px) { .login-brand-panel { min-height:unset; padding:1.5rem; margin-bottom:1rem; } .login-title { font-size:2.4rem; } }
            </style>
            """,
            unsafe_allow_html=True,
        )
        brand_col, form_col = st.columns([1, 1], gap="large", vertical_alignment="center")
        with brand_col:
            st.markdown(
                """
                <div class="login-brand-panel">
                  <div class="login-logo">⌕</div>
                  <div class="login-eyebrow">Smarter candidate discovery</div>
                  <div class="login-title">RESUME<br>SEARCH</div>
                  <p class="login-copy">Find talent. See the fit. Search resumes, compare relevant skills, and build a shortlist with more clarity.</p>
                  <p class="login-benefit">✓ &nbsp; Skill-aware resume matching</p>
                  <p class="login-benefit">✓ &nbsp; Ranked candidate insights</p>
                  <p class="login-benefit">✓ &nbsp; Optional AI-assisted analysis</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with form_col:
            st.markdown('<div class="login-heading">Welcome back</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-muted">Sign in or create an account to continue.</div>', unsafe_allow_html=True)
            login_mode = st.radio("Account access", ["Sign in", "Create account"], horizontal=True, label_visibility="collapsed", key="login_mode")
            with st.form("resume_search_auth_form", clear_on_submit=False):
                login_email = st.text_input("Email address", placeholder="you@company.com")
                login_password = st.text_input("Password", type="password", placeholder="At least 8 characters" if login_mode == "Create account" else "Enter your password")
                login_role = st.selectbox("I am a", ["Recruiter", "Job seeker"])
                auth_submit = st.form_submit_button("Create account" if login_mode == "Create account" else "Sign in", type="primary", use_container_width=True)
            if auth_submit:
                try:
                    if login_mode == "Create account":
                        register_user(login_email, login_password, login_role)
                        st.success("Account created. You are now signed in.")
                        user = authenticate_user(login_email, login_password)
                    else:
                        user = authenticate_user(login_email, login_password)
                        if user is None:
                            st.error("Email or password is incorrect.")
                    if user is not None:
                        if user["role"] != login_role:
                            st.warning(f"This account is registered as {user['role']}. Select that account type to continue.")
                        else:
                            st.session_state["resume_search_signed_in"] = True
                            st.session_state["resume_search_user_id"] = user["id"]
                            st.session_state["resume_search_email"] = user["email"]
                            st.session_state["resume_search_role"] = user["role"]
                            st.rerun()
                except ValueError as error:
                    st.error(str(error))
                except Exception:
                    st.error("Authentication could not be completed. Check local database access and try again.")
            st.markdown('<div class="login-foot">Resume Search · Secure password hashing · Local account database</div>', unsafe_allow_html=True)
        return

    # Signed-in prototype controls
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
        st.markdown("---")
        st.caption(f"Signed in as {st.session_state.get('resume_search_role', 'User')}")
        if st.button("Sign out", use_container_width=True):
            st.session_state["resume_search_signed_in"] = False
            st.session_state.pop("resume_search_email", None)
            st.session_state.pop("resume_search_role", None)
            st.session_state.pop("resume_search_user_id", None)
            st.rerun()

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
            selected_role = st.selectbox(
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
            if selected_role == "Other / custom role":
                job_title = st.text_input("Enter your job role *", placeholder="e.g. Embedded Systems Engineer")
            else:
                job_title = selected_role
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

    # Optional Gemini tools run only after an explicit button click.
    st.markdown("---")
    st.markdown("## 3. Gemini AI tools")
    st.caption("Optional AI tools for recruiters and job seekers. Resume text is sent to Google Gemini only when you run an AI action.")
    if uploaded_file is not None:
        try:
            ai_df = load_resumes(uploaded_file.getvalue(), uploaded_file.name)
            from backend import _find_resume_column
            resume_column = _find_resume_column(ai_df)
            candidate_index = st.selectbox("Select a resume for AI analysis", options=list(range(len(ai_df))), format_func=lambda idx: f"Candidate {idx + 1}", key="ai_candidate_index")
            ai_resume_text = str(ai_df.iloc[candidate_index][resume_column] or "")
            tab_profile, tab_gap, tab_jd = st.tabs(["Resume Intelligence", "Skill Gap Analyzer", "Job Description Generator"])
            with tab_profile:
                st.write("Extract a structured profile grounded in one resume.")
                if st.button("Analyze selected resume", key="ai_analyze_resume", type="primary"):
                    with st.spinner("Analyzing one resume with Gemini…"):
                        try:
                            st.session_state["ai_resume_profile"] = analyze_resume(ai_resume_text)
                        except (GeminiConfigurationError, ValueError, RuntimeError) as error:
                            st.error(str(error))
                        except Exception:
                            st.error("Gemini request failed. Check your API key, connection, and free-tier quota.")
                if "ai_resume_profile" in st.session_state:
                    st.json(st.session_state["ai_resume_profile"])
            with tab_gap:
                gap_description = st.text_area("Paste the target job description", height=170, key="ai_gap_description")
                if st.button("Analyze skill gaps", key="ai_analyze_gap", type="primary"):
                    with st.spinner("Comparing one resume with the job description…"):
                        try:
                            st.session_state["ai_skill_gap"] = analyze_skill_gap(ai_resume_text, gap_description)
                        except (GeminiConfigurationError, ValueError, RuntimeError) as error:
                            st.error(str(error))
                        except Exception:
                            st.error("Gemini request failed. Check your API key, connection, and free-tier quota.")
                if "ai_skill_gap" in st.session_state:
                    st.json(st.session_state["ai_skill_gap"])
            with tab_jd:
                jd_title = st.text_input("Job title", key="ai_jd_title", placeholder="e.g. Junior Python Developer")
                jd_skills = st.text_input("Required skills (comma-separated)", key="ai_jd_skills", placeholder="Python, SQL, Git")
                left, right = st.columns(2)
                with left:
                    jd_level = st.selectbox("Experience level", ["Entry level", "Junior", "Mid-level", "Senior", "Internship"], key="ai_jd_level")
                with right:
                    jd_type = st.selectbox("Employment type", ["Full-time", "Part-time", "Internship", "Contract", "Temporary"], key="ai_jd_type")
                jd_context = st.text_area("Additional context (optional)", key="ai_jd_context", height=90)
                if st.button("Generate job description", key="ai_generate_jd", type="primary"):
                    with st.spinner("Drafting a job description with Gemini…"):
                        try:
                            st.session_state["ai_job_description"] = generate_job_description(jd_title, [item.strip() for item in jd_skills.split(",") if item.strip()], jd_level, jd_type, jd_context)
                        except (GeminiConfigurationError, ValueError, RuntimeError) as error:
                            st.error(str(error))
                        except Exception:
                            st.error("Gemini request failed. Check your API key, connection, and free-tier quota.")
                if "ai_job_description" in st.session_state:
                    import json
                    jd_result = st.session_state["ai_job_description"]
                    st.json(jd_result)
                    st.download_button("Download job description (JSON)", data=json.dumps(jd_result, indent=2, ensure_ascii=False), file_name="generated_job_description.json", mime="application/json", key="ai_jd_download")
        except ValueError as error:
            st.error(f"Could not prepare AI tools: {error}")
        st.caption("AI output can be incorrect. Verify details, do not use it as the sole basis for hiring decisions, and upload resumes only when you have permission.")
    else:
        st.info("Upload a CSV above to enable the Gemini AI tools.")

    st.markdown(
        '<div class="footer-note">Resume Search · Review resume evidence carefully. Automated relevance scores should support—not replace—human judgment.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    _main()
