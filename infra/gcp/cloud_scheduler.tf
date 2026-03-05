# Cloud Scheduler job for late detection (runs every 2 minutes)
resource "google_cloud_scheduler_job" "late_detector" {
  name             = "pulsechecks-late-detector-${var.environment}"
  description      = "Trigger late detection check every 2 minutes"
  schedule         = "*/2 * * * *"
  time_zone        = "UTC"
  attempt_deadline = "60s"
  region           = var.gcp_region
  project          = var.gcp_project_id

  retry_config {
    retry_count = 3
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_service.pulsechecks_api.status[0].url}/internal/late-detection"

    headers = {
      "Content-Type" = "application/json"
    }

    # Use OIDC token for authentication
    oidc_token {
      service_account_email = google_service_account.cloudrun_sa.email
      audience              = google_cloud_run_service.pulsechecks_api.status[0].url
    }
  }

  depends_on = [
    google_project_service.required_apis,
    google_cloud_run_service.pulsechecks_api,
  ]
}
