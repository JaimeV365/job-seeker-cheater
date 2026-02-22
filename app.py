import csv
import io
import os

import streamlit as st
import streamlit.components.v1 as components

from src.cv.parser import parse_cv
from src.cv.entities import build_profile
from src.matching.dedup import deduplicate
from src.matching.explainer import explain_match
from src.matching.filters import apply_hard_filters
from src.matching.scorer import score_jobs
from src.models.preferences import Preferences
from src.models.profile import Profile
from src.sources.normalizer import fetch_all_jobs, get_all_connectors
from src.sources.reed import ReedConnector
from src.sources.adzuna import AdzunaConnector
from src.storage.privacy import PrivacyManager
from src.utils.http_client import register_personal_fragments

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Job Seeker Cheater",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fredoka+One&family=Nunito:wght@300;400;700&family=JetBrains+Mono:wght@400&display=swap');

#MainMenu {visibility: hidden;}
[data-testid="stStatusWidget"] {visibility: hidden;}
footer {visibility: hidden;}
header [data-testid="stToolbar"] {display: none;}

:root {
    --deep-blue: #1B2A4A;
    --purple: #6C3BAA;
    --bordeaux: #8B1A3A;
    --gold: #F5C542;
    --off-white: #F7F5F2;
    --lavender: #EDE8F5;
    --slate: #5A6275;
    --green: #2e7d32;
}

.stApp { font-family: 'Nunito', sans-serif; }
h1, h2, h3 { font-family: 'Fredoka One', cursive; color: var(--deep-blue); }

.hero-title {
    font-family: 'Fredoka One', cursive;
    font-size: 3.5rem; color: var(--deep-blue);
    margin-bottom: 0; line-height: 1.1;
    letter-spacing: -1px;
}
.hero-cheater { color: var(--bordeaux); }
.hero-tagline {
    font-family: 'Nunito', sans-serif;
    font-size: 1.3rem; color: var(--slate);
    margin-top: 0.3rem; margin-bottom: 0.8rem;
}

