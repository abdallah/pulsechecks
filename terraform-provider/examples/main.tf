terraform {
  required_providers {
    pulsechecks = {
      source = "abdallah/pulsechecks"
    }
  }
}

provider "pulsechecks" {
  api_url = "https://api.pulsechecks.example.com"
  token   = "your-api-token"
}

resource "pulsechecks_team" "example" {
  name = "My Team"
}

# Heartbeat — always-running process pings every 5 minutes
resource "pulsechecks_check" "worker" {
  team_id        = pulsechecks_team.example.team_id
  name           = "Background Worker"
  check_type     = "heartbeat"
  period_seconds = 300
  grace_seconds  = 60
}

# Cron — scheduled job; next due time derived from cron expression
resource "pulsechecks_check" "nightly_backup" {
  team_id       = pulsechecks_team.example.team_id
  name          = "Nightly Database Backup"
  check_type    = "cron"
  schedule      = "0 2 * * *"
  grace_seconds = 1800
}

# HTTP — PulseChecks actively polls the URL every 60 seconds
resource "pulsechecks_check" "api_health" {
  team_id        = pulsechecks_team.example.team_id
  name           = "API Health"
  check_type     = "http"
  period_seconds = 60
  grace_seconds  = 30
}

output "worker_ping_url" {
  value     = "https://api.pulsechecks.example.com/ping/${pulsechecks_check.worker.token}"
  sensitive = true
}

output "backup_ping_url" {
  value     = "https://api.pulsechecks.example.com/ping/${pulsechecks_check.nightly_backup.token}"
  sensitive = true
}
