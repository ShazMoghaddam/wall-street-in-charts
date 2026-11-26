# Security policy

## Reporting a problem

If you find a security issue, such as a leaked secret, an unsafe dependency or a way to make the pipeline run untrusted code, please report it privately through [GitHub's private vulnerability reporting](https://github.com/ShazMoghaddam/wall-street-in-charts/security/advisories/new) rather than opening a public issue.

You can expect a reply within a week.

## Secrets

The pipeline uses two secrets: `SEC_CONTACT_EMAIL` and `FRED_API_KEY`. They are read from environment variables or a git-ignored `.env` file. They are never written to the code, the download cache or the outputs. If you fork this repo, keep your own values out of commits.

## Supported versions

Only the latest version on `main` is supported.
