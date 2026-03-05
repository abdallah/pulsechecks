# Pub/Sub topics for alert notifications
# Note: User-created alert topics are created dynamically by the application
# This file sets up the infrastructure permissions

# Service account for Pub/Sub
resource "google_service_account" "pubsub_sa" {
  account_id   = "pulsechecks-pubsub"
  display_name = "Pulsechecks Pub/Sub Service Account"
  description  = "Service account for Pulsechecks Pub/Sub operations"

  depends_on = [google_project_service.required_apis]
}

# Grant Pub/Sub permissions to Cloud Run service account
resource "google_project_iam_member" "cloudrun_pubsub_admin" {
  project = var.gcp_project_id
  role    = "roles/pubsub.admin"
  member  = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

# Example: Infrastructure monitoring topic (optional)
resource "google_pubsub_topic" "infrastructure_alerts" {
  name    = "pulsechecks-infrastructure-alerts-${var.environment}"
  project = var.gcp_project_id

  # Message retention
  message_retention_duration = "604800s" # 7 days

  depends_on = [google_project_service.required_apis]
}

# Email subscription example (optional - configure with your email)
# resource "google_pubsub_subscription" "infrastructure_alerts_email" {
#   name    = "pulsechecks-infrastructure-alerts-email"
#   topic   = google_pubsub_topic.infrastructure_alerts.name
#   project = var.gcp_project_id
#
#   # Push to email (requires Cloud Functions or external endpoint)
#   push_config {
#     push_endpoint = "https://your-email-endpoint.example.com"
#   }
# }
