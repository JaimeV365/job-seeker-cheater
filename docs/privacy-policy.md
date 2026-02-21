# Privacy Policy -- Job Seeker Cheater

**Last updated:** February 2026

> **Important:** This document is a practical template. Review with qualified legal
> counsel before relying on it for compliance purposes.

## Summary

Job Seeker Cheater processes your CV and job preferences **locally on your own
device**. We do not operate servers that receive, store, or process your personal
data.

## What data is processed

| Data category         | Purpose                                | Where it lives             |
|-----------------------|----------------------------------------|----------------------------|
| CV text (PDF/DOCX/TXT)| Extract skills, experience, role hints | In-memory on your device   |
| Job preferences        | Filter and rank job listings          | In-memory (or optional local file) |
| Extracted skills       | Match scoring                         | In-memory on your device   |
| Job listings (public)  | Display and rank                      | Local SQLite cache         |

## What data is NOT collected

- We do **not** upload your CV to any server.
- We do **not** send your skills, preferences, or personal information in API requests.
- We do **not** use cookies, analytics, tracking pixels, or third-party scripts.
- We do **not** log your activity.

## Local storage

By default, all data exists only in memory and is cleared when you close the app.

If you enable "Remember on this device", a minimal profile (skills, preferences,
summary -- **not** the raw CV text) is saved as a JSON file on your local disk.
You can delete this at any time with the "Delete all local data" button.

## External requests

The app makes **outbound GET requests** to these public job APIs:

- `remotive.com/api/remote-jobs`
- `arbeitnow.com/api/job-board-api`
- `boards-api.greenhouse.io/v1/boards/{slug}/jobs`

These requests contain **no personal data** -- only standard HTTP headers and
the public API endpoint URL. A privacy-aware HTTP client actively blocks any
request that contains CV text fragments.

## Your rights

Since we do not collect or store your data on any server:

- **Access/Portability:** Use the Export feature to download your locally stored profile.
- **Deletion:** Click "Delete all local data" to erase everything instantly.
- **Objection:** Stop using the tool at any time; no data persists beyond your device.

## Contact

If you have privacy questions about this tool, open an issue on the GitHub repository.

## Changes

We may update this policy as the tool evolves. Changes will be noted in the
repository commit history.
