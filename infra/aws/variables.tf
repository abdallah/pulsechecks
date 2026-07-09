variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "pulsechecks"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "api_gateway_throttling_rate_limit" {
  description = "Default API Gateway request rate limit (requests per second)"
  type        = number
  default     = 1000
}

variable "api_gateway_throttling_burst_limit" {
  description = "Default API Gateway burst limit"
  type        = number
  default     = 2000
}

variable "google_client_id" {
  description = "Google OAuth Client ID"
  type        = string
  sensitive   = true
}

variable "google_client_secret" {
  description = "Google OAuth Client Secret"
  type        = string
  sensitive   = true
}

variable "allowed_email_domains" {
  description = "Comma-separated list of allowed email domains"
  type        = string
}



variable "cognito_domain_prefix" {
  description = "Cognito domain prefix (must be globally unique)"
  type        = string
}


variable "api_key" {
  description = "API key for backend authentication"
  type        = string
  sensitive   = true
  default     = "pulsechecks-dev-key-123"
}

variable "domain_name" {
  description = "Domain name for the frontend (e.g., example.com)"
  type        = string
  default     = "pulsechecks.example.com"
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

variable "ping_throttling_rate_limit" {
  description = "Dedicated steady-state throttle (req/s) for ping ingestion routes, isolated from the management API budget"
  type        = number
  default     = 500
}

variable "ping_throttling_burst_limit" {
  description = "Dedicated burst throttle for ping ingestion routes"
  type        = number
  default     = 1000
}

# ─── Warm standby / cross-cloud failover ────────────────────────────────────

variable "auth_provider" {
  description = "Auth provider override ('firebase' to share identity space with the GCP primary; empty = Cognito)"
  type        = string
  default     = ""
}

variable "firebase_project_id" {
  description = "Firebase project ID (required when auth_provider = 'firebase')"
  type        = string
  default     = ""
}

variable "standby_mode" {
  description = "Run this deployment as a warm standby: mirror definitions from the primary, detect but do not alert for synced checks"
  type        = bool
  default     = false
}

variable "sync_token" {
  description = "Shared secret authenticating the cross-cloud definitions sync (credential-grade: the payload includes check tokens)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "primary_export_url" {
  description = "The primary's export endpoint, e.g. https://api.example.com/internal/export-definitions"
  type        = string
  default     = ""
}

variable "enable_cross_cloud_failover" {
  description = "Create Route53 health-checked failover records for api.<domain> (GCP primary -> this cloud's API Gateway)"
  type        = bool
  default     = false
}

variable "primary_api_fqdn" {
  description = "FQDN Route53 health-checks on the GCP primary (usually api.<domain>... use the LB hostname to avoid checking through the failover record itself)"
  type        = string
  default     = ""
}

variable "gcp_primary_api_ip" {
  description = "Static global IP of the GCP edge load balancer (terraform output from infra/gcp)"
  type        = string
  default     = ""
}
