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

variable "edge_throttling_enabled" {
  description = "Enable GCP edge throttling in front of Cloud Run"
  type        = bool
  default     = true
}

variable "edge_throttle_requests_per_second" {
  description = "Cloud Armor rate limit threshold for GCP edge throttling"
  type        = number
  default     = 1000
}

variable "edge_throttle_burst" {
  description = "Cloud Armor burst threshold for GCP edge throttling"
  type        = number
  default     = 2000
}

# SMTP settings for email alert channels (optional). Leave empty to
# disable email channels on this deployment.
variable "smtp_host" {
  description = "SMTP server hostname for email alert channels"
  type        = string
  default     = ""
}

variable "smtp_port" {
  description = "SMTP server port"
  type        = string
  default     = "587"
}

variable "smtp_username" {
  description = "SMTP username"
  type        = string
  default     = ""
}

variable "smtp_password" {
  description = "SMTP password"
  type        = string
  default     = ""
  sensitive   = true
}

variable "smtp_from" {
  description = "From address for alert emails, e.g. 'PulseChecks <alerts@example.com>'"
  type        = string
  default     = ""
}

variable "heartbeat_url" {
  description = "External dead-man's-switch URL pinged after each late-detection run (optional)"
  type        = string
  default     = ""
}

variable "edge_throttle_api_requests_per_minute" {
  description = "Per-IP Cloud Armor limit for management API paths (everything except /ping/ and /health)"
  type        = number
  default     = 300
}

variable "edge_throttle_ban_duration_seconds" {
  description = "How long Cloud Armor bans an IP that sustains traffic above the burst threshold"
  type        = number
  default     = 600
}
