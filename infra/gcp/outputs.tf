output "project_id" {
  description = "GCP Project ID"
  value       = var.gcp_project_id
}

output "region" {
  description = "GCP Region"
  value       = var.gcp_region
}

output "cloudrun_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_service.pulsechecks_api.status[0].url
}

output "cloudrun_service_name" {
  description = "Cloud Run service name"
  value       = google_cloud_run_service.pulsechecks_api.name
}

output "firestore_database" {
  description = "Firestore database name"
  value       = google_firestore_database.pulsechecks.name
}

output "firebase_web_api_key" {
  description = "Firebase Web API Key"
  value       = data.google_firebase_web_app_config.pulsechecks_web.api_key
  sensitive   = true
}

output "firebase_auth_domain" {
  description = "Firebase Auth Domain"
  value       = "${var.gcp_project_id}.firebaseapp.com"
}

output "service_account_email" {
  description = "Service account email for Cloud Run"
  value       = google_service_account.cloudrun_sa.email
}

output "deployment_instructions" {
  description = "Instructions for deploying the application"
  value       = <<-EOT
    Next steps to deploy Pulsechecks on GCP:

    1. Build and push container image:
       cd ../backend
       gcloud builds submit --tag gcr.io/${var.gcp_project_id}/pulsechecks-api

    2. Deploy Cloud Run service:
       gcloud run deploy pulsechecks-api \
         --image gcr.io/${var.gcp_project_id}/pulsechecks-api \
         --region ${var.gcp_region} \
         --platform managed \
         --allow-unauthenticated

    3. Configure frontend:
       - Set VITE_API_URL to: ${google_cloud_run_service.pulsechecks_api.status[0].url}
       - Set VITE_FIREBASE_CONFIG with the Web API key

    4. Deploy frontend to Firebase Hosting:
       cd ../frontend
       firebase deploy --only hosting
  EOT
}
