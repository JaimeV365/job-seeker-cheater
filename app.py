import csv
import io
import json
import os
from pathlib import Path

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
from src.sources.reed import ReedConnector
from src.sources.adzuna import AdzunaConnector
from src.sources.lever import LeverConnector
from src.sources.greenhouse import GreenhouseConnector
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
    font-size: 4.5rem; color: var(--deep-blue);
    margin-bottom: 0; line-height: 1.05;
    letter-spacing: -2px;
}
@media (min-width: 768px) {
    .hero-title { font-size: 6rem; }
}
.hero-cheater { color: var(--bordeaux); }
.hero-tagline {
    font-family: 'Nunito', sans-serif;
    font-size: 1.4rem; color: var(--slate);
    margin-top: 0.3rem; margin-bottom: 1rem;
}

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
    margin-bottom: 1rem; border-left: 3px solid var(--purple);
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
    "United Kingdom": "UK", "United States": "US", "Germany": "DE",
    "Canada": "CA", "France": "FR", "Spain": "ES", "Australia": "AU",
    "Netherlands": "NL", "Ireland": "IE", "Sweden": "SE", "Italy": "IT",
    "Portugal": "PT", "Switzerland": "CH", "Austria": "AT", "Belgium": "BE",
    "India": "IN", "Singapore": "SG", "Brazil": "BR", "New Zealand": "NZ",
    "Poland": "PL", "South Africa": "ZA",
}
COUNTRY_NAMES = list(COUNTRY_MAP.keys())
CODE_TO_NAME = {v: k for k, v in COUNTRY_MAP.items() if v}
REMOTE_COUNTRY_OPTIONS = [n for n in COUNTRY_NAMES if n != "Any country"]

API_KEYS_PATH = Path(__file__).parent / "data" / "api_keys.json"

