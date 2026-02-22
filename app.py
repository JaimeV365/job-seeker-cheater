import csv
import io
import json
import os
from pathlib import Path

import streamlit as st

from src.cv.parser import parse_cv
from src.cv.entities import build_profile, _load_skills_dict
from src.matching.dedup import deduplicate
from src.matching.explainer import explain_match
from src.matching.filters import apply_hard_filters
from src.matching.scorer import score_jobs
from src.models.preferences import Preferences
from src.models.profile import Profile
from src.sources.normalizer import fetch_all_jobs, get_all_connectors
from src.sources.remotive import RemotiveConnector
from src.sources.arbeitnow import ArbeitnowConnector
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
    font-family: 'Fredoka One', cursive !important;
    font-size: 5rem !important; color: var(--deep-blue) !important;
    margin-bottom: 0 !important; line-height: 1.05 !important;
    letter-spacing: -2px !important;
}
@media (min-width: 768px) {
    .hero-title { font-size: 7rem !important; }
}
.hero-cheater { color: var(--bordeaux) !important; }
.hero-tagline {
    font-family: 'Nunito', sans-serif !important;
    font-size: 1.5rem !important; color: var(--slate) !important;
    margin-top: 0.3rem; margin-bottom: 1rem;
}

/* Bigger tabs */
button[data-baseweb="tab"] {
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    padding: 0.8rem 1.5rem !important;
    font-family: 'Nunito', sans-serif !important;
}
[data-baseweb="tab-list"] {
    gap: 0 !important;
}
[data-baseweb="tab-list"] button {
    flex: 1 !important;
    justify-content: center !important;
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

            with st.status(f"Parsing {uploaded_file.name}...", expanded=True) as parse_status:
                st.write("Extracting text from your CV...")
                try:
                    raw_text = parse_cv(uploaded_file.name, uploaded_file.read())
                    st.write("Detecting skills, experience, and role hints...")
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
                    parse_status.update(
                        label=f"Parsed {uploaded_file.name} — {len(profile_part.skills)} skills found",
                        state="complete",
                    )
                except Exception as e:
                    parse_status.update(label=f"Failed: {e}", state="error")

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

        # Build a broad options list: detected skills + seed list
        seed = _load_skills_dict()
        all_known = set()
        for cat_skills in seed.values():
            all_known.update(s.lower() for s in cat_skills)
        all_known.update(s.lower() for s in profile.skills)
        skill_options = sorted(all_known)

        current_skills = list(profile.skills)
        current_lower = [s.lower() for s in current_skills]
        default_skills = [s for s in skill_options if s in current_lower]

        edited_skills = st.multiselect(
            "Your skills (remove irrelevant ones, search to add from 200+ known skills)",
            options=skill_options,
            default=default_skills,
            help="Click X to remove. Start typing to search and add skills from the list.",
            key="skill_editor",
        )

        # Custom skill input for skills not in the seed list
        new_skill = st.text_input(
            "Add a custom skill not in the list above",
            placeholder="e.g. qualtrics, medallia, customer journey mapping",
            key="custom_skill_input",
        )
        if new_skill:
            for s in [x.strip().lower() for x in new_skill.split(",") if x.strip()]:
                if s and s not in edited_skills:
                    edited_skills.append(s)

        if set(edited_skills) != set(current_lower):
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

    col_a, col_b = st.columns(2)
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
        CONTRACT_OPTIONS = ["Full-time", "Part-time", "Contract", "Temporary"]
        ct_map_rev = {"full_time": "Full-time", "part_time": "Part-time",
                      "contract": "Contract", "temporary": "Temporary"}
        ct_defaults = [ct_map_rev.get(c, c) for c in prefs.contract_types if c]
        contract_types = st.multiselect(
            "Contract type",
            CONTRACT_OPTIONS,
            default=[c for c in ct_defaults if c in CONTRACT_OPTIONS],
            placeholder="Any (leave empty)",
            help="Leave empty = all types.",
        )

    col_c, col_d, col_e = st.columns(3)
    with col_c:
        SENIORITY_OPTIONS = ["Junior", "Mid", "Senior", "Lead", "Executive"]
        sen_defaults = [s.title() for s in prefs.seniority_levels if s]
        seniority_levels = st.multiselect(
            "Seniority level",
            SENIORITY_OPTIONS,
            default=[s for s in sen_defaults if s in SENIORITY_OPTIONS],
            placeholder="Any (leave empty)",
            help="Leave empty = all levels. Select specific ones to filter.",
        )
    with col_d:
        min_salary = st.number_input(
            "Min salary (annual)", min_value=0,
            value=int(prefs.min_salary) if prefs.min_salary else 0, step=5000,
        )
    with col_e:
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
        ct_map = {"Full-time": "full_time", "Part-time": "part_time",
                  "Contract": "contract", "Temporary": "temporary"}
        new_prefs = Preferences(
            target_titles=[t.strip() for t in target_titles.split(",") if t.strip()],
            required_skills=[s.strip().lower() for s in required_skills.split(",") if s.strip()],
            nice_to_have_skills=[s.strip().lower() for s in nice_skills.split(",") if s.strip()],
            locations=[loc.strip() for loc in locations.split(",") if loc.strip()],
            country=COUNTRY_MAP.get(country_name, ""),
            remote_types=[remote_map[r] for r in remote_types],
            contract_types=[ct_map[c] for c in contract_types],
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

    ALL_SOURCES = ["Remotive", "Arbeitnow", "Greenhouse", "Lever", "Reed", "Adzuna"]
    selected_sources = st.multiselect(
        "Job sources to search",
        ALL_SOURCES,
        default=ALL_SOURCES,
        help=(
            "**Remotive** -- remote-first worldwide | "
            "**Arbeitnow** -- European & remote | "
            "**Greenhouse** -- tech company boards | "
            "**Lever** -- tech company boards | "
            "**Reed** -- UK's #1 (free API key) | "
            "**Adzuna** -- UK/US/EU/AU (free API key)"
        ),
    )

    # Inline API key setup for Reed/Adzuna
    reed_available = ReedConnector.is_available()
    adzuna_available = AdzunaConnector.is_available()

    if ("Reed" in selected_sources and not reed_available) or \
       ("Adzuna" in selected_sources and not adzuna_available):
        with st.expander("API keys needed for Reed / Adzuna (free to get, takes 2 minutes)", expanded=True):
            col_k1, col_k2 = st.columns(2)
            with col_k1:
                if not reed_available:
                    st.caption("[Get a free Reed key](https://www.reed.co.uk/developers/Jobseeker)")
                    reed_key_input = st.text_input("Reed API Key", type="password", key="reed_key_inline")
            with col_k2:
                if not adzuna_available:
                    st.caption("[Get free Adzuna keys](https://developer.adzuna.com/signup)")
                    adzuna_id_input = st.text_input("Adzuna App ID", key="adzuna_id_inline")
                    adzuna_key_input = st.text_input("Adzuna App Key", type="password", key="adzuna_key_inline")
            if st.button("Save keys"):
                new_keys = _load_api_keys()
                if not reed_available and reed_key_input:
                    new_keys["REED_API_KEY"] = reed_key_input
                if not adzuna_available:
                    if adzuna_id_input:
                        new_keys["ADZUNA_APP_ID"] = adzuna_id_input
                    if adzuna_key_input:
                        new_keys["ADZUNA_APP_KEY"] = adzuna_key_input
                _save_api_keys(new_keys)
                _apply_api_keys(new_keys)
                st.success("Keys saved! They'll work from now on.")
                st.rerun()

    with st.expander("Configure company career boards (Greenhouse & Lever)"):
        st.caption(
            "Add company slugs to search their boards. "
            "Find the slug from the URL: `boards.greenhouse.io/vodafone` → `vodafone`"
        )
        col_gh, col_lv = st.columns(2)
        with col_gh:
            gh_slugs_text = st.text_area(
                "Greenhouse slugs (one per line)",
                value="\n".join(GreenhouseConnector().slugs),
                height=100,
            )
        with col_lv:
            lv_slugs_text = st.text_area(
                "Lever slugs (one per line)",
                value="\n".join(LeverConnector().slugs),
                height=100,
            )

    st.caption(
        "**Indeed & LinkedIn** don't offer free public APIs. "
        "Reed and Adzuna are excellent alternatives. "
        "For specific companies, add their Greenhouse or Lever slugs above."
    )

    fetch_btn = st.button("Fetch & Match Jobs", type="primary", use_container_width=True)

    if fetch_btn:
        if st.session_state.profile.is_empty:
            st.warning("Upload your CV first for personalised ranking.")

        prefs_obj = st.session_state.preferences
        kw = " ".join(prefs_obj.target_titles[:3]) if prefs_obj.target_titles else ""
        loc = prefs_obj.locations[0] if prefs_obj.locations else ""
        country = prefs_obj.country or "UK"

        gh_slugs = [s.strip() for s in gh_slugs_text.strip().split("\n") if s.strip()] if gh_slugs_text else []
        lv_slugs = [s.strip() for s in lv_slugs_text.strip().split("\n") if s.strip()] if lv_slugs_text else []

        connectors = []
        skipped = []
        for s in selected_sources:
            if s == "Remotive":
                connectors.append(RemotiveConnector(search=kw))
            elif s == "Arbeitnow":
                connectors.append(ArbeitnowConnector())
            elif s == "Greenhouse":
                connectors.append(GreenhouseConnector(slugs=gh_slugs))
            elif s == "Lever":
                connectors.append(LeverConnector(slugs=lv_slugs))
            elif s == "Reed":
                if ReedConnector.is_available():
                    connectors.append(ReedConnector(keywords=kw, location=loc))
                else:
                    skipped.append("Reed (no API key)")
            elif s == "Adzuna":
                if AdzunaConnector.is_available():
                    connectors.append(AdzunaConnector(keywords=kw, location=loc, country=country))
                    for extra_country in prefs_obj.also_remote_in:
                        if extra_country != country:
                            connectors.append(AdzunaConnector(keywords=kw, country=extra_country))
                else:
                    skipped.append("Adzuna (no API key)")

        if skipped:
            st.warning(f"Skipped: {', '.join(skipped)}. Add free API keys above to enable them.")

        with st.status("Searching for jobs...", expanded=True) as status:
            st.write("Fetching from public job APIs...")
            try:
                jobs = fetch_all_jobs(connectors)
                st.write(f"Found {len(jobs)} raw listings. Deduplicating...")
                jobs = deduplicate(jobs)
                st.session_state.jobs = jobs
                st.write(f"{len(jobs)} unique jobs after dedup.")
            except Exception as e:
                st.error(f"Error fetching jobs: {e}")
                jobs = []

            if jobs and not st.session_state.profile.is_empty:
                st.write("Filtering and ranking matches against your CV...")
                profile_obj = st.session_state.profile
                filtered = apply_hard_filters(jobs, prefs_obj)
                st.write(f"{len(filtered)} jobs passed your filters (from {len(jobs)} total).")
                scored = score_jobs(filtered, profile_obj, prefs_obj)
                results = []
                for job, score, sub_scores in scored:
                    explanation = explain_match(job, profile_obj, prefs_obj, sub_scores)
                    results.append((job, score, sub_scores, explanation))
                st.session_state.scored_results = results
                status.update(label=f"Done! {len(results)} matches found.", state="complete")
            elif jobs:
                results = [(j, 0.0, {}, {"reasons": ["Upload CV for personalised scoring"], "gaps": []}) for j in jobs]
                st.session_state.scored_results = results
                status.update(label=f"Found {len(results)} jobs (upload CV for ranking).", state="complete")
            else:
                status.update(label="No jobs found. Try different sources or broaden preferences.", state="error")

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
            import html as html_mod
            score_pct = int(score * 100)
            reasons = explanation.get("reasons", [])
            gaps = explanation.get("gaps", [])

            safe_title = html_mod.escape(job.title)
            safe_company = html_mod.escape(job.company)
            safe_location = html_mod.escape(job.location or "Not specified")
            safe_tags = " ".join(
                f'<span class="skill-tag">{html_mod.escape(t)}</span>' for t in job.tags[:8]
            ) if job.tags else ""
            reasons_html = "".join(
                f'<div class="match-reason">✅ {html_mod.escape(r)}</div>' for r in reasons[:3]
            )
            gaps_html = "".join(
                f'<div class="match-gap">⚠️ {html_mod.escape(g)}</div>' for g in gaps[:2]
            )

            card_html = f"""<div class="job-card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div style="flex:1;">
      <h3>{safe_title}</h3>
      <span class="company">{safe_company}</span>
      <div class="meta">
        {safe_location}
        {"&nbsp;|&nbsp;" + job.remote_type.title() if job.remote_type else ""}
        {"&nbsp;|&nbsp;" + html_mod.escape(job.display_salary) if job.display_salary else ""}
        &nbsp;|&nbsp; {html_mod.escape(job.source)}
      </div>
    </div>
    <div class="score-badge">{score_pct}%</div>
  </div>
  {safe_tags}
  {reasons_html}
  {gaps_html}
</div>"""
            st.markdown(card_html, unsafe_allow_html=True)

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
