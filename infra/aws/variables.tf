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

