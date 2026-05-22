# Upstream Baseline

Forked from: https://github.com/brightbeanxyz/brightbean-studio
Baseline SHA: 39e2368f43666d621413383da116f64558e40380
Fork date: 2026-05-22

## Pull strategy

Check monthly: `git fetch upstream && git log upstream/main --oneline -20`

Merge if:
- Security fixes
- New platform support
- Dependency updates

Do NOT merge if:
- Migrations conflict with local changes
- Upstream adds Temporal or Redis dependency

## Changes from upstream

- `railway.toml`: added `healthcheckPath` and `healthcheckTimeout`
- `cloudrun/web.yaml`: Cloud Run web service manifest (scales to zero)
- `cloudrun/worker.yaml`: Cloud Run worker manifest (min-instances: 1)
- `.github/workflows/deploy-railway.yml`: Railway CI/CD + Port deployment reporting
- `.github/workflows/deploy-cloudrun.yml`: Cloud Run deploy (manual trigger only)