# ---------------------------------------------------------------------------
# API key management -- load from local file, set into os.environ
# ---------------------------------------------------------------------------
def _load_api_keys() -> dict:
    if API_KEYS_PATH.exists():
        try:
            return json.loads(API_KEYS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_api_keys(keys: dict):
    API_KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    API_KEYS_PATH.write_text(json.dumps(keys, indent=2), encoding="utf-8")


def _apply_api_keys(keys: dict):
    for env_var, value in keys.items():
        if value:
            os.environ[env_var] = value


_stored_keys = _load_api_keys()
_apply_api_keys(_stored_keys)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "profile": Profile(),
    "preferences": Preferences(),
    "jobs": [],
    "scored_results": [],
    "persist_mode": False,
    "all_cv_skills": [],
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
        st.session_state.all_cv_skills = list(st.session_state.profile.skills)

# ---------------------------------------------------------------------------
# Header
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

# ---------------------------------------------------------------------------
# Sidebar: privacy + API keys
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Privacy")
    mode_label = "Saved locally" if st.session_state.persist_mode else "Ephemeral (lost on close)"
    st.caption(f"**Mode:** {mode_label}")
    new_persist = st.toggle("Remember my profile on this device",
                            value=st.session_state.persist_mode,
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
        st.success("All cleared.")
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

    # API Keys section
    st.markdown("---")
    st.markdown("### API Keys (optional)")
    st.caption("Unlock extra job boards. Keys are saved locally and never shared.")

    with st.expander("Reed.co.uk (free key)", expanded=False):
        st.caption("UK's largest job board. [Get a free key](https://www.reed.co.uk/developers/Jobseeker)")
        reed_key = st.text_input("Reed API Key", value=_stored_keys.get("REED_API_KEY", ""),
                                 type="password", key="reed_key_input")

    with st.expander("Adzuna (free key)", expanded=False):
        st.caption("UK, US, EU, AU and more. [Get a free key](https://developer.adzuna.com/signup)")
        adzuna_id = st.text_input("Adzuna App ID", value=_stored_keys.get("ADZUNA_APP_ID", ""),
                                  key="adzuna_id_input")
        adzuna_key = st.text_input("Adzuna App Key", value=_stored_keys.get("ADZUNA_APP_KEY", ""),
                                   type="password", key="adzuna_key_input")

    if st.button("Save API keys"):
        new_keys = {}
        if reed_key:
            new_keys["REED_API_KEY"] = reed_key
        if adzuna_id:
            new_keys["ADZUNA_APP_ID"] = adzuna_id
        if adzuna_key:
            new_keys["ADZUNA_APP_KEY"] = adzuna_key
        _save_api_keys(new_keys)
        _apply_api_keys(new_keys)
        st.success("Keys saved locally and activated.")
        st.rerun()

# ---------------------------------------------------------------------------
# Tabs (all freely navigable, no auto-advance)
# ---------------------------------------------------------------------------
tab_cv, tab_prefs, tab_search, tab_results = st.tabs(
    ["Upload CV", "Preferences", "Search Jobs", "Results"]
)

# ===== TAB 1: CV Upload =====
with tab_cv:
    st.markdown("Upload one or more CVs. If you have different versions, upload them all "
                "and we'll combine the skills from each one.")

    uploaded_files = st.file_uploader(
        "Upload CV files (PDF, DOCX, TXT, or HTML)",
        type=["pdf", "docx", "txt", "html", "htm"],
        accept_multiple_files=True,
        key="cv_upload",
    )

    if uploaded_files:
        all_skills: list[str] = list(st.session_state.all_cv_skills)
        all_role_hints: list[str] = list(st.session_state.profile.role_hints) if not st.session_state.profile.is_empty else []
        all_raw_text: list[str] = []
        max_experience: float | None = st.session_state.profile.years_experience
        new_files_parsed = False

        for uploaded_file in uploaded_files:
            file_key = f"_parsed_{uploaded_file.name}_{uploaded_file.size}"
            if file_key in st.session_state:
                continue

            with st.spinner(f"Parsing **{uploaded_file.name}** locally..."):
                try:
                    raw_text = parse_cv(uploaded_file.name, uploaded_file.read())
                    profile_part = build_profile(raw_text)

                    for s in profile_part.skills:
                        if s not in all_skills:
                            all_skills.append(s)
                    for rh in profile_part.role_hints:
                        if rh not in all_role_hints:
                            all_role_hints.append(rh)
                    all_raw_text.append(raw_text)
                    if profile_part.years_experience:
                        if max_experience is None or profile_part.years_experience > max_experience:
                            max_experience = profile_part.years_experience

                    fragments = [raw_text[i:i+50] for i in range(0, min(len(raw_text), 500), 50)]
                    register_personal_fragments(fragments)

                    st.session_state[file_key] = True
                    new_files_parsed = True
                except Exception as e:
                    st.error(f"Failed to parse {uploaded_file.name}: {e}")

        if new_files_parsed:
            existing_raw = st.session_state.profile.raw_text if not st.session_state.profile.is_empty else ""
            combined_raw = existing_raw
            if all_raw_text:
                combined_raw = (existing_raw + "\n\n" + "\n\n".join(all_raw_text)).strip()

            merged_profile = Profile(
                raw_text=combined_raw,
                skills=all_skills,
                years_experience=max_experience,
                role_hints=all_role_hints,
                summary="",
            )
            st.session_state.profile = merged_profile
            st.session_state.all_cv_skills = list(all_skills)
            if st.session_state.persist_mode:
                privacy_mgr.save_profile(merged_profile, st.session_state.preferences)

    profile = st.session_state.profile
    if not profile.is_empty:
        st.success(f"CV parsed! **{len(profile.skills)}** skills detected. "
                   "Edit them below, then move to the **Preferences** tab.")

        current_skills = list(profile.skills)
        edited_skills = st.multiselect(
            "Your skills (remove irrelevant ones, type to add new)",
            options=current_skills,
            default=current_skills,
            help="Click the X to remove a skill. Type a new skill name and press Enter to add it.",
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
            st.session_state.all_cv_skills = list(edited_skills)
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
            st.text(profile.raw_text[:3000])
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
            placeholder="e.g. CX Consultant, Data Analyst, Product Manager",
        )
        required_skills = st.text_input(
            "Required skills -- must-have (comma-separated)",
            value=", ".join(prefs.required_skills),
            placeholder="e.g. python, sql, customer experience",
        )
        nice_skills = st.text_input(
            "Nice-to-have skills (comma-separated)",
            value=", ".join(prefs.nice_to_have_skills),
            placeholder="e.g. tableau, qualtrics, six sigma",
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

    st.markdown("---")
    st.markdown("**Also look for remote jobs in other countries?**")
    st.caption(
        "If you can legally work remotely for employers in other countries, add them here. "
        "Only remote positions from these countries will be included."
    )
    also_remote_defaults = [CODE_TO_NAME.get(c, c)
                           for c in prefs.also_remote_in
                           if CODE_TO_NAME.get(c, c) in REMOTE_COUNTRY_OPTIONS]
    also_remote_in = st.multiselect(
        "Additional remote countries",
        REMOTE_COUNTRY_OPTIONS,
        default=also_remote_defaults,
        placeholder="e.g. Germany, France, Netherlands...",
        help="Jobs from these countries will only be included if they are remote.",
    )

    if st.button("Save preferences", type="primary"):
        remote_map = {"Remote": "remote", "Hybrid": "hybrid", "On-site": "onsite"}
        seniority_map = {"Junior": "junior", "Mid": "mid", "Senior": "senior",
                         "Lead": "lead", "Executive": "executive"}
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
        st.success("Preferences saved! Head to the **Search Jobs** tab when ready.")

# ===== TAB 3: Search Jobs =====
with tab_search:
    st.caption("Fetches from public job APIs only. No personal data is sent.")

    reed_available = ReedConnector.is_available()
    adzuna_available = AdzunaConnector.is_available()

    all_source_options = ["Remotive", "Arbeitnow", "Greenhouse", "Lever"]
    if reed_available:
        all_source_options.append("Reed")
    if adzuna_available:
        all_source_options.append("Adzuna")

    default_sources = ["Remotive", "Arbeitnow"]
    if reed_available:
        default_sources.append("Reed")
    if adzuna_available:
        default_sources.append("Adzuna")

    selected_sources = st.multiselect(
        "Job sources to search",
        all_source_options,
        default=default_sources,
        help=(
            "**Remotive** -- remote-first worldwide | "
            "**Arbeitnow** -- European & remote | "
            "**Greenhouse** -- tech company boards | "
            "**Lever** -- tech company boards | "
            + ("**Reed** -- UK's #1 job board | " if reed_available else "")
            + ("**Adzuna** -- UK/US/EU/AU and more" if adzuna_available else "")
        ),
    )

    # Company boards config
    with st.expander("Configure company career boards (Greenhouse & Lever)"):
        st.caption(
            "Many companies use **Greenhouse** or **Lever** to host their career pages. "
            "Add company slugs below to search their boards directly. "
            "Find the slug from the URL: e.g. `boards.greenhouse.io/vodafone` → slug is `vodafone`."
        )
        col_gh, col_lv = st.columns(2)
        with col_gh:
            gh_slugs_text = st.text_area(
                "Greenhouse company slugs (one per line)",
                value="\n".join(GreenhouseConnector().slugs),
                height=120,
                help="e.g. vodafone, gsk, costco",
            )
        with col_lv:
            lv_slugs_text = st.text_area(
                "Lever company slugs (one per line)",
                value="\n".join(LeverConnector().slugs),
                height=120,
                help="e.g. netflix, spotify, cloudflare",
            )

    if not reed_available or not adzuna_available:
        missing = []
        if not reed_available:
            missing.append("**Reed.co.uk** (UK's #1)")
        if not adzuna_available:
            missing.append("**Adzuna** (UK/US/EU/AU)")
        st.markdown(
            f'<div class="api-hint">Want more sources? '
            f'Add free API keys in the sidebar (click ☰ top-left) to unlock: '
            f'{" and ".join(missing)}.</div>',
            unsafe_allow_html=True,
        )

    st.caption(
        "**About Indeed & LinkedIn:** These platforms don't offer free public APIs "
        "and scraping violates their terms of service. Reed and Adzuna are excellent "
        "UK/international alternatives. For specific companies, add their Greenhouse "
        "or Lever slugs above."
    )

    fetch_btn = st.button("Fetch & Match Jobs", type="primary", use_container_width=True)

    if fetch_btn:
        if st.session_state.profile.is_empty:
            st.warning("Upload your CV first for personalised ranking.")

        prefs_obj = st.session_state.preferences

        gh_slugs = [s.strip() for s in gh_slugs_text.strip().split("\n") if s.strip()] if gh_slugs_text else []
        lv_slugs = [s.strip() for s in lv_slugs_text.strip().split("\n") if s.strip()] if lv_slugs_text else []

        source_map = {
            "Remotive": "remotive", "Arbeitnow": "arbeitnow",
            "Greenhouse": "greenhouse", "Lever": "lever",
            "Reed": "reed", "Adzuna": "adzuna",
        }

        connectors = []
        for s in selected_sources:
            s_name = source_map.get(s, "")
            if s_name == "greenhouse":
                connectors.append(GreenhouseConnector(slugs=gh_slugs))
            elif s_name == "lever":
                connectors.append(LeverConnector(slugs=lv_slugs))
            elif s_name == "reed":
                kw = " ".join(prefs_obj.target_titles[:3]) if prefs_obj.target_titles else ""
                loc = prefs_obj.locations[0] if prefs_obj.locations else ""
                connectors.append(ReedConnector(keywords=kw, location=loc))
            elif s_name == "adzuna":
                kw = " ".join(prefs_obj.target_titles[:3]) if prefs_obj.target_titles else ""
                loc = prefs_obj.locations[0] if prefs_obj.locations else ""
                country = prefs_obj.country or "UK"
                connectors.append(AdzunaConnector(keywords=kw, location=loc, country=country))
                for extra_country in prefs_obj.also_remote_in:
                    if extra_country != country:
                        connectors.append(AdzunaConnector(keywords=kw, country=extra_country))
            else:
                for c in get_all_connectors():
                    if c.name == s_name:
                        connectors.append(c)
                        break

        with st.spinner("Fetching jobs from public APIs... This may take 15-30 seconds."):
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
            st.success(f"Done! **{len(results)} matches** found. Check the **Results** tab.")
        elif jobs:
            results = [(j, 0.0, {}, {"reasons": ["Upload CV for personalised scoring"], "gaps": []}) for j in jobs]
            st.session_state.scored_results = results
            st.info(f"Found {len(results)} jobs. Upload a CV for ranked results!")
        else:
            st.warning("No jobs found. Try different sources or broaden your preferences.")

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
            writer.writerow(["Score", "Title", "Company", "Location", "Remote",
                             "Source", "URL", "Reasons"])
            for job, score, _, explanation in results:
                writer.writerow([
                    f"{score:.2f}", job.title, job.company, job.location,
                    job.remote_type, job.source, job.url,
                    "; ".join(explanation.get("reasons", [])),
                ])
            st.download_button("CSV", csv_buffer.getvalue(), "jobs.csv", "text/csv",
                               use_container_width=True)

        filtered_results = results
        if source_filter:
            filtered_results = [r for r in filtered_results
                                if r[0].source.split(":")[0] in source_filter]
        if remote_filter:
            rt_map = {"Remote": "remote", "Hybrid": "hybrid", "On-site": "onsite"}
            wanted = {rt_map[r] for r in remote_filter if r in rt_map}
            filtered_results = [r for r in filtered_results
                                if r[0].remote_type in wanted]
        if sort_option == "Lowest match":
            filtered_results.sort(key=lambda x: x[1])
        elif sort_option == "Newest":
            from datetime import datetime, timezone
            filtered_results.sort(
                key=lambda x: x[0].published_at or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
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
                st.markdown(
                    " ".join(f'<span class="skill-tag">{t}</span>' for t in job.tags[:8]),
                    unsafe_allow_html=True,
                )
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
