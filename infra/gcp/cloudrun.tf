# Cloud Run service for Pulsechecks API
resource "google_cloud_run_service" "pulsechecks_api" {
  name     = "pulsechecks-api-${var.environment}"
  location = var.gcp_region
  project  = var.gcp_project_id

  template {
    spec {
      service_account_name = google_service_account.cloudrun_sa.email

      # Scale to zero for cost optimization
      containers {
        image = var.container_image

        # Resource limits
        resources {
          limits = {
            cpu    = var.cpu_limit
            memory = var.memory_limit
          }
        }

        # Environment variables
        env {
          name  = "CLOUD_PROVIDER"
          value = "gcp"
        }

        env {
          name  = "GCP_PROJECT"
          value = var.gcp_project_id
        }

        env {
          name  = "GCP_REGION"
          value = var.gcp_region
        }

        env {
          name  = "FIRESTORE_DATABASE"
          value = google_firestore_database.pulsechecks.name
        }

        env {
          name  = "FIREBASE_PROJECT_ID"
          value = var.gcp_project_id
        }

        env {
          name  = "ALLOWED_EMAIL_DOMAINS"
          value = var.allowed_email_domains
        }

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }

        env {
          name  = "FRONTEND_URL"
          value = "https://${var.domain_name}"
        }

        # Port
        ports {
          container_port = 8080
        }
      }

      # Auto-scaling
      container_concurrency = 80
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = var.min_instances
        "autoscaling.knative.dev/maxScale" = var.max_instances
        "run.googleapis.com/client-name"   = "terraform"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [
    google_project_service.required_apis,
    google_firestore_database.pulsechecks,
    google_service_account.cloudrun_sa,
  ]
}

# Allow unauthenticated access (JWT verification in app)
resource "google_cloud_run_service_iam_member" "public_access" {
  service  = google_cloud_run_service.pulsechecks_api.name
  location = google_cloud_run_service.pulsechecks_api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Custom domain mapping for Cloud Run (optional)
resource "google_cloud_run_domain_mapping" "api_domain" {
  count    = var.enable_custom_domain_mapping ? 1 : 0
  provider = google-beta
  name     = var.api_domain_name
  location = var.gcp_region
  project  = var.gcp_project_id

  metadata {
    namespace = var.gcp_project_id
  }

  spec {
    route_name = google_cloud_run_service.pulsechecks_api.name
  }

  depends_on = [google_cloud_run_service.pulsechecks_api]
}

locals {
  create_dns_records = var.enable_dns_records && var.dns_managed_zone_name != ""
}

resource "google_dns_record_set" "api_domain_cname" {
  count        = local.create_dns_records ? 1 : 0
  managed_zone = var.dns_managed_zone_name
  name         = "${var.api_domain_name}."
  type         = "CNAME"
  ttl          = 300
  rrdatas      = [var.dns_cname_target]
}

resource "google_dns_record_set" "frontend_domain_cname" {
  count        = local.create_dns_records ? 1 : 0
  managed_zone = var.dns_managed_zone_name
  name         = "${var.domain_name}."
  type         = "CNAME"
  ttl          = 300
  rrdatas      = [var.dns_cname_target]
}
