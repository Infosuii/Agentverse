# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's private reporting instead: **Security → Report a vulnerability** on this repository. Include steps to reproduce and the impact you expect. We aim to reply within a few days.

## Scope notes

- Jane Avenue runs its engines, verifier and SQLite store locally. In `live` mode it sends only the parsed policy query to the Gemini API, with `store=False`.
- API keys belong in `.env`, which is git-ignored. Never commit keys, and rotate any key that has been exposed.
- This is a research prototype and is not hardened for multi-tenant or internet-facing deployment.
