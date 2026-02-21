# Data Retention -- Job Seeker Cheater

**Last updated:** February 2026

## Default Mode: No Retention

By default, Job Seeker Cheater operates in **ephemeral mode**:

| Data                | Retained?    | Duration                    |
|---------------------|--------------|-----------------------------|
| CV raw text         | In-memory    | Until app is closed         |
| Extracted profile   | In-memory    | Until app is closed         |
| Preferences         | In-memory    | Until app is closed         |
| Job listings cache  | SQLite file  | 1 hour TTL, then expired    |
| Search results      | In-memory    | Until app is closed         |

When you close the Streamlit app (or refresh the browser), all in-memory data
is discarded.

## Optional Local Persistence

If you toggle "Remember my profile on this device" (OFF by default):

| Data                | Stored in                | Contains raw CV? |
|---------------------|--------------------------|------------------|
| Skills list         | `data/local_profile.json`| No               |
| Experience years    | `data/local_profile.json`| No               |
| Role hints          | `data/local_profile.json`| No               |
| Summary (first 300 chars) | `data/local_profile.json` | Partial   |
| Preferences         | `data/local_profile.json`| No               |

**The raw CV text is never written to disk.**

## Deletion

- **One-click delete**: The "Delete all local data" button in the sidebar removes
  `data/local_profile.json` and `data/job_cache.db` immediately.
- **Manual delete**: Remove the `data/` directory contents.
- **App close**: In ephemeral mode, closing the app clears everything.

## Job Listing Cache

The SQLite job cache (`data/job_cache.db`) stores **only public job listing data**
(no personal information). Cached entries expire after 1 hour (configurable).
The cache can be cleared manually or via the delete button.

## Recommendations

- Use ephemeral mode for maximum privacy.
- If using persistent mode, periodically use the delete button to clear stale data.
- Do not share `data/local_profile.json` with untrusted parties.

---

*Review retention practices with legal counsel if deploying in a regulated context.*
