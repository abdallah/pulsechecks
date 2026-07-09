# Point the domain to the cloudfront distribution
locals {
  # Extracts the main domain (e.g., example.com) from the full domain_name
  main_domain = join(".", slice(split(".", var.domain_name), length(split(".", var.domain_name)) - 2, length(split(".", var.domain_name))))
}

provider "aws" {
  alias   = "route53"
  profile = "route53"
  region  = "us-east-1"
}

data "aws_route53_zone" "main" {
  provider     = aws.route53
  name         = local.main_domain
  private_zone = false
}

resource "aws_route53_record" "frontend" {
  provider = aws.route53
  zone_id  = data.aws_route53_zone.main.zone_id
  name     = var.domain_name
  type     = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "api" {
  provider = aws.route53
  zone_id  = data.aws_route53_zone.main.zone_id
  name     = "api.${var.domain_name}"
  type     = "A"
  alias {
    name                   = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].target_domain_name
    zone_id                = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].hosted_zone_id
    evaluate_target_health = false
  }
}

module "acm_certificate" {
  source  = "terraform-aws-modules/acm/aws"
  version = "~> 5.0"

  providers = {
    aws = aws
  }

  domain_name               = var.domain_name
  subject_alternative_names = ["api.${var.domain_name}"]
  validation_method         = "DNS"

  create_route53_records  = false
  validation_record_fqdns = module.acm_validation_records.validation_route53_record_fqdns

  wait_for_validation = true
}

module "acm_validation_records" {
  source  = "terraform-aws-modules/acm/aws"
  version = "~> 5.0"

  providers = {
    aws = aws.route53
  }

  create_certificate          = false
  create_route53_records_only = true

  validation_method = "DNS"
  zone_id           = data.aws_route53_zone.main.zone_id

  distinct_domain_names                     = module.acm_certificate.distinct_domain_names
  acm_certificate_domain_validation_options = module.acm_certificate.acm_certificate_domain_validation_options
}


# ─── Cross-cloud failover for the API domain ────────────────────────────────
# Route53 health-checks the GCP primary; while healthy, api.<domain> resolves
# to the GCP load balancer. When the health check fails, DNS fails over to
# this cloud's API Gateway. Ingestion DNS failover is automatic; alert
# *promotion* (STANDBY_MODE=false) stays a manual runbook step by design.

resource "aws_route53_health_check" "gcp_primary" {
  count = var.enable_cross_cloud_failover ? 1 : 0

  fqdn              = var.primary_api_fqdn
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30

  tags = {
    Name = "${var.project_name}-gcp-primary-health"
  }
}

resource "aws_route53_record" "api_failover_primary" {
  count    = var.enable_cross_cloud_failover ? 1 : 0
  provider = aws.route53

  zone_id        = data.aws_route53_zone.main.zone_id
  name           = "api.${var.domain_name}"
  type           = "A"
  ttl            = 60
  records        = [var.gcp_primary_api_ip]
  set_identifier = "gcp-primary"

  failover_routing_policy {
    type = "PRIMARY"
  }

  health_check_id = aws_route53_health_check.gcp_primary[0].id
}

resource "aws_route53_record" "api_failover_secondary" {
  count    = var.enable_cross_cloud_failover ? 1 : 0
  provider = aws.route53

  zone_id        = data.aws_route53_zone.main.zone_id
  name           = "api.${var.domain_name}"
  type           = "A"
  set_identifier = "aws-standby"

  alias {
    name                   = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].target_domain_name
    zone_id                = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].hosted_zone_id
    evaluate_target_health = false
  }

  failover_routing_policy {
    type = "SECONDARY"
  }
}
