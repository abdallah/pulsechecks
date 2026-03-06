terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  # Configure backend for state storage
  # For GitLab: Use HTTP backend
  # For local: Comment out or use local backend
  #  backend "http" {
  # Set via environment variables:
  # TF_HTTP_ADDRESS, TF_HTTP_LOCK_ADDRESS, TF_HTTP_UNLOCK_ADDRESS
  #  }
}

provider "google" {
  project               = var.gcp_project_id
  region                = var.gcp_region
  billing_project       = var.gcp_project_id
  user_project_override = true
}

provider "google-beta" {
  project               = var.gcp_project_id
  region                = var.gcp_region
  billing_project       = var.gcp_project_id
  user_project_override = true
}

# Enable required Google Cloud APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",                  # Cloud Run
    "firestore.googleapis.com",            # Firestore
    "firebase.googleapis.com",             # Firebase
    "identitytoolkit.googleapis.com",      # Firebase Auth / Identity Platform
    "cloudscheduler.googleapis.com",       # Cloud Scheduler
    "cloudbuild.googleapis.com",           # Cloud Build (for container builds)
    "artifactregistry.googleapis.com",     # Artifact Registry
    "pubsub.googleapis.com",               # Pub/Sub
    "logging.googleapis.com",              # Cloud Logging
    "monitoring.googleapis.com",           # Cloud Monitoring
    "cloudresourcemanager.googleapis.com", # Resource Manager
    "serviceusage.googleapis.com",         # Service Usage API
    "firebasehosting.googleapis.com",      # Firebase Hosting
  ])

  service = each.key

  # Don't disable services on destroy
  disable_on_destroy = false
}

# Get project details
data "google_project" "project" {
  project_id = var.gcp_project_id
}

# Service account for Cloud Run
resource "google_service_account" "cloudrun_sa" {
  account_id   = "pulsechecks-cloudrun"
  display_name = "Pulsechecks Cloud Run Service Account"
  description  = "Service account for Pulsechecks Cloud Run services"

  depends_on = [google_project_service.required_apis]
}

# Grant Firestore access to Cloud Run service account
resource "google_project_iam_member" "cloudrun_firestore" {
  project = var.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

# Grant Pub/Sub access to Cloud Run service account
resource "google_project_iam_member" "cloudrun_pubsub" {
  project = var.gcp_project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

# Grant logging access
resource "google_project_iam_member" "cloudrun_logging" {
  project = var.gcp_project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

# Grant monitoring access
resource "google_project_iam_member" "cloudrun_monitoring" {
  project = var.gcp_project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}
