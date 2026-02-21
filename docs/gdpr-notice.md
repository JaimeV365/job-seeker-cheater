# GDPR Notice -- Job Seeker Cheater

**Last updated:** February 2026

> **Important:** This document is a practical engineering template, not legal advice.
> Review with a qualified Data Protection Officer or legal counsel before any
> production deployment that may fall under GDPR jurisdiction.

## Data Controller

In its default local-only configuration, **you (the user) are the sole data
controller**. No external party processes your data.

If this tool were ever hosted as a web service, the hosting entity would become
the data controller and must complete a full GDPR compliance assessment.

## Lawful Basis for Processing

| Processing activity       | Lawful basis (local mode)    | Notes                              |
|---------------------------|------------------------------|------------------------------------|
| CV text extraction        | Consent (you upload it)      | Processed in-memory only           |
| Preference storage        | Consent (you enter it)       | Optional opt-in persistence        |
| Job listing fetch         | Legitimate interest          | Public data, no personal data sent |
| Match scoring             | Consent                      | Local computation                  |

For a hosted deployment, lawful basis must be reassessed (likely explicit consent
under Art. 6(1)(a) or legitimate interest under Art. 6(1)(f)).

## Data Categories

- **Special category data:** Not intentionally processed. CV text may incidentally
  contain such data; it remains in local memory only.
- **Personal data:** Name, skills, experience (from CV). Processed locally.
- **Non-personal data:** Public job listings.

## Data Subject Rights (GDPR Articles 15-22)

| Right                  | How it is addressed                                          |
|------------------------|--------------------------------------------------------------|
| Right of access        | Export feature downloads your local profile as JSON          |
| Right to rectification | Edit preferences or re-upload CV at any time                 |
| Right to erasure       | "Delete all local data" button; close app clears memory      |
| Right to restriction   | Disable persistence; use ephemeral mode                      |
| Right to portability   | Export/Import JSON profile                                   |
| Right to object        | Stop using the tool; no server-side processing occurs        |
| Automated decisions    | Ranking is algorithmic; no legally binding decisions are made |

## International Transfers

Outbound API requests may reach servers in various countries:

- Remotive (remotive.com) -- servers may be in the US/EU
- Arbeitnow (arbeitnow.com) -- Germany-based
- Greenhouse (greenhouse.io) -- US-based

**No personal data is included in these requests.** Only public job listings
are retrieved. The privacy-aware HTTP client actively prevents personal data
leakage.

## Data Protection Impact Assessment (DPIA)

In local-only mode, a full DPIA is unlikely to be required since no personal
data is transmitted or stored on external systems. A DPIA should be conducted
before any hosted deployment.

## Data Breach Procedures

In local-only mode, data breaches are limited to the user's own device security.
For hosted deployments, implement breach notification procedures per Art. 33-34.

## Contact

For data protection questions, open an issue on the GitHub repository or contact
the tool maintainer directly.

---

*This notice should be reviewed with qualified legal counsel before reliance
in any GDPR-regulated context.*
