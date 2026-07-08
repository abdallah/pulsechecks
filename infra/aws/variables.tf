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
