# Data Flow -- Job Seeker Cheater

## Overview

All personal data stays on the user's device. Only public job listing API
requests leave the machine.

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER'S LOCAL MACHINE                         │
│                                                                  │
│  ┌──────────┐    ┌───────────┐    ┌──────────────┐              │
│  │ CV File  │───>│ CV Parser │───>│ Profile       │              │
│  │ (upload) │    │ (pypdf/   │    │ (in-memory)   │              │
│  └──────────┘    │ docx/txt) │    │ - skills      │              │
│                  └───────────┘    │ - experience  │              │
│                                   │ - role hints  │              │
│                                   └──────┬───────┘              │
│                                          │                       │
│  ┌──────────────┐                        │                       │
│  │ Preferences  │────────────────────────┤                       │
│  │ (in-memory   │                        │                       │
│  │  or local    │                        ▼                       │
│  │  JSON file)  │              ┌──────────────────┐             │
│  └──────────────┘              │ Matching Engine   │             │
│                                │ - Hard filters    │             │
│  ┌──────────────┐              │ - TF-IDF scoring  │             │
│  │ Job Cache    │──────────────│ - Skill overlap   │             │
│  │ (SQLite,     │              │ - Explainability  │             │
│  │  jobs only)  │              └────────┬─────────┘             │
│  └──────┬───────┘                       │                       │
│         │                               ▼                       │
│         │                     ┌──────────────────┐              │
│         │                     │ Streamlit UI      │              │
│         │                     │ - Results cards   │              │
│         │                     │ - CSV export      │              │
│         │                     │ - Apply links     │              │
│         │                     └──────────────────┘              │
│         │                                                        │
└─────────┼────────────────────────────────────────────────────────┘
          │
          │  GET requests ONLY
          │  (no personal data)
          ▼
┌─────────────────────────────────────────────────┐
│              EXTERNAL PUBLIC APIS                 │
│                                                   │
│  • remotive.com/api/remote-jobs                   │
│  • arbeitnow.com/api/job-board-api                │
│  • boards-api.greenhouse.io/v1/boards/{slug}/jobs │
│                                                   │
│  Response: JSON job listings (public data)        │
└─────────────────────────────────────────────────┘
```

## Data Categories by Location

| Data                      | Location              | Persistence          | Contains PII? |
|---------------------------|-----------------------|----------------------|---------------|
| Raw CV text               | In-memory only        | Cleared on close     | Yes           |
| Extracted skills          | In-memory (+ opt-in local file) | Opt-in       | Minimal       |
| Preferences               | In-memory (+ opt-in local file) | Opt-in       | No            |
| Job listings              | SQLite cache file     | TTL-based (1 hour)   | No            |
| API request content       | Network (outbound)    | Stateless            | No            |
| API response content      | In-memory + cache     | TTL-based            | No            |

## Privacy Guardrails

1. **SafeHttpClient**: Wraps all outbound requests. Checks URL, params, and body
   against registered CV text fragments. Raises `PrivacyViolationError` on match.
2. **No raw CV in persistence**: The local profile file saves only skills,
   summary, and preferences -- never the full CV text.
3. **No logging of PII**: No server logs, no analytics, no telemetry.
4. **Streamlit config**: `gatherUsageStats = false` disables Streamlit telemetry.

## Proxy Considerations

If a future source requires a server-side proxy:

- The proxy MUST be stateless (no request body logging).
- The proxy MUST NOT receive any CV content or personal data.
- The proxy may only fetch and normalise public job listings.
- This must be documented here with the proxy's data handling details.
