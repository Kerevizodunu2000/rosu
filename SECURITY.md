# Security Policy

## Supported versions

Rosu ships as a single Windows executable through GitHub Releases. Only the
**latest release** receives security fixes — please update before reporting.

| Version         | Supported |
| --------------- | --------- |
| Latest release  | ✅        |
| Older releases  | ❌        |

## Reporting a vulnerability

**Please do not open a public GitHub issue for a security problem.** Responsible,
private disclosure gives us a chance to ship a fix first.

Report privately in one of these ways:

- **GitHub private advisory** — the **“Report a vulnerability”** button under this
  repository’s **Security** tab (GitHub Private Vulnerability Reporting), or
- **Email** — **rosu.app@gmail.com** with `SECURITY` in the subject line.

Please include:

- the affected version (Settings → About) and your OS,
- a clear description of the issue and its impact, and
- steps or a small proof-of-concept to reproduce it.

Do **not** include anyone else’s personal data in your report.

We aim to **acknowledge within 72 hours** and to ship a fix or mitigation as soon
as is practical for a volunteer, non-commercial project. If you’d like, we’ll
credit you once a fix is released.

## Scope

**In scope**

- The Rosu desktop app (`rosu.exe`) and its source in this repository.
- The Google Drive OAuth / backup flow (`rosu/drive/`).
- The report endpoint the app posts to (`rosu-web`, <https://rosu-web.vercel.app>).

**Out of scope**

- Vulnerabilities in third-party dependencies — please report those upstream; we
  will bump the dependency once a fix is available.
- The contents of beatmap archives a user chooses to manage, back up, or share
  (those belong to their respective rights holders; Rosu only organizes files the
  user already has).

Thank you for helping keep Rosu and its users safe.
