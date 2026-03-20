# CLAUDE.md — AI Assistant Guide for CFTC-Filing

This file provides guidance for AI assistants (Claude Code and similar tools) working on this repository.

## Project Overview

**CFTC-Filing** is a project related to Commodity Futures Trading Commission (CFTC) regulatory filings. This repository is currently in its initial state with no source code yet committed.

> **Note:** This CLAUDE.md was created as a foundation. Update it as the codebase evolves to reflect the actual architecture, conventions, and workflows.

---

## Repository State

- **Status:** Freshly initialized — no source files exist yet
- **Branch convention:** Feature branches use the pattern `claude/<description>-<id>`
- **Remote:** `Allanli1011/CFTC-Filing`

---

## Development Workflow

### Branch Strategy

- `main` / `master` — stable, production-ready code
- `claude/<description>-<id>` — AI-assisted feature branches
- `feature/<description>` — human-driven feature branches
- `fix/<description>` — bug fixes

### Git Commit Conventions

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add CFTC form submission endpoint
fix: correct date parsing in swap report
docs: update API documentation for reporting module
refactor: extract filing validator into separate module
test: add unit tests for position aggregation
chore: update dependencies
```

### Standard Workflow

```bash
# 1. Create or switch to your branch
git checkout -b claude/<description>-<id>

# 2. Make changes, then stage and commit
git add <files>
git commit -m "feat: describe your change"

# 3. Push branch
git push -u origin <branch-name>
```

---

## Regulatory Context

CFTC filings involve strict data requirements. When implementing filing-related features, be aware of:

- **Swap Data Reporting (SDR):** Real-time and continuation reporting rules under Parts 43 and 45
- **Large Trader Reporting:** Position reporting thresholds under Part 17
- **Financial Data Standards:** Adherence to FpML, ISO 20022, or DTCC formats as applicable
- **Data Validation:** All submitted data must pass CFTC schema validation before submission
- **Audit Trail:** All filing actions should be logged with timestamps and user identifiers
- **PII / Sensitive Data:** Never log counterparty identifiers or trade details in plaintext logs

---

## Code Quality Standards

### Security

- Never hardcode API keys, credentials, or secrets — use environment variables
- Validate and sanitize all external inputs before processing
- Use parameterized queries for any database operations (prevent SQL injection)
- Do not log sensitive filing data (counterparty info, trade economics) to stdout

### Testing

- Write tests for all filing validation logic — incorrect filings carry regulatory risk
- Cover edge cases: zero-lot trades, cross-border transactions, amended/cancelled reports
- Integration tests should mock CFTC endpoints, not call production systems

### Error Handling

- Filing submission failures must be caught, logged, and surfaced to operators
- Implement retry logic with exponential backoff for transient API failures
- Distinguish between validation errors (fix the data) and system errors (retry)

---

## Environment Variables

Document all required environment variables here as they are added:

| Variable | Description | Required |
|----------|-------------|----------|
| _(none yet)_ | _(project not initialized)_ | — |

---

## Project Structure (to be populated)

Update this section once source files are added:

```
CFTC-Filing/
├── CLAUDE.md          # This file
├── README.md          # Project overview (add when ready)
├── src/               # Source code (add when initialized)
├── tests/             # Test suite (add when initialized)
└── docs/              # Regulatory documentation (add when ready)
```

---

## Key Commands (to be populated)

Add commands here once the project is initialized:

```bash
# Install dependencies
# (add command)

# Run tests
# (add command)

# Lint / format
# (add command)

# Run development server
# (add command)

# Build for production
# (add command)
```

---

## Notes for AI Assistants

1. **Regulatory accuracy matters:** CFTC filing errors can result in compliance violations. Prefer conservative, well-validated implementations over clever shortcuts.
2. **Ask before assuming schema:** CFTC report formats are defined by regulation. Do not invent field names or structures — reference actual CFTC technical specifications.
3. **No real submissions in dev:** Never configure code to submit to live CFTC endpoints in a development or test environment.
4. **Keep this file updated:** After significant structural changes, update the Project Structure and Key Commands sections above.
5. **Branch naming:** Always develop on `claude/`-prefixed branches as specified in the task context.
