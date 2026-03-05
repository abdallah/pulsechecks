# Firebase project (uses existing GCP project)
resource "google_firebase_project" "pulsechecks" {
  provider = google-beta
  project  = var.gcp_project_id

  depends_on = [
    google_project_service.required_apis,
  ]
}

# Firebase Web App
resource "google_firebase_web_app" "pulsechecks_web" {
  provider     = google-beta
  project      = var.gcp_project_id
  display_name = "Pulsechecks Web"

  depends_on = [google_firebase_project.pulsechecks]
}

# Get Firebase Web App config
data "google_firebase_web_app_config" "pulsechecks_web" {
  provider   = google-beta
  project    = var.gcp_project_id
  web_app_id = google_firebase_web_app.pulsechecks_web.app_id
}

# Identity Platform Config (Firebase Auth)
resource "google_identity_platform_config" "auth_config" {
  provider = google-beta
  project  = var.gcp_project_id

  # Sign-in options
  sign_in {
    allow_duplicate_emails = false

    email {
      enabled           = true
      password_required = false
    }
  }

  # Authorized domains
  authorized_domains = [
    var.domain_name,
    "${var.gcp_project_id}.firebaseapp.com",
    "${var.gcp_project_id}.web.app",
  ]

  depends_on = [
    google_firebase_project.pulsechecks,
    google_project_service.required_apis,
  ]
}

# OAuth IdP Config for Google Sign-In
resource "google_identity_platform_default_supported_idp_config" "google_oauth" {
  provider = google-beta
  project  = var.gcp_project_id

  idp_id        = "google.com"
  client_id     = var.google_oauth_client_id
  client_secret = var.google_oauth_client_secret
  enabled       = true

  depends_on = [google_identity_platform_config.auth_config]
}

# Auth domain mapping (optional - for custom domain)
# Uncomment if you want to use a custom auth domain
# resource "google_identity_platform_tenant" "pulsechecks_tenant" {
#   provider     = google-beta
#   project      = var.gcp_project_id
#   display_name = "Pulsechecks"
#
#   depends_on = [google_identity_platform_config.auth_config]
# }
