terraform {
  required_providers {
    pulsechecks = {
      source  = "github.com/abdallah/pulsechecks/terraform-provider-pulsechecks"
      version = "~> 1.0"
    }
  }
}

provider "pulsechecks" {
  api_url = var.pulsechecks_api_url
  token   = var.pulsechecks_token
}

resource "pulsechecks_team" "production" {
  name = "Production Team"
}

resource "pulsechecks_check" "database_backup" {
  team_id        = pulsechecks_team.production.team_id
  name           = "Database Backup"
  period_seconds = 86400  # 24 hours
  grace_seconds  = 3600   # 1 hour
}

resource "pulsechecks_check" "api_health" {
  team_id        = pulsechecks_team.production.team_id
  name           = "API Health Check"
  period_seconds = 300    # 5 minutes
  grace_seconds  = 60     # 1 minute
}