.step-bar { display: flex; gap: 0; margin-bottom: 1.2rem; }
.step-item {
    flex: 1; text-align: center; padding: 0.6rem 0.3rem;
    font-size: 0.85rem; font-weight: 700;
    border-bottom: 4px solid #ddd; color: var(--slate);
    cursor: default;
}
.step-done { border-bottom-color: var(--green); color: var(--green); }
.step-active { border-bottom-color: var(--purple); color: var(--purple); }
.step-pending { border-bottom-color: #ddd; color: #bbb; }

.job-card {
    background: white; border-radius: 12px; padding: 1.2rem;
    margin-bottom: 1rem; border-left: 5px solid var(--purple);
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.job-card h3 { margin: 0 0 0.3rem 0; font-size: 1.1rem; }
.job-card .company { color: var(--purple); font-weight: 700; }
.job-card .meta { color: var(--slate); font-size: 0.85rem; }
.score-badge {
    display: inline-block; background: var(--gold); color: var(--deep-blue);
    font-weight: 700; border-radius: 50%;
    width: 48px; height: 48px; line-height: 48px;
    text-align: center; font-size: 0.95rem;
}
.skill-tag {
    display: inline-block; background: var(--lavender); color: var(--deep-blue);
    padding: 2px 10px; border-radius: 12px; font-size: 0.82rem;
    margin: 2px 3px; font-family: 'JetBrains Mono', monospace;
}
.match-reason { color: var(--green); font-size: 0.88rem; }
.match-gap { color: #e65100; font-size: 0.88rem; }
.privacy-strip {
    background: var(--lavender); border-radius: 6px;
    padding: 0.5rem 0.8rem; font-size: 0.82rem;
    margin-bottom: 0.8rem; border-left: 3px solid var(--purple);
}
.disclaimer {
    font-size: 0.78rem; color: var(--slate);
    border-top: 1px solid #ddd; padding-top: 0.8rem; margin-top: 1.5rem;
}
.api-hint {
    background: #fff8e1; border-left: 3px solid var(--gold);
    border-radius: 6px; padding: 0.6rem 0.8rem; font-size: 0.84rem;
    margin-top: 0.6rem;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
COUNTRY_MAP = {
    "Any country": "",
    "United Kingdom": "UK",
    "United States": "US",
    "Germany": "DE",
    "Canada": "CA",
    "France": "FR",
    "Spain": "ES",
    "Australia": "AU",
    "Netherlands": "NL",
    "Ireland": "IE",
    "Sweden": "SE",
    "Italy": "IT",
    "Portugal": "PT",
    "Switzerland": "CH",
    "Austria": "AT",
    "Belgium": "BE",
    "India": "IN",
    "Singapore": "SG",
    "Brazil": "BR",
    "New Zealand": "NZ",
    "Poland": "PL",
    "South Africa": "ZA",
}
COUNTRY_NAMES = list(COUNTRY_MAP.keys())
CODE_TO_NAME = {v: k for k, v in COUNTRY_MAP.items() if v}

# Countries available for "Also search remote in" (excludes "Any country")
REMOTE_COUNTRY_OPTIONS = [n for n in COUNTRY_NAMES if n != "Any country"]

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "profile": Profile(),
    "preferences": Preferences(),
    "jobs": [],
    "scored_results": [],
    "persist_mode": False,
    "current_step": 0,
    "_go_to_tab": None,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

privacy_mgr = PrivacyManager()

if st.session_state.profile.is_empty and privacy_mgr.is_persisted():
    loaded = privacy_mgr.load_profile()
    if loaded:
        st.session_state.profile, st.session_state.preferences = loaded
        st.session_state.persist_mode = True

# ---------------------------------------------------------------------------
# Auto-advance: inject JS to click a tab if requested
# ---------------------------------------------------------------------------
if st.session_state._go_to_tab is not None:
    tab_idx = st.session_state._go_to_tab
    st.session_state._go_to_tab = None
    components.html(
        f"""<script>
        const tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
        if (tabs.length > {tab_idx}) {{ tabs[{tab_idx}].click(); }}
        </script>""",
        height=0,
    )

# ---------------------------------------------------------------------------
# Step progress
# ---------------------------------------------------------------------------
def _step_status():
    cv_done = not st.session_state.profile.is_empty
    prefs_done = bool(st.session_state.preferences.target_titles)
    search_done = bool(st.session_state.scored_results)
    step = st.session_state.current_step
    return [
        "done" if cv_done else ("active" if step == 0 else "pending"),
        "done" if prefs_done else ("active" if step == 1 else "pending"),
        "done" if search_done else ("active" if step == 2 else "pending"),
        "done" if search_done else ("active" if step == 3 else "pending"),
    ]

STEP_LABELS = ["1. Upload CV", "2. Preferences", "3. Search", "4. Results"]

# ---------------------------------------------------------------------------
# Header -- big, clean, no image, no emoji
# ---------------------------------------------------------------------------
st.markdown(
    '<p class="hero-title">Job Seeker <span class="hero-cheater">Cheater</span></p>'
    '<p class="hero-tagline">It searches. You chill.</p>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="privacy-strip">'
    "Your CV is processed <b>locally on your machine</b> and never uploaded anywhere. "
    "No cookies. No trackers. Pinky promise."
    "</div>",
    unsafe_allow_html=True,
)

statuses = _step_status()
step_html = '<div class="step-bar">'
for label, status in zip(STEP_LABELS, statuses):
    icon = "✅ " if status == "done" else ""
    step_html += f'<div class="step-item step-{status}">{icon}{label}</div>'
step_html += "</div>"
st.markdown(step_html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Privacy")
    mode_label = "Saved locally" if st.session_state.persist_mode else "Ephemeral"
    st.caption(f"**Mode:** {mode_label}")
    new_persist = st.toggle("Remember my profile on this device", value=st.session_state.persist_mode,
                            help="OFF = cleared on close. ON = saved to local disk only.")
    if new_persist != st.session_state.persist_mode:
        st.session_state.persist_mode = new_persist
        if new_persist and not st.session_state.profile.is_empty:
            privacy_mgr.save_profile(st.session_state.profile, st.session_state.preferences)
        st.rerun()
    if st.button("Delete all local data"):
        privacy_mgr.delete_all()
        for k, v in _DEFAULTS.items():
            st.session_state[k] = v
        st.success("Done! All cleared.")
        st.rerun()
    with st.expander("Import / Export"):
        export_data = privacy_mgr.export_profile()
        if export_data:
            st.download_button("Download profile JSON", export_data, "profile.json", "application/json")
        uploaded_profile = st.file_uploader("Import profile JSON", type=["json"], key="import_profile")
        if uploaded_profile:
            content = uploaded_profile.read().decode("utf-8")
            if privacy_mgr.import_profile(content):
                loaded = privacy_mgr.load_profile()
                if loaded:
                    st.session_state.profile, st.session_state.preferences = loaded
                    st.success("Imported!")
                    st.rerun()

# ---------------------------------------------------------------------------
# Tabs (all freely navigable)
# ---------------------------------------------------------------------------
tab_cv, tab_prefs, tab_search, tab_results = st.tabs(
    ["Upload CV", "Preferences", "Search Jobs", "Results"]
)

# ===== TAB 1: CV Upload =====
with tab_cv:
    uploaded_file = st.file_uploader(
        "Upload your CV (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"], key="cv_upload",
    )

    if uploaded_file is not None:
        with st.spinner("Parsing your CV locally..."):
            try:
                raw_text = parse_cv(uploaded_file.name, uploaded_file.read())
                profile = build_profile(raw_text)
                st.session_state.profile = profile
                fragments = [raw_text[i:i+50] for i in range(0, min(len(raw_text), 500), 50)]
                register_personal_fragments(fragments)
                if st.session_state.persist_mode:
                    privacy_mgr.save_profile(profile, st.session_state.preferences)
                st.session_state.current_step = max(st.session_state.current_step, 1)
                st.session_state._go_to_tab = 1
                st.rerun()
            except Exception as e:
                st.error(f"Failed to parse: {e}")

    profile = st.session_state.profile
    if not profile.is_empty:
        st.success("CV parsed! Review your skills below, then head to **Preferences**.")

        current_skills = list(profile.skills)
        edited_skills = st.multiselect(
            "Your skills (remove irrelevant ones, type to add new ones)",
            options=current_skills,
            default=current_skills,
            help="Remove skills that aren't relevant. Type a new skill name and press Enter to add it.",
            key="skill_editor",
        )
        if set(edited_skills) != set(current_skills):
            st.session_state.profile = Profile(
                raw_text=profile.raw_text,
                skills=edited_skills,
                years_experience=profile.years_experience,
                role_hints=profile.role_hints,
                summary=profile.summary,
            )
            if st.session_state.persist_mode:
                privacy_mgr.save_profile(st.session_state.profile, st.session_state.preferences)

        col1, col2 = st.columns([3, 1])
        with col1:
            if profile.role_hints:
                st.caption("**Role hints:** " + ", ".join(profile.role_hints[:5]))
        with col2:
            if profile.years_experience:
                st.metric("Experience", f"~{profile.years_experience:.0f} yrs")

        with st.expander("Preview extracted text"):
            st.text(profile.raw_text[:2000])
    else:
        st.info("Upload a CV to get started, you magnificent slacker.")

# ===== TAB 2: Preferences =====
with tab_prefs:
    prefs = st.session_state.preferences

    col_main, col_side = st.columns([3, 2])

    with col_main:
        target_titles = st.text_input(
            "Target job titles (comma-separated)",
            value=", ".join(prefs.target_titles),
            placeholder="e.g. Data Scientist, ML Engineer, Analytics Manager",
        )
        required_skills = st.text_input(
            "Required skills -- must-have (comma-separated)",
            value=", ".join(prefs.required_skills),
            placeholder="e.g. python, sql, machine learning",
        )
        nice_skills = st.text_input(
            "Nice-to-have skills (comma-separated)",
            value=", ".join(prefs.nice_to_have_skills),
            placeholder="e.g. spark, tensorflow, aws",
        )

    with col_side:
        current_country_name = CODE_TO_NAME.get(prefs.country, "Any country")
        country_name = st.selectbox(
            "Country",
            COUNTRY_NAMES,
            index=COUNTRY_NAMES.index(current_country_name) if current_country_name in COUNTRY_NAMES else 0,
            help="Your primary country. Disambiguates cities (e.g. London UK vs London CA).",
        )
        locations = st.text_input(
            "City / region (comma-separated)",
            value=", ".join(prefs.locations),
            placeholder="e.g. London, Manchester, Edinburgh",
        )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        REMOTE_OPTIONS = ["Remote", "Hybrid", "On-site"]
        remote_defaults = [
            {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On-site"}.get(r, r)
            for r in prefs.remote_types if r
        ]
        remote_types = st.multiselect(
            "Work arrangement",
            REMOTE_OPTIONS,
            default=[d for d in remote_defaults if d in REMOTE_OPTIONS],
            placeholder="Any (leave empty)",
            help="Leave empty = all types. Select specific ones to filter.",
        )
    with col_b:
        SENIORITY_OPTIONS = ["Junior", "Mid", "Senior", "Lead", "Executive"]
        sen_defaults = [s.title() for s in prefs.seniority_levels if s]
        seniority_levels = st.multiselect(
            "Seniority level",
            SENIORITY_OPTIONS,
            default=[s for s in sen_defaults if s in SENIORITY_OPTIONS],
            placeholder="Any (leave empty)",
            help="Leave empty = all levels. Select specific ones to filter.",
        )
    with col_c:
        min_salary = st.number_input(
            "Min salary (annual)", min_value=0,
            value=int(prefs.min_salary) if prefs.min_salary else 0, step=5000,
        )
        industries = st.text_input(
            "Industries (optional)",
            value=", ".join(prefs.industries),
            placeholder="e.g. fintech, healthtech",
        )

    # Multi-region remote: "Also search for remote jobs in..."
    st.markdown("---")
    st.markdown("**Also look for remote jobs in other countries?**")
    st.caption(
        "If you can legally work remotely for employers in other countries, add them here. "
        "Only remote positions will be included from these regions."
    )
    also_remote_defaults = [CODE_TO_NAME.get(c, c) for c in prefs.also_remote_in if CODE_TO_NAME.get(c, c) in REMOTE_COUNTRY_OPTIONS]
    also_remote_in = st.multiselect(
        "Additional remote countries",
        REMOTE_COUNTRY_OPTIONS,
        default=also_remote_defaults,
        placeholder="e.g. Germany, France, Netherlands...",
        help="Jobs from these countries will only be included if they are remote.",
    )

    if st.button("Save preferences & continue", type="primary"):
        remote_map = {"Remote": "remote", "Hybrid": "hybrid", "On-site": "onsite"}
        seniority_map = {"Junior": "junior", "Mid": "mid", "Senior": "senior", "Lead": "lead", "Executive": "executive"}
        new_prefs = Preferences(
            target_titles=[t.strip() for t in target_titles.split(",") if t.strip()],
            required_skills=[s.strip().lower() for s in required_skills.split(",") if s.strip()],
            nice_to_have_skills=[s.strip().lower() for s in nice_skills.split(",") if s.strip()],
            locations=[loc.strip() for loc in locations.split(",") if loc.strip()],
            country=COUNTRY_MAP.get(country_name, ""),
            remote_types=[remote_map[r] for r in remote_types],
            seniority_levels=[seniority_map[s] for s in seniority_levels],
            min_salary=float(min_salary) if min_salary > 0 else None,
            industries=[i.strip().lower() for i in industries.split(",") if i.strip()],
            also_remote_in=[COUNTRY_MAP[n] for n in also_remote_in if n in COUNTRY_MAP],
        )
        st.session_state.preferences = new_prefs
        if st.session_state.persist_mode:
            privacy_mgr.save_profile(st.session_state.profile, new_prefs)
        st.session_state.current_step = max(st.session_state.current_step, 2)
        st.session_state._go_to_tab = 2
        st.rerun()

# ===== TAB 3: Search Jobs =====
with tab_search:
    st.caption("Fetches from public job APIs only. No personal data is sent.")

    reed_available = ReedConnector.is_available()
    adzuna_available = AdzunaConnector.is_available()

    # Build source options dynamically based on available API keys
    source_options = {
        "Remotive": ("Remote-first jobs worldwide", True),
        "Arbeitnow": ("European & remote jobs", True),
        "Greenhouse": ("Tech company career boards", True),
    }
    if reed_available:
        source_options["Reed"] = ("UK's largest job board", True)
    if adzuna_available:
        source_options["Adzuna"] = ("UK, US, EU, AU and more", True)

    default_sources = ["Remotive", "Arbeitnow"]
    if reed_available:
        default_sources.append("Reed")
    if adzuna_available:
        default_sources.append("Adzuna")

    selected_sources = st.multiselect(
        "Job sources to search",
        list(source_options.keys()),
        default=default_sources,
        help="Select which boards to search. More sources = more results but slower.",
    )

    # Helpful hint if Reed/Adzuna not configured
    if not reed_available or not adzuna_available:
        missing = []
        if not reed_available:
            missing.append("**Reed.co.uk** (UK's #1 board) -- get a free key at [reed.co.uk/developers](https://www.reed.co.uk/developers/Jobseeker)")
        if not adzuna_available:
            missing.append("**Adzuna** (UK/US/EU/AU) -- get a free key at [developer.adzuna.com](https://developer.adzuna.com/signup)")
        hint_text = "Want more sources? Add free API keys to unlock:<br>" + "<br>".join(missing)
        hint_text += "<br><br>Set them as environment variables before launching, or add to a <code>.env</code> file."
        st.markdown(f'<div class="api-hint">{hint_text}</div>', unsafe_allow_html=True)

    st.markdown("")
    st.caption(
        "**About Indeed & LinkedIn:** These platforms don't offer free public APIs. "
        "We respect their terms of service, so we can't scrape them. "
        "Reed and Adzuna are excellent free alternatives that cover UK and international markets."
    )

    fetch_btn = st.button("Fetch & Match Jobs", type="primary", use_container_width=True)

    if fetch_btn:
        if st.session_state.profile.is_empty:
            st.warning("Upload your CV first for personalised ranking.")

        source_map = {
            "Remotive": "remotive", "Arbeitnow": "arbeitnow",
            "Greenhouse": "greenhouse", "Reed": "reed", "Adzuna": "adzuna",
        }

        prefs_obj = st.session_state.preferences

        # Build connectors, passing search context to Reed/Adzuna
        connectors = []
        all_available = get_all_connectors()
        for s in selected_sources:
            s_name = source_map.get(s, "")
            if s_name in ("reed", "adzuna"):
                kw = " ".join(prefs_obj.target_titles[:3]) if prefs_obj.target_titles else ""
                loc = prefs_obj.locations[0] if prefs_obj.locations else ""
                country = prefs_obj.country or "UK"
                if s_name == "reed":
                    connectors.append(ReedConnector(keywords=kw, location=loc))
                else:
                    connectors.append(AdzunaConnector(keywords=kw, location=loc, country=country))
                    # Also fetch from additional remote countries
                    for extra_country in prefs_obj.also_remote_in:
                        if extra_country != country:
                            connectors.append(AdzunaConnector(keywords=kw, country=extra_country))
            else:
                for c in all_available:
                    if c.name == s_name:
                        connectors.append(c)
                        break

        with st.spinner("Fetching jobs from public APIs..."):
            try:
                jobs = fetch_all_jobs(connectors)
                jobs = deduplicate(jobs)
                st.session_state.jobs = jobs
            except Exception as e:
                st.error(f"Error fetching jobs: {e}")
                jobs = []

        if jobs and not st.session_state.profile.is_empty:
            with st.spinner("Ranking matches..."):
                profile_obj = st.session_state.profile
                filtered = apply_hard_filters(jobs, prefs_obj)
                scored = score_jobs(filtered, profile_obj, prefs_obj)
                results = []
                for job, score, sub_scores in scored:
                    explanation = explain_match(job, profile_obj, prefs_obj, sub_scores)
                    results.append((job, score, sub_scores, explanation))
                st.session_state.scored_results = results
                st.session_state.current_step = 3
                st.session_state._go_to_tab = 3
                st.rerun()
        elif jobs:
            results = [(j, 0.0, {}, {"reasons": ["Upload CV for personalised scoring"], "gaps": []}) for j in jobs]
            st.session_state.scored_results = results
            st.session_state.current_step = 3
            st.session_state._go_to_tab = 3
            st.rerun()

# ===== TAB 4: Results =====
with tab_results:
    results = st.session_state.scored_results

    if not results:
        st.info("No results yet. Use the **Search Jobs** tab to fetch listings.")
    else:
        f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
        with f1:
            all_sources = sorted({r[0].source.split(":")[0] for r in results})
            source_filter = st.multiselect("Source", all_sources, default=all_sources)
        with f2:
            remote_filter = st.multiselect("Work type", ["Remote", "Hybrid", "On-site"])
        with f3:
            sort_option = st.selectbox("Sort", ["Best match", "Lowest match", "Newest"])
        with f4:
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(["Score", "Title", "Company", "Location", "Remote", "Source", "URL", "Reasons"])
            for job, score, _, explanation in results:
                writer.writerow([
                    f"{score:.2f}", job.title, job.company, job.location,
                    job.remote_type, job.source, job.url,
                    "; ".join(explanation.get("reasons", [])),
                ])
            st.download_button("CSV", csv_buffer.getvalue(), "jobs.csv", "text/csv", use_container_width=True)

        filtered_results = results
        if source_filter:
            filtered_results = [r for r in filtered_results if r[0].source.split(":")[0] in source_filter]
        if remote_filter:
            rt_map = {"Remote": "remote", "Hybrid": "hybrid", "On-site": "onsite"}
            wanted = {rt_map[r] for r in remote_filter if r in rt_map}
            filtered_results = [r for r in filtered_results if r[0].remote_type in wanted]
        if sort_option == "Lowest match":
            filtered_results.sort(key=lambda x: x[1])
        elif sort_option == "Newest":
            from datetime import datetime, timezone
            filtered_results.sort(
                key=lambda x: x[0].published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True,
            )

        st.caption(f"Showing {len(filtered_results)} of {len(results)}")

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
                            {job.location or "Not specified"}
                            {"&nbsp; | &nbsp;" + job.remote_type.title() if job.remote_type else ""}
                            {"&nbsp; | &nbsp;" + job.display_salary if job.display_salary else ""}
                            &nbsp; | &nbsp; {job.source}
                        </div>
                    </div>
                    <div class="score-badge">{score_pct}%</div>
                </div>
            """, unsafe_allow_html=True)

            if job.tags:
                st.markdown(" ".join(f'<span class="skill-tag">{t}</span>' for t in job.tags[:8]), unsafe_allow_html=True)
            for r in reasons[:3]:
                st.markdown(f'<div class="match-reason">✅ {r}</div>', unsafe_allow_html=True)
            for g in gaps[:2]:
                st.markdown(f'<div class="match-gap">⚠️ {g}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            c1, c2 = st.columns([1, 5])
            with c1:
                if job.url:
                    st.link_button("Apply", job.url, use_container_width=True)
            with c2:
                with st.expander("Description"):
                    st.text(job.description[:1500] if job.description else "No description.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("""
<div class="disclaimer">
<b>Disclaimer:</b> Job Seeker Cheater suggests jobs -- it doesn't apply on your behalf.
You're responsible for verifying listings and submitting applications.
Data from public APIs. Your CV stays on your machine. No cookies, no analytics.
<b>Not legal or employment advice.</b>
</div>
""", unsafe_allow_html=True)
