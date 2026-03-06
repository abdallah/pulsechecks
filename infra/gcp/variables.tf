variable "gcp_project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP Region for resources"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (e.g., prod, staging)"
  type        = string
  default     = "prod"
}

variable "domain_name" {
  description = "Domain name for the application (e.g., pulsechecks.example.com)"
  type        = string
}

variable "api_domain_name" {
  description = "API domain name (e.g., api.pulsechecks.example.com)"
  type        = string
}

variable "allowed_email_domains" {
  description = "Comma-separated list of allowed email domains for access"
  type        = string
  default     = ""
}

variable "google_oauth_client_id" {
  description = "Google OAuth Client ID for Firebase Auth"
  type        = string
}

variable "google_oauth_client_secret" {
  description = "Google OAuth Client Secret for Firebase Auth"
  type        = string
  sensitive   = true
}

variable "container_image" {
  description = "Container image for Cloud Run (e.g., gcr.io/project/pulsechecks-api:latest)"
  type        = string
}

variable "min_instances" {
  description = "Minimum number of Cloud Run instances (0 for scale-to-zero)"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 10
}

variable "cpu_limit" {
  description = "CPU limit for Cloud Run instances"
  type        = string
  default     = "1000m"
}

variable "memory_limit" {
  description = "Memory limit for Cloud Run instances"
  type        = string
  default     = "512Mi"
}

variable "enable_custom_domain_mapping" {
  description = "Enable Cloud Run custom domain mapping for api_domain_name"
  type        = bool
  default     = false
}

variable "enable_dns_records" {
  description = "Create Cloud DNS CNAME records for domain_name and api_domain_name"
  type        = bool
  default     = false
}

variable "dns_managed_zone_name" {
  description = "Existing Cloud DNS managed zone name used when enable_dns_records is true"
  type        = string
  default     = ""
}

variable "dns_cname_target" {
  description = "CNAME target for Firebase/Cloud Run custom domains"
  type        = string
  default     = "ghs.googlehosted.com."
}
