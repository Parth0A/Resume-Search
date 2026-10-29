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
        :root { --rs-navy: #142b59; --rs-navy-strong: #10234b; --rs-sky-soft: #edf6ff; --rs-border: #18396f; --rs-text: #172642; --rs-muted: #63718a; }
        .stApp { background: #f7f9fd; color: var(--rs-text); }
        .main .block-container { max-width: 1180px; padding-top: 1.4rem; padding-bottom: 3rem; }
        [data-testid="stSidebar"] { background: #101b31; }
        [data-testid="stSidebar"] * { color: #eef3ff; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #c7d3ee; }

        /* Clean outlined cards: no solid fill, navy border, rounded corners. */
        div[data-testid="stFileUploader"],
        div[data-testid="stForm"],
        div[data-testid="stMetric"],
        div[data-testid="stExpander"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: transparent !important;
            border: 1.5px solid var(--rs-border) !important;
            border-radius: 18px !important;
            box-shadow: none !important;
        }
        div[data-testid="stFileUploader"] { padding: .85rem; }
        div[data-testid="stForm"] { padding: 1.2rem 1.3rem 1rem; }
        div[data-testid="stMetric"] { padding: 1rem; }
        div[data-testid="stExpander"] { overflow: hidden; }
        /* Inputs remain easy to spot; only the skill search/input area gets a faint sky tint. */
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        div[data-testid="stFileUploader"] section {
            border: 1.5px solid var(--rs-border) !important;
            border-radius: 12px !important;
            box-shadow: none !important;
        }
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
            background: var(--rs-sky-soft) !important;
            border: 1.5px solid var(--rs-border) !important;
            border-radius: 13px !important;
            min-height: 2.8rem;
            box-shadow: none !important;
        }
        /* Selected skill chips: navy fill, white text, rounded edges. */
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] {
            background: var(--rs-navy) !important;
            border: 1px solid var(--rs-navy-strong) !important;
            border-radius: 999px !important;
            padding: 2px 5px;
        }
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] *,
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] span {
            color: #ffffff !important;
            fill: #ffffff !important;
        }
        div[data-testid="stMultiSelect"] input { background: transparent !important; }
        div.stButton > button, div.stFormSubmitButton > button, div.stDownloadButton > button {
            background: #142b59 !important;
            color: #ffffff !important;
            border: 1.5px solid #142b59 !important;
            border-radius: 12px !important;
            font-weight: 650;
            min-height: 2.7rem;
            box-shadow: none !important;
        }
        div.stButton > button:hover, div.stFormSubmitButton > button:hover, div.stDownloadButton > button:hover {
            background: #10234b !important;
            color: #ffffff !important;
            border-color: #10234b !important;
        }
        div.stFormSubmitButton > button[kind="primary"] {
            background: var(--rs-navy) !important;
            color: #ffffff !important;
        }
        div[data-testid="stProgress"] > div > div { background: linear-gradient(90deg, #18396f, #547dbb); }
        /* When Streamlit is in dark theme, use a black canvas and white controls/cards. */
        [data-theme="dark"] .stApp, html[data-theme="dark"] .stApp,
        [data-testid="stAppViewContainer"][data-theme="dark"] {
            background: #05070b !important;
            color: #f5f7fb !important;
        }
        [data-theme="dark"] div[data-testid="stFileUploader"],
        [data-theme="dark"] div[data-testid="stForm"],
        [data-theme="dark"] div[data-testid="stMetric"],
        [data-theme="dark"] div[data-testid="stExpander"],
        [data-theme="dark"] div[data-testid="stVerticalBlockBorderWrapper"],
        html[data-theme="dark"] div[data-testid="stFileUploader"],
        html[data-theme="dark"] div[data-testid="stForm"],
        html[data-theme="dark"] div[data-testid="stMetric"],
        html[data-theme="dark"] div[data-testid="stExpander"] {
            background: #ffffff !important;
            color: #172642 !important;
            border-color: #18396f !important;
        }
        [data-theme="dark"] div[data-testid="stFileUploader"] *,
        [data-theme="dark"] div[data-testid="stForm"] *,
        [data-theme="dark"] div[data-testid="stMetric"] *,
        [data-theme="dark"] div[data-testid="stExpander"] *,
        html[data-theme="dark"] div[data-testid="stFileUploader"] *,
        html[data-theme="dark"] div[data-testid="stForm"] *,
        html[data-theme="dark"] div[data-testid="stMetric"] *,
        html[data-theme="dark"] div[data-testid="stExpander"] * {
            color: #172642;
        }
        [data-theme="dark"] div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
        html[data-theme="dark"] div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
            background: #edf6ff !important;
            border-color: #18396f !important;
        }
        [data-theme="dark"] div[data-testid="stTextInput"] input,
        [data-theme="dark"] div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        html[data-theme="dark"] div[data-testid="stTextInput"] input,
        html[data-theme="dark"] div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            background: #ffffff !important;
            color: #172642 !important;
            border-color: #18396f !important;
        }
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
        /* Final override: keep search/upload panels transparent with navy outlines. */
        div[data-testid="stFileUploader"],
        div[data-testid="stForm"],
        div[data-testid="stMetric"],
        div[data-testid="stExpander"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: transparent !important;
            border: 1.5px solid #18396f !important;
            border-radius: 18px !important;
            box-shadow: none !important;
        }
        div[data-testid="stFileUploader"] section {
            background: transparent !important;
            border: 1.5px dashed #18396f !important;
            border-radius: 14px !important;
        }
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
            background: transparent !important;
            color: var(--rs-text) !important;
            border: 1.5px solid #18396f !important;
            border-radius: 12px !important;
        }
        div[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
            background: #edf6ff !important;
            color: #172642 !important;
            border: 1.5px solid #18396f !important;
            border-radius: 13px !important;
        }
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] {
            background: #142b59 !important;
            border: 1px solid #10234b !important;
            border-radius: 999px !important;
        }
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] *,
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] span {
            color: #ffffff !important;
            fill: #ffffff !important;
        }
        div[data-testid="stFileUploader"] button,
        div.stButton > button,
        div.stFormSubmitButton > button,
        div.stDownloadButton > button {
            border: 1.5px solid #18396f !important;
            border-radius: 12px !important;
            box-shadow: none !important;
        }
        /* Streamlit versions expose theme on different ancestor elements. */
        html[data-theme="dark"] .stApp,
        [data-testid="stAppViewContainer"][data-theme="dark"] .stApp,
        .stApp[data-theme="dark"] {
            background: #05070b !important;
            color: #f5f7fb !important;
        }
        html[data-theme="dark"] div[data-testid="stFileUploader"],
        html[data-theme="dark"] div[data-testid="stForm"],
        html[data-theme="dark"] div[data-testid="stMetric"],
        html[data-theme="dark"] div[data-testid="stExpander"],
        html[data-theme="dark"] div[data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stAppViewContainer"][data-theme="dark"] div[data-testid="stFileUploader"],
        [data-testid="stAppViewContainer"][data-theme="dark"] div[data-testid="stForm"],
        [data-testid="stAppViewContainer"][data-theme="dark"] div[data-testid="stMetric"],
        [data-testid="stAppViewContainer"][data-theme="dark"] div[data-testid="stExpander"] {
            background: #ffffff !important;
            color: #172642 !important;
            border-color: #18396f !important;
        }
        html[data-theme="dark"] div[data-testid="stTextInput"] input,
        html[data-theme="dark"] div[data-testid="stNumberInput"] input,
        html[data-theme="dark"] div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
            background: #ffffff !important;
            color: #172642 !important;
            border-color: #18396f !important;
        }
        html[data-theme="dark"] div[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
            background: #edf6ff !important;
            color: #172642 !important;
            border-color: #18396f !important;
        }
        .small-note { color: #68758d; font-size: .92rem; }
        .footer-note { color: #7b869b; text-align: center; font-size: .82rem; padding-top: 1.8rem; }
        @media (max-width: 700px) {
            .main .block-container { padding: 1rem .8rem 2rem; }
            .hero { padding: 1.35rem 1.15rem; border-radius: 15px; }
        }

        /* Restore the original navy-and-blue theme while keeping the current layout and profile option. */
        :root { --rs-navy: #142b59; --rs-navy-strong: #10234b; --rs-border: #18396f; }
        .stApp { background: #f7f9fd; color: #172642; }
        [data-testid="stSidebar"] { background: #101b31 !important; }
        [data-testid="stSidebar"] * { color: #eef3ff !important; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #c7d3ee !important; }
        .brand-icon { background: linear-gradient(135deg, #4d6bff, #8c74ff) !important; }
        .brand-accent { color: #8ea6ff !important; }
        .hero { background: linear-gradient(125deg, #101b31 0%, #233b72 64%, #526fe2 100%) !important; }
        .hero-kicker { color: #bdcaff !important; }
        div.stButton > button, div.stFormSubmitButton > button, div.stDownloadButton > button, div[data-testid="stFileUploader"] button {
            background: var(--rs-navy) !important; color: #ffffff !important; border: 1px solid var(--rs-navy-strong) !important;
            border-radius: 12px !important; font-weight: 700 !important; min-height: 2.8rem; box-shadow: none !important;
        }
        div.stButton > button:hover, div.stFormSubmitButton > button:hover, div.stDownloadButton > button:hover, div[data-testid="stFileUploader"] button:hover {
            background: var(--rs-navy-strong) !important; color: #ffffff !important;
        }
        div.stButton > button:focus, div.stFormSubmitButton > button:focus, div.stDownloadButton > button:focus { outline: 2px solid #8ea6ff !important; outline-offset: 2px !important; }
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] { background: var(--rs-navy) !important; border-color: var(--rs-navy-strong) !important; }
        div[data-testid="stProgress"] > div > div { background: linear-gradient(90deg, #18396f, #547dbb) !important; }
        .home-card-icon { font-size: 2.5rem; color: #ffffff; margin: .2rem 0 .9rem; }
        .home-card-title { color: #ffffff !important; font-size: 1.35rem; margin: 0 0 .7rem; }
        .home-card-copy { color: #e0e8ff !important; min-height: 5.5rem; line-height: 1.6; }
        [class*="st-key-home_card_"] { background: linear-gradient(135deg, #101b31, #233b72) !important; border: 1px solid #18396f !important; border-radius: 22px !important; padding: 1.5rem !important; min-height: 330px; }
        [class*="st-key-home_card_"] [data-testid="stMarkdownContainer"] p { color: #ffffff !important; }
        [class*="st-key-home_card_"] div.stButton > button { background: #142b59 !important; color: #ffffff !important; border: 1px solid #8ea6ff !important; border-radius: 999px !important; }
        [class*="st-key-home_card_"] div.stButton > button:hover { background: #10234b !important; color: #ffffff !important; }
        [data-testid="stFileUploader"], [data-testid="stForm"], [data-testid="stMetric"], [data-testid="stExpander"], [data-testid="stVerticalBlockBorderWrapper"] { border-color: #18396f !important; border-radius: 16px !important; }
        @media (max-width: 700px) {
            .main .block-container { padding: 1rem .8rem 2rem; }
            [class*="st-key-home_cards"] [data-testid="stHorizontalBlock"] { flex-direction: column !important; gap: 1rem !important; }
            [class*="st-key-home_cards"] [data-testid="stHorizontalBlock"] > [data-testid="column"] { width: 100% !important; min-width: 100% !important; flex: 1 1 100% !important; }
            [class*="st-key-home_card_"] { min-height: 250px; width: 100% !important; }
            .home-card-copy { min-height: 0; }
            .hero { padding: 1.35rem 1.15rem; border-radius: 15px; }
        }

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


    # Keep navigation state in the existing Streamlit session; no backend or data model changes.
    role = st.session_state.get("resume_search_role", "Recruiter")
    pages = ["Home", "Gemini AI", "Upload Dataset", "See Resumes", "Edit Profile", "Change Icon", "About This Project"]
    if role != "Job seeker":
        pages.append("Search Resume")
    if "resume_search_page" not in st.session_state:
        st.session_state["resume_search_page"] = "Home"
    if st.session_state["resume_search_page"] not in pages:
        st.session_state["resume_search_page"] = "Home"
    if "resume_dataset_bytes" not in st.session_state:
        st.session_state["resume_dataset_bytes"] = None
        st.session_state["resume_dataset_name"] = None
    if "resume_search_icon" not in st.session_state:
        st.session_state["resume_search_icon"] = "⌕"

    with st.sidebar:
        st.markdown(f'<div class="brand-mark"><span class="brand-icon">{st.session_state["resume_search_icon"]}</span><span>Resume <span class="brand-accent">Search</span></span></div>', unsafe_allow_html=True)
        st.caption(f"Signed in as {role}")
        st.markdown("### Workspace")
        nav_items = [("Home", "⌂"), ("Gemini AI", "✦"), ("Upload Dataset", "⇧"), ("See Resumes", "▤")]
        if role != "Job seeker":
            nav_items.append(("Search Resume", "⌕"))
        for page_name, page_icon in nav_items:
            if st.button(f"{page_icon}  {page_name}", key=f"nav_{page_name}", use_container_width=True):
                st.session_state["resume_search_page"] = page_name
                st.rerun()
        st.markdown("---")
        st.markdown("### Account")
        for page_name, page_icon in [("Edit Profile", "♙"), ("Change Icon", "✎"), ("About This Project", "ⓘ")]:
            if st.button(f"{page_icon}  {page_name}", key=f"nav_{page_name}", use_container_width=True):
                st.session_state["resume_search_page"] = page_name
                st.rerun()
        st.markdown("---")
        if st.button("↪  Log Out", key="resume_search_logout", use_container_width=True):
            st.session_state["resume_search_signed_in"] = False
            for key in ("resume_search_email", "resume_search_role", "resume_search_user_id", "resume_search_page"):
                st.session_state.pop(key, None)
            st.rerun()

    page = st.session_state["resume_search_page"]
    dataset_bytes = st.session_state.get("resume_dataset_bytes")
    dataset_name = st.session_state.get("resume_dataset_name") or "uploaded_resumes.csv"

    if page == "Home":
        st.markdown("""<div class="hero"><div class="hero-kicker">Candidate discovery workspace</div><h1>Find the right talent,<br>faster.</h1><p>Use Gemini AI, upload your dataset, or browse your available resumes.</p></div>""", unsafe_allow_html=True)
        st.markdown('<div class="small-note">Choose where you want to start.</div>', unsafe_allow_html=True)
        with st.container(key="home_cards"):
            card_columns = st.columns(3, gap="large")
            card_data = [
                ("Gemini AI", "✦", "Analyze resume skills, identify skill gaps, or draft a job description.", "Open Gemini AI"),
                ("Upload Dataset", "⇧", "Upload a CSV dataset containing resume text.", "Upload Dataset"),
                ("See Resumes", "▤", "Browse the resumes in your uploaded dataset.", "See Resumes"),
            ]
            for column, (card_title, card_icon, description, button_label) in zip(card_columns, card_data):
                with column:
                    with st.container(border=True, key=f"home_card_{card_title.lower().replace(' ', '_')}"):
                        st.markdown(f'<div class="home-card-icon">{card_icon}</div><h2 class="home-card-title">{card_title}</h2><p class="home-card-copy">{description}</p>', unsafe_allow_html=True)
                        if st.button(button_label, key=f"home_action_{card_title}", use_container_width=True):
                            st.session_state["resume_search_page"] = card_title
                            st.rerun()

    elif page == "Upload Dataset":
        st.markdown("## Upload Dataset")
        st.caption("Upload a CSV file containing resume text. The dataset stays in this browser session.")
        uploaded_file = st.file_uploader("Choose a resume CSV file", type=["csv"], max_upload_size=1024, help="The file should contain a resume-text column; Category is optional.", key="resume_dataset_uploader")
        if uploaded_file is not None:
            try:
                load_resumes(uploaded_file.getvalue(), uploaded_file.name)
                st.session_state["resume_dataset_bytes"] = uploaded_file.getvalue()
                st.session_state["resume_dataset_name"] = uploaded_file.name
                st.success(f"Dataset ready: {uploaded_file.name} · {uploaded_file.size / (1024 * 1024):.1f} MB")
                st.caption("Supported resume-text columns: Resume_str, Resume, ResumeText, Text, Content.")
            except ValueError as error:
                st.error(f"Could not read this dataset: {error}")
            except Exception:
                st.error("Could not validate this CSV. Check its format and try again.")
        # Refresh local values immediately so the See Resumes action appears after this upload.
        dataset_bytes = st.session_state.get("resume_dataset_bytes")
        dataset_name = st.session_state.get("resume_dataset_name") or "uploaded_resumes.csv"
        if dataset_bytes is not None:
            st.success(f"Current dataset: {dataset_name}")
            if st.button("See Resumes", key="upload_see_resumes", type="primary"):
                st.session_state["resume_search_page"] = "See Resumes"
                st.rerun()
        else:
            st.info("After a valid upload, the See Resumes button will appear here.")

    elif page == "See Resumes":
        st.markdown("## See Resumes")
        if dataset_bytes is None:
            st.info("Upload a dataset first to browse resumes.")
            if role != "Job seeker" and st.button("Upload Dataset", key="empty_resumes_upload", type="primary"):
                st.session_state["resume_search_page"] = "Upload Dataset"
                st.rerun()
        else:
            try:
                resumes_df = load_resumes(dataset_bytes, dataset_name)
                from backend import _find_resume_column
                resume_column = _find_resume_column(resumes_df)
                st.caption(f"{len(resumes_df):,} resumes · {dataset_name}")
                summary_rows = []
                for idx, row in resumes_df.iterrows():
                    category = str(row.get("Category", row.get("category", "")) or "").strip()
                    summary_rows.append({"Candidate": f"Candidate {idx + 1}", "Category": category or "Not specified", "Resume text length": len(str(row[resume_column] or ""))})
                st.dataframe(summary_rows, use_container_width=True, hide_index=True)
                st.markdown("### Resume details")
                candidate_index = st.selectbox("Select a resume to view", options=list(range(len(resumes_df))), format_func=lambda idx: f"Candidate {idx + 1}", key="browse_resume_index")
                st.text_area("Resume text", value=str(resumes_df.iloc[candidate_index][resume_column] or ""), height=260, disabled=True)
                if role != "Job seeker" and st.button("Search this dataset", key="browse_to_search", type="primary"):
                    st.session_state["resume_search_page"] = "Search Resume"
                    st.rerun()
            except ValueError as error:
                st.error(f"Could not display resumes: {error}")

    elif page == "Search Resume":
        st.markdown("## Search Resume")
        if dataset_bytes is None:
            st.info("Upload a dataset before searching resumes.")
            if st.button("Upload Dataset", key="search_upload_dataset", type="primary"):
                st.session_state["resume_search_page"] = "Upload Dataset"
                st.rerun()
        else:
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
                if dataset_bytes is None:
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
                        df = load_resumes(dataset_bytes, dataset_name)
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



    elif page == "Gemini AI":
        st.markdown("## Gemini AI")
        st.caption("Optional AI tools for resume analysis and job-description support.")
        if role == "Job seeker":
            st.markdown("### Analyze your resume")
            own_resume_text = st.text_area("Paste your resume text", height=220, key="job_seeker_resume_text")
            target_job_text = st.text_area("Paste a target job description", height=160, key="job_seeker_target_job")
            if st.button("Analyze skill gaps", key="job_seeker_skill_gap", type="primary"):
                with st.spinner("Analyzing your resume against the target role…"):
                    try:
                        st.session_state["job_seeker_gap_result"] = analyze_skill_gap(own_resume_text, target_job_text)
                    except (GeminiConfigurationError, ValueError, RuntimeError) as error:
                        st.error(str(error))
                    except Exception:
                        st.error("Gemini request failed. Check your API key, connection, and free-tier quota.")
            if "job_seeker_gap_result" in st.session_state:
                st.json(st.session_state["job_seeker_gap_result"])
            st.caption("AI output can be incorrect. Verify suggestions before acting on them.")
        elif dataset_bytes is None:
            st.info("Upload a dataset first to enable resume-based Gemini tools.")
            if st.button("Upload Dataset", key="gemini_upload_dataset", type="primary"):
                st.session_state["resume_search_page"] = "Upload Dataset"
                st.rerun()
        else:
            # Optional Gemini tools run only after an explicit button click.
            st.markdown("---")
            st.markdown("## 3. Gemini AI tools")
            st.caption("Optional AI tools for recruiters and job seekers. Resume text is sent to Google Gemini only when you run an AI action.")
            if dataset_bytes is not None:
                try:
                    ai_df = load_resumes(dataset_bytes, dataset_name)
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



    elif page == "Edit Profile":
        st.markdown("## Edit Profile")
        st.caption("Display preferences apply to this browser session; the account database is unchanged.")
        st.text_input("Account email", value=st.session_state.get("resume_search_email", ""), disabled=True)
        display_name = st.text_input("Display name", value=st.session_state.get("resume_search_display_name", ""), key="profile_display_name_input")
        if st.button("Save Profile", key="save_profile", type="primary"):
            st.session_state["resume_search_display_name"] = display_name.strip()
            st.success("Display name saved for this session.")

    elif page == "Change Icon":
        st.markdown("## Change Icon")
        icon_options = ["⌕", "✦", "🔎", "📄", "🟢", "💼", "✨"]
        current_icon = st.session_state.get("resume_search_icon", "⌕")
        selected_icon = st.selectbox("Choose your workspace icon", icon_options, index=icon_options.index(current_icon) if current_icon in icon_options else 0)
        if st.button("Save Icon", key="save_workspace_icon", type="primary"):
            st.session_state["resume_search_icon"] = selected_icon
            st.success("Workspace icon updated for this session.")

    elif page == "About This Project":
        st.markdown("## About This Project")
        st.write("Resume Search helps users explore resume datasets, search for text-relevant candidates, review matching skills, and optionally use Gemini AI for resume insights.")
        st.write("Search scores measure text similarity only. They are not hiring probabilities, and results should be reviewed by a person.")
        st.write("Uploaded datasets and profile display preferences are kept in the current Streamlit session; they are not permanently saved by these interface changes.")

    st.markdown('<div class="footer-note">Resume Search · Review resume evidence carefully. Automated relevance scores should support—not replace—human judgment.</div>', unsafe_allow_html=True)



if __name__ == "__main__":
    _main()
