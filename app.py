import csv
import io
import json

import streamlit as st

from src.cv.parser import parse_cv
from src.cv.entities import build_profile
from src.matching.dedup import deduplicate
from src.matching.explainer import explain_match
from src.matching.filters import apply_hard_filters
from src.matching.scorer import score_jobs
from src.models.preferences import Preferences
from src.models.profile import Profile
from src.sources.normalizer import fetch_all_jobs, get_all_connectors
from src.storage.privacy import PrivacyManager
from src.utils.http_client import register_personal_fragments

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Job Seeker Cheater",
    page_icon="🏖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS (brand styling)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fredoka+One&family=Nunito:wght@300;400;700&family=JetBrains+Mono:wght@400&display=swap');

:root {
    --deep-blue: #1B2A4A;
    --purple: #6C3BAA;
    --bordeaux: #8B1A3A;
    --gold: #F5C542;
    --off-white: #F7F5F2;
    --lavender: #EDE8F5;
    --slate: #5A6275;
}

.stApp { font-family: 'Nunito', sans-serif; }

h1, h2, h3 { font-family: 'Fredoka One', cursive; color: var(--deep-blue); }

.hero-title {
    font-family: 'Fredoka One', cursive;
    font-size: 2.8rem;
    color: var(--deep-blue);
    margin-bottom: 0;
    line-height: 1.2;
}
.hero-cheater { color: var(--bordeaux); }
.hero-tagline {
    font-family: 'Nunito', sans-serif;
    font-size: 1.3rem;
    color: var(--slate);
    margin-top: 0.2rem;
}

