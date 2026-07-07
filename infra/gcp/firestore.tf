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

# TTL Policy for ping events (expiry timestamp is set per-document by the
# backend from PING_RETENTION_DAYS, default 90 days)
resource "google_firestore_field" "ping_ttl" {
  project    = var.gcp_project_id
  database   = google_firestore_database.pulsechecks.name
  collection = "pings"
  field      = "ttl"

  ttl_config {}

  depends_on = [google_firestore_database.pulsechecks]
}

# TTL Policy for alert delivery history (same retention as pings)
resource "google_firestore_field" "alert_delivery_ttl" {
  project    = var.gcp_project_id
  database   = google_firestore_database.pulsechecks.name
  collection = "alertDeliveries"
  field      = "ttl"

  ttl_config {}

  depends_on = [google_firestore_database.pulsechecks]
}

# Composite indexes for the alert delivery queue and history queries
resource "google_firestore_index" "alert_deliveries_pending" {
  project    = var.gcp_project_id
  database   = google_firestore_database.pulsechecks.name
  collection = "alertDeliveries"

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }
  fields {
    field_path = "nextAttemptAt"
    order      = "ASCENDING"
  }

  depends_on = [google_firestore_database.pulsechecks]
}

resource "google_firestore_index" "alert_deliveries_team_history" {
  project    = var.gcp_project_id
  database   = google_firestore_database.pulsechecks.name
  collection = "alertDeliveries"

  fields {
    field_path = "teamId"
    order      = "ASCENDING"
  }
  fields {
    field_path = "createdAt"
    order      = "DESCENDING"
  }

  depends_on = [google_firestore_database.pulsechecks]
}

resource "google_firestore_index" "alert_deliveries_check_history" {
  project    = var.gcp_project_id
  database   = google_firestore_database.pulsechecks.name
  collection = "alertDeliveries"

  fields {
    field_path = "teamId"
    order      = "ASCENDING"
  }
  fields {
    field_path = "checkId"
    order      = "ASCENDING"
  }
  fields {
    field_path = "createdAt"
    order      = "DESCENDING"
  }

  depends_on = [google_firestore_database.pulsechecks]
}

# Single-field indexes for token/teamId/alertAfterAt are managed by Firestore automatically.
# Add google_firestore_index resources only for true composite index requirements.

# Composite index for the HTTP poller's due-check query
resource "google_firestore_index" "http_checks_due" {
  project    = var.gcp_project_id
  database   = google_firestore_database.pulsechecks.name
  collection = "checks"

  fields {
    field_path = "type"
    order      = "ASCENDING"
  }
  fields {
    field_path = "nextDueAt"
    order      = "ASCENDING"
  }

  depends_on = [google_firestore_database.pulsechecks]
}
