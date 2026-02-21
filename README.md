# Job Seeker Cheater 🏖️

> **Your laptop works. You relax.**

A local-first, privacy-respecting job matching tool. Upload your CV, set your
preferences, and let the machine fetch, rank, and explain job matches from
free public sources -- all running on your laptop with zero paid APIs.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![No paid APIs](https://img.shields.io/badge/paid%20APIs-none-brightgreen)

---

## Features

- **CV Parsing** -- Upload PDF, DOCX, or TXT. Skills, experience, and role hints are extracted automatically.
- **Preferences** -- Target titles, required/nice-to-have skills, location, remote/hybrid/on-site, seniority, salary floor.
- **Free Job Sources** -- Remotive, Arbeitnow, and Greenhouse public board APIs (configurable company list).
- **Smart Ranking** -- TF-IDF text similarity + skill overlap + preference fit + recency bonus, with per-job explanations.
- **Explainability** -- Every match shows "Matched because..." and "Potential gaps..." so you know why.
- **One-click Apply** -- Opens the original listing URL.
- **CSV Export** -- Download your ranked matches.
- **Privacy by Design** -- CV never leaves your machine. No cookies, no trackers, no telemetry.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/<your-username>/job-seeker-cheater.git
cd job-seeker-cheater

# Install dependencies
pip install -r requirements.txt

# Launch the app
python -m streamlit run app.py
```

The app opens at `http://localhost:8501`.

## How It Works

1. **Upload your CV** (PDF/DOCX/TXT) -- parsed locally, never sent anywhere.
2. **Set preferences** -- job titles, skills, location, remote type, seniority, salary.
3. **Fetch jobs** -- pulls from Remotive, Arbeitnow, and Greenhouse public APIs.
4. **Review ranked matches** -- sorted by weighted score with explanations.
5. **Apply** -- click through to the original listing.

## Privacy by Design 🔒

This tool is built with privacy as a first-class requirement:

- **Local processing only** -- Your CV text, extracted skills, and preferences are processed in-memory on your machine.
- **No server-side storage** -- The Streamlit app runs on `localhost`. There is no cloud backend.
- **No personal data in API requests** -- A `SafeHttpClient` actively blocks any request that contains CV content.
- **No cookies, analytics, or trackers** -- `gatherUsageStats` is disabled in Streamlit config.
- **Ephemeral by default** -- All data clears when you close the app.
- **Optional local persistence** -- Opt-in "Remember on this device" saves a minimal profile (no raw CV text) to a local JSON file.
- **One-click delete** -- Wipe all local data instantly.
- **Export/Import** -- Portable profile for your own backups.

See [Privacy Policy](docs/privacy-policy.md) | [GDPR Notice](docs/gdpr-notice.md) | [Data Flow](docs/data-flow.md)

> **Note:** Privacy documentation is provided as practical templates. Review with qualified legal counsel before any production or public deployment.

## Project Structure

```
app.py                  Streamlit entry point
src/
  cv/parser.py          PDF/DOCX/TXT extraction
  cv/entities.py        Skill, experience, role detection
  sources/base.py       Abstract connector interface
  sources/remotive.py   Remotive API connector
  sources/arbeitnow.py  Arbeitnow API connector
  sources/greenhouse.py Greenhouse board API connector
  sources/normalizer.py Multi-source fetch + dedup
  matching/scorer.py    TF-IDF + weighted scoring
  matching/filters.py   Hard filters (location, remote, salary, seniority)
  matching/dedup.py     Cross-source deduplication
  matching/explainer.py Match reason + gap generation
  models/               Job, Profile, Preferences dataclasses
  storage/cache.py      SQLite job listing cache
  storage/privacy.py    Local persistence + wipe manager
  utils/http_client.py  SafeHttpClient (privacy guardrails)
  utils/text.py         Text cleaning utilities
data/
  skills_seed.json      ~200 tech + business skills dictionary
  greenhouse_companies.yaml  Configurable Greenhouse slugs
docs/                   Privacy, GDPR, security, legal docs
tests/                  42 tests (pytest)
```

## Running Tests

```bash
pytest -q
```

## Configuration

- **Greenhouse companies**: Edit `data/greenhouse_companies.yaml` to add/remove company slugs.
- **Skills dictionary**: Extend `data/skills_seed.json` with domain-specific skills.
- **Streamlit theme**: Edit `.streamlit/config.toml` for colours and layout.

## Known Limitations

- Job APIs may rate-limit or change without notice.
- Salary data is sparse across sources; many jobs have no salary information.
- Entity extraction uses keyword matching and heuristics, not NLP models.
- Greenhouse connector fetches serially per company slug (can be slow with many slugs).
- No login/multi-user support (single-user local tool by design).

## Next 5 Improvements

1. **Add more sources** -- HN Who's Hiring, Indeed RSS, LinkedIn public posts.
2. **Async fetching** -- Parallel API calls with `httpx.AsyncClient` for speed.
3. **NLP entity extraction** -- Use spaCy or a local LLM for better skill/role detection.
4. **Job alerts** -- Schedule periodic fetches and notify on new high-score matches.
5. **Docker packaging** -- One-command `docker run` for zero-install setup.

## Legal

This tool suggests jobs only. It does not apply for jobs on your behalf. You are
solely responsible for verifying listings and submitting applications. All job data
is sourced from public APIs in compliance with their terms of service.

See [Legal Disclaimer](docs/legal-disclaimer.md) for full details.

---

*Built with Python, Streamlit, and a healthy disrespect for tedious job searching.*