.job-card {
    background: white;
    border-radius: 12px;
    padding: 1.2rem;
    margin-bottom: 1rem;
    border-left: 5px solid var(--purple);
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.job-card h3 { margin: 0 0 0.3rem 0; font-size: 1.15rem; }
.job-card .company { color: var(--purple); font-weight: 700; }
.job-card .meta { color: var(--slate); font-size: 0.9rem; }

.score-badge {
    display: inline-block;
    background: var(--gold);
    color: var(--deep-blue);
    font-weight: 700;
    border-radius: 50%;
    width: 50px;
    height: 50px;
    line-height: 50px;
    text-align: center;
    font-size: 1rem;
}

.skill-tag {
    display: inline-block;
    background: var(--lavender);
    color: var(--deep-blue);
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.85rem;
    margin: 2px 3px;
    font-family: 'JetBrains Mono', monospace;
}

.match-reason { color: #2e7d32; font-size: 0.9rem; }
.match-gap { color: #e65100; font-size: 0.9rem; }

.privacy-banner {
    background: var(--lavender);
    border-radius: 8px;
    padding: 0.8rem 1rem;
    font-size: 0.9rem;
    margin-bottom: 1rem;
    border-left: 4px solid var(--purple);
}

.disclaimer {
    font-size: 0.8rem;
    color: var(--slate);
    border-top: 1px solid #ddd;
    padding-top: 1rem;
    margin-top: 2rem;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "profile" not in st.session_state:
    st.session_state.profile = Profile()
if "preferences" not in st.session_state:
    st.session_state.preferences = Preferences()
if "jobs" not in st.session_state:
    st.session_state.jobs = []
if "scored_results" not in st.session_state:
    st.session_state.scored_results = []
if "persist_mode" not in st.session_state:
    st.session_state.persist_mode = False

privacy_mgr = PrivacyManager()

# Try loading persisted profile on first run
if st.session_state.profile.is_empty and privacy_mgr.is_persisted():
    loaded = privacy_mgr.load_profile()
    if loaded:
        st.session_state.profile, st.session_state.preferences = loaded
        st.session_state.persist_mode = True

# ---------------------------------------------------------------------------
# Hero section
# ---------------------------------------------------------------------------
hero_col1, hero_col2 = st.columns([3, 2])
with hero_col1:
    st.markdown(
        '<p class="hero-title">Job Seeker <span class="hero-cheater">Cheater</span> 🏖️</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="hero-tagline">Your laptop works. You relax.</p>',
        unsafe_allow_html=True,
    )
with hero_col2:
    st.image(
        "https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=400&q=80",
        caption="This could be you while your laptop finds jobs",
        use_container_width=True,
    )

st.markdown(
    '<div class="privacy-banner">'
    "🔒 <b>Your CV is processed locally on your machine and is never uploaded to any server.</b> "
    "We only fetch public job listings. No cookies, no trackers, no funny business. Pinky promise."
    "</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar: Privacy settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🔒 Privacy Settings")

    mode_label = "💾 Remember on this device" if st.session_state.persist_mode else "🧊 Ephemeral (memory only)"
    st.markdown(f"**Mode:** {mode_label}")

    new_persist = st.toggle(
        "Remember my profile on this device",
        value=st.session_state.persist_mode,
        help="OFF = data cleared on close. ON = saved locally on your disk.",
    )
    if new_persist != st.session_state.persist_mode:
        st.session_state.persist_mode = new_persist
        if new_persist and not st.session_state.profile.is_empty:
            privacy_mgr.save_profile(st.session_state.profile, st.session_state.preferences)
        st.rerun()

    st.divider()

    if st.button("🗑️ Delete all local data", type="secondary"):
        privacy_mgr.delete_all()
        st.session_state.profile = Profile()
        st.session_state.preferences = Preferences()
        st.session_state.jobs = []
        st.session_state.scored_results = []
        st.session_state.persist_mode = False
        st.success("All local data deleted.")
        st.rerun()

    with st.expander("📤 Export / Import profile"):
        export_data = privacy_mgr.export_profile()
        if export_data:
            st.download_button("Download profile JSON", export_data, "profile.json", "application/json")
        else:
            st.caption("No saved profile to export.")

        uploaded_profile = st.file_uploader("Import profile JSON", type=["json"], key="import_profile")
        if uploaded_profile:
            content = uploaded_profile.read().decode("utf-8")
            if privacy_mgr.import_profile(content):
                loaded = privacy_mgr.load_profile()
                if loaded:
                    st.session_state.profile, st.session_state.preferences = loaded
                    st.success("Profile imported!")
                    st.rerun()
            else:
                st.error("Invalid profile file.")

    st.divider()
    st.caption(
        "This tool suggests jobs only. You are responsible for verifying "
        "listings and submitting applications. Data sources are used in "
        "compliance with their public API terms."
    )

# ---------------------------------------------------------------------------
# Main tabs
# ---------------------------------------------------------------------------
tab_cv, tab_prefs, tab_search, tab_results = st.tabs(
    ["📄 Upload CV", "⚙️ Preferences", "🔍 Find Jobs", "📊 Results"]
)

# ---- Tab 1: CV Upload ----
with tab_cv:
    st.markdown("### Upload your CV")
    st.caption("Supported formats: PDF, DOCX, TXT")

    uploaded_file = st.file_uploader(
        "Choose your CV file",
        type=["pdf", "docx", "txt"],
        key="cv_upload",
    )

    if uploaded_file is not None:
        with st.spinner("Parsing your CV locally..."):
            try:
                raw_text = parse_cv(uploaded_file.name, uploaded_file.read())
                profile = build_profile(raw_text)
                st.session_state.profile = profile

                # Register fragments for privacy guardrail
                fragments = [raw_text[i:i+50] for i in range(0, min(len(raw_text), 500), 50)]
                register_personal_fragments(fragments)

                if st.session_state.persist_mode:
                    privacy_mgr.save_profile(profile, st.session_state.preferences)

                st.success("CV parsed successfully!")
            except Exception as e:
                st.error(f"Failed to parse CV: {e}")

    profile = st.session_state.profile
    if not profile.is_empty:
        st.markdown("#### Detected Profile")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Skills found:**")
            if profile.skills:
                skills_html = " ".join(f'<span class="skill-tag">{s}</span>' for s in profile.skills[:30])
                st.markdown(skills_html, unsafe_allow_html=True)
            else:
                st.caption("No skills detected.")

        with col2:
            if profile.years_experience:
                st.metric("Years of experience", f"~{profile.years_experience:.0f}")
            if profile.role_hints:
                st.markdown("**Role hints:** " + ", ".join(profile.role_hints[:5]))

        with st.expander("Preview extracted text"):
            st.text(profile.raw_text[:2000])
    else:
        st.info("Upload a CV to get started, you magnificent slacker.")

# ---- Tab 2: Preferences ----
with tab_prefs:
    st.markdown("### Set your job preferences")

    prefs = st.session_state.preferences

    target_titles = st.text_input(
        "Target job titles (comma-separated)",
        value=", ".join(prefs.target_titles),
        placeholder="e.g. Data Scientist, ML Engineer, Analytics Manager",
    )
    required_skills = st.text_input(
        "Required skills (must-have, comma-separated)",
        value=", ".join(prefs.required_skills),
        placeholder="e.g. python, sql, machine learning",
    )
    nice_skills = st.text_input(
        "Nice-to-have skills (comma-separated)",
        value=", ".join(prefs.nice_to_have_skills),
        placeholder="e.g. spark, tensorflow, aws",
    )
    locations = st.text_input(
        "Preferred locations (comma-separated)",
        value=", ".join(prefs.locations),
        placeholder="e.g. London, Berlin, Remote",
    )

    col1, col2 = st.columns(2)
    with col1:
        remote_type = st.selectbox(
            "Work arrangement",
            ["Any", "Remote", "Hybrid", "On-site"],
            index=["", "remote", "hybrid", "onsite"].index(prefs.remote_type)
            if prefs.remote_type in ["", "remote", "hybrid", "onsite"]
            else 0,
        )
        seniority = st.selectbox(
            "Seniority level",
            ["Any", "Junior", "Mid", "Senior", "Lead", "Executive"],
            index=["", "junior", "mid", "senior", "lead", "executive"].index(prefs.seniority)
            if prefs.seniority in ["", "junior", "mid", "senior", "lead", "executive"]
            else 0,
        )
    with col2:
        min_salary = st.number_input(
            "Minimum salary (annual, optional)",
            min_value=0,
            value=int(prefs.min_salary) if prefs.min_salary else 0,
            step=5000,
        )
        industries = st.text_input(
            "Industries (optional, comma-separated)",
            value=", ".join(prefs.industries),
            placeholder="e.g. fintech, healthtech, e-commerce",
        )

    if st.button("💾 Save preferences", type="primary"):
        new_prefs = Preferences(
            target_titles=[t.strip() for t in target_titles.split(",") if t.strip()],
            required_skills=[s.strip().lower() for s in required_skills.split(",") if s.strip()],
            nice_to_have_skills=[s.strip().lower() for s in nice_skills.split(",") if s.strip()],
            locations=[l.strip() for l in locations.split(",") if l.strip()],
            remote_type={"Any": "", "Remote": "remote", "Hybrid": "hybrid", "On-site": "onsite"}[remote_type],
            seniority={"Any": "", "Junior": "junior", "Mid": "mid", "Senior": "senior", "Lead": "lead", "Executive": "executive"}[seniority],
            min_salary=float(min_salary) if min_salary > 0 else None,
            industries=[i.strip().lower() for i in industries.split(",") if i.strip()],
        )
        st.session_state.preferences = new_prefs

        if st.session_state.persist_mode:
            privacy_mgr.save_profile(st.session_state.profile, new_prefs)

        st.success("Preferences saved!")

# ---- Tab 3: Find Jobs ----
with tab_search:
    st.markdown("### Fetch & match jobs")
    st.caption("Fetches from Remotive, Arbeitnow, and Greenhouse public boards.")

    sources_col1, sources_col2 = st.columns([2, 1])
    with sources_col1:
        selected_sources = st.multiselect(
            "Sources to search",
            ["Remotive", "Arbeitnow", "Greenhouse"],
            default=["Remotive", "Arbeitnow"],
        )
    with sources_col2:
        st.markdown("")
        st.markdown("")
        fetch_btn = st.button("🔍 Fetch & Match Jobs", type="primary", use_container_width=True)

    if fetch_btn:
        if st.session_state.profile.is_empty:
            st.warning("Upload your CV first to get personalised matches.")

        connectors = []
        source_map = {
            "Remotive": "remotive",
            "Arbeitnow": "arbeitnow",
            "Greenhouse": "greenhouse",
        }
        all_connectors = get_all_connectors()
        connectors = [c for c in all_connectors if c.name in [source_map[s] for s in selected_sources]]

        with st.spinner("Fetching jobs from public APIs... (no personal data sent)"):
            try:
                jobs = fetch_all_jobs(connectors)
                jobs = deduplicate(jobs)
                st.session_state.jobs = jobs
                st.success(f"Fetched {len(jobs)} unique jobs!")
            except Exception as e:
                st.error(f"Error fetching jobs: {e}")
                jobs = []

        if jobs and not st.session_state.profile.is_empty:
            with st.spinner("Ranking matches..."):
                prefs = st.session_state.preferences
                profile = st.session_state.profile

                filtered = apply_hard_filters(jobs, prefs)
                scored = score_jobs(filtered, profile, prefs)

                results_with_explanations = []
                for job, score, sub_scores in scored:
                    explanation = explain_match(job, profile, prefs, sub_scores)
                    results_with_explanations.append((job, score, sub_scores, explanation))

                st.session_state.scored_results = results_with_explanations
                st.info(f"Matched {len(results_with_explanations)} jobs after filters. Check the Results tab!")
        elif jobs:
            results = [(j, 0.0, {}, {"reasons": ["Upload CV for personalised scoring"], "gaps": []}) for j in jobs]
            st.session_state.scored_results = results
            st.info(f"Found {len(results)} jobs. Upload a CV for ranked matches!")

# ---- Tab 4: Results ----
with tab_results:
    st.markdown("### Your matches")

    results = st.session_state.scored_results

    if not results:
        st.info("No results yet. Go to the 'Find Jobs' tab and fetch some listings!")
    else:
        # Filters
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            all_sources = sorted({r[0].source.split(":")[0] for r in results})
            source_filter = st.multiselect("Filter by source", all_sources, default=all_sources)
        with filter_col2:
            remote_filter = st.selectbox("Remote type", ["All", "Remote", "Hybrid", "On-site"])
        with filter_col3:
            sort_option = st.selectbox("Sort by", ["Score (high to low)", "Score (low to high)", "Newest first"])

        filtered_results = results
        if source_filter:
            filtered_results = [r for r in filtered_results if r[0].source.split(":")[0] in source_filter]
        if remote_filter != "All":
            rt_map = {"Remote": "remote", "Hybrid": "hybrid", "On-site": "onsite"}
            filtered_results = [r for r in filtered_results if r[0].remote_type == rt_map.get(remote_filter, "")]

        if sort_option == "Score (low to high)":
            filtered_results.sort(key=lambda x: x[1])
        elif sort_option == "Newest first":
            filtered_results.sort(key=lambda x: x[0].published_at or __import__("datetime").datetime.min, reverse=True)

        st.caption(f"Showing {len(filtered_results)} of {len(results)} results")

        # CSV export
        if filtered_results:
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(["Score", "Title", "Company", "Location", "Remote", "Source", "URL", "Match Reasons"])
            for job, score, _, explanation in filtered_results:
                writer.writerow([
                    f"{score:.2f}",
                    job.title,
                    job.company,
                    job.location,
                    job.remote_type,
                    job.source,
                    job.url,
                    "; ".join(explanation.get("reasons", [])),
                ])
            st.download_button(
                "📥 Export to CSV",
                csv_buffer.getvalue(),
                "job_matches.csv",
                "text/csv",
            )

        # Job cards
        for job, score, sub_scores, explanation in filtered_results[:50]:
            score_pct = int(score * 100)
            reasons = explanation.get("reasons", [])
            gaps = explanation.get("gaps", [])

            st.markdown(f"""
            <div class="job-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div style="flex: 1;">
                        <h3>{job.title}</h3>
                        <span class="company">{job.company}</span>
                        <div class="meta">
                            📍 {job.location or "Not specified"}
                            {"&nbsp;&nbsp;🏠 " + job.remote_type.title() if job.remote_type else ""}
                            {"&nbsp;&nbsp;💰 " + job.display_salary if job.display_salary else ""}
                            &nbsp;&nbsp;📡 {job.source}
                        </div>
                    </div>
                    <div class="score-badge">{score_pct}%</div>
                </div>
            """, unsafe_allow_html=True)

            if job.tags:
                tags_html = " ".join(f'<span class="skill-tag">{t}</span>' for t in job.tags[:8])
                st.markdown(tags_html, unsafe_allow_html=True)

            if reasons:
                for r in reasons[:4]:
                    st.markdown(f'<div class="match-reason">✅ {r}</div>', unsafe_allow_html=True)
            if gaps:
                for g in gaps[:3]:
                    st.markdown(f'<div class="match-gap">⚠️ {g}</div>', unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

            btn_col1, btn_col2 = st.columns([1, 4])
            with btn_col1:
                if job.url:
                    st.link_button("🚀 Apply", job.url, use_container_width=True)

            with btn_col2:
                with st.expander("View description"):
                    st.text(job.description[:1500] if job.description else "No description available.")

# ---------------------------------------------------------------------------
# Footer disclaimer
# ---------------------------------------------------------------------------
st.markdown("""
<div class="disclaimer">
<b>Disclaimer:</b> Job Seeker Cheater is a job-suggestion tool only. It does not apply for
jobs on your behalf. You are solely responsible for verifying job listings and
submitting applications. All job data is sourced from public APIs (Remotive, Arbeitnow,
Greenhouse public boards) in compliance with their terms. Your CV and personal data are
processed locally on your machine and are never transmitted to external servers.
This tool does not use cookies or third-party analytics.
<br><br>
<b>Not legal or employment advice.</b> Review with qualified counsel before relying on any
compliance-related features for production use.
</div>
""", unsafe_allow_html=True)
