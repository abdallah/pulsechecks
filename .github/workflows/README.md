# GitHub Actions CI

This directory contains GitHub Actions workflows for automated testing.

> **Note:** Production deployments run in GitLab CI (see the root
> `.gitlab-ci.yml`), not GitHub Actions. The former `aws-deploy.yml` and
> `gcp-deploy.yml` workflows have been removed; their GitLab equivalents are
> the `deploy:*` jobs.

## Workflows

### Test (`test.yml`)

Runs on every pull request and push to main branch.

**Jobs:**
- Backend tests with coverage
- Frontend tests with coverage
- Terraform validation for both AWS and GCP

**No secrets required** - runs automatically on PRs.

## Releases

Terraform provider releases are built with goreleaser — see
`terraform-provider/.goreleaser.yml` and
`terraform-provider/.github/workflows/release.yml`.
