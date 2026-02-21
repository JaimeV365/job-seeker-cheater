# Security Notes -- Job Seeker Cheater

**Last updated:** February 2026

> **Important:** This is a practical threat assessment, not a formal security audit.
> Review with qualified security professionals before any production deployment.

## Threat Model

### Assets

1. **CV/Resume data** -- Contains PII (name, contact, work history, skills).
2. **User preferences** -- May reveal job-seeking intent.
3. **Job listing cache** -- Public data, low sensitivity.

### Threat Matrix

| Threat                           | Likelihood | Impact | Mitigation                                  |
|----------------------------------|------------|--------|----------------------------------------------|
| CV data exfiltration via network | Low        | High   | SafeHttpClient blocks PII in outbound requests |
| Local file access by malware     | Medium     | High   | OS-level protections; ephemeral mode default  |
| Man-in-the-middle on API calls   | Low        | Low    | All APIs use HTTPS; no PII in requests        |
| Streamlit XSS/injection         | Low        | Medium | XSRF protection enabled; no user-generated URLs |
| Dependency supply chain          | Medium     | High   | Pin versions in requirements.txt; audit regularly |
| Accidental PII logging           | Low        | High   | No server logs; no console PII; privacy tests |

### Attack Surface

- **Network**: Outbound HTTPS GET requests only. No inbound listeners beyond localhost.
- **Local files**: Optional `local_profile.json` and `job_cache.db` in the `data/` directory.
- **Dependencies**: Python packages from PyPI. No custom native extensions.

## Mitigations in Place

### Privacy Guardrails
- `SafeHttpClient` intercepts all outbound requests and rejects any containing
  registered CV text fragments.
- Raw CV text is never written to disk (only extracted metadata if opt-in).
- Streamlit telemetry disabled (`gatherUsageStats = false`).

### Network Security
- All external API calls use HTTPS.
- XSRF protection enabled in Streamlit config.
- CORS disabled (not needed for local app).
- No authentication tokens or API keys transmitted.

### Local Security
- Ephemeral mode by default (nothing on disk).
- Local persistence is explicit opt-in.
- One-click data deletion available.
- No sensitive data in console output or logs.

## Recommendations

1. **Keep dependencies updated** -- Run `pip install --upgrade -r requirements.txt` periodically.
2. **Use a virtual environment** -- Isolate project dependencies.
3. **Encrypt your disk** -- Use BitLocker (Windows) or FileVault (macOS) for at-rest protection.
4. **Don't share profile files** -- `data/local_profile.json` contains career metadata.
5. **Review before hosting** -- If hosting publicly, add authentication, rate limiting, and a WAF.

## Incident Response

For local-only usage, incidents are limited to local device compromise. Standard
device security practices apply (OS updates, antivirus, disk encryption).

For hosted deployments, establish formal incident response procedures including
breach notification per applicable regulations.

---

*This document should be reviewed by qualified security professionals before
reliance in a production context.*
