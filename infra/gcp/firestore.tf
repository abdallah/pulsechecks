# Firestore Database
resource "google_firestore_database" "pulsechecks" {
  project     = var.gcp_project_id
  name        = "(default)"
  location_id = var.gcp_region
  type        = "FIRESTORE_NATIVE"

  # Concurrency mode
  concurrency_mode = "OPTIMISTIC"

  # Point-in-time recovery
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_ENABLED"

  depends_on = [google_project_service.required_apis]
}

# TTL Policy for ping events (30 days)
resource "google_firestore_field" "ping_ttl" {
  project    = var.gcp_project_id
  database   = google_firestore_database.pulsechecks.name
  collection = "pings"
  field      = "ttl"

  ttl_config {}

  depends_on = [google_firestore_database.pulsechecks]
}

# Single-field indexes for token/teamId/alertAfterAt are managed by Firestore automatically.
# Add google_firestore_index resources only for true composite index requirements.
