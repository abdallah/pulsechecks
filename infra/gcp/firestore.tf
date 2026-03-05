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
  collection = "checks/*/pings"
  field      = "ttl"

  ttl_config {}

  depends_on = [google_firestore_database.pulsechecks]
}

# Index for check token lookups
resource "google_firestore_index" "check_token_index" {
  project    = var.gcp_project_id
  database   = google_firestore_database.pulsechecks.name
  collection = "checks"

  fields {
    field_path = "token"
    order      = "ASCENDING"
  }

  depends_on = [google_firestore_database.pulsechecks]
}

# Index for team checks
resource "google_firestore_index" "check_team_index" {
  project    = var.gcp_project_id
  database   = google_firestore_database.pulsechecks.name
  collection = "checks"

  fields {
    field_path = "teamId"
    order      = "ASCENDING"
  }

  depends_on = [google_firestore_database.pulsechecks]
}

# Index for late detection (alertAfterAt)
resource "google_firestore_index" "check_alert_after_index" {
  project    = var.gcp_project_id
  database   = google_firestore_database.pulsechecks.name
  collection = "checks"

  fields {
    field_path = "alertAfterAt"
    order      = "ASCENDING"
  }

  depends_on = [google_firestore_database.pulsechecks]
}
