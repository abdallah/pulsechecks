# Terraform Provider for Pulsechecks

A Terraform provider for managing Pulsechecks monitoring resources.

## Features

- **Resources:**
  - `pulsechecks_team` - Manage teams
  - `pulsechecks_check` - Manage monitoring checks

- **Data Sources:**
  - `pulsechecks_team` - Read team information
  - `pulsechecks_checks` - List checks for a team

## Usage

```hcl
terraform {
  required_providers {
    pulsechecks = {
      source = "abdallah/pulsechecks"
      version = "~> 1.0"
    }
  }
}

provider "pulsechecks" {
  api_url = "https://api.pulsechecks.example.com"
  token   = var.pulsechecks_token
}

resource "pulsechecks_team" "example" {
  name = "Production Team"
}

resource "pulsechecks_check" "database_backup" {
  team_id        = pulsechecks_team.example.team_id
  name           = "Database Backup"
  period_seconds = 86400  # 24 hours
  grace_seconds  = 3600   # 1 hour
}

data "pulsechecks_team" "existing" {
  team_id = "team-123"
}
```

## Configuration

The provider can be configured via:

- Provider block attributes
- Environment variables:
  - `PULSECHECKS_API_URL`
  - `PULSECHECKS_TOKEN`

## Development

```bash
go mod tidy
go build
```
