"""Resume Search Streamlit interface with a welcome-inspired visual style."""

from __future__ import annotations

import io
import time
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

    # Real local SQLite account authentication.
    from auth import authenticate_user, get_user_by_id, initialize_auth_db, register_user
    initialize_auth_db()

    # Streamlit session state is not an authentication database. Revalidate each
    # rerun and expire inactive sessions after 30 minutes.
    session_now = time.time()
    session_user_id = st.session_state.get("resume_search_user_id")
    session_expires_at = st.session_state.get("resume_search_expires_at", 0)
    if st.session_state.get("resume_search_signed_in"):
        if not session_user_id or session_now >= session_expires_at:
            st.session_state["resume_search_signed_in"] = False
        else:
            current_user = get_user_by_id(session_user_id)
            if current_user is None:
                st.session_state["resume_search_signed_in"] = False
            else:
                st.session_state["resume_search_email"] = current_user["email"]
                st.session_state["resume_search_role"] = current_user["role"]
                st.session_state["resume_search_expires_at"] = session_now + 1800

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
                            st.session_state["resume_search_expires_at"] = time.time() + 1800
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
            st.session_state.pop("resume_search_expires_at", None)
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
        max_upload_size=25,
        help="Maximum upload size: 25 MB. Use a smaller CSV if your dataset is larger.",
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
