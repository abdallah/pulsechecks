terraform {
  required_providers {
    pulsechecks = {
      source = "abdallah/pulsechecks"
    }
  }
}

provider "pulsechecks" {
  api_url = "https://api.pulsechecks.example.com"
  token   = "test-token"
}

resource "pulsechecks_team" "example" {
  name = "Test Team"
}

resource "pulsechecks_check" "database_backup" {
  team_id        = pulsechecks_team.example.team_id
  name           = "Database Backup Check"
  period_seconds = 86400
  grace_seconds  = 3600
}

output "team_id" {
  value = pulsechecks_team.example.team_id
}

output "check_token" {
  value     = pulsechecks_check.database_backup.token
  sensitive = true
}
