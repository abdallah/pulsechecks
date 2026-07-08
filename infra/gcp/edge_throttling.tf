# GCP edge throttling resources
#
# Production API traffic should flow through a global external HTTPS load
# balancer with Cloud Armor rate limiting in front of Cloud Run.

locals {
  api_edge_throttling_enabled = var.edge_throttling_enabled
}

resource "google_compute_global_address" "api_edge" {
  count = local.api_edge_throttling_enabled ? 1 : 0

  name = "pulsechecks-api-edge-${var.environment}"
}

resource "google_compute_managed_ssl_certificate" "api_edge" {
  count = local.api_edge_throttling_enabled ? 1 : 0

  name = "pulsechecks-api-edge-cert-${var.environment}"

  managed {
    domains = [var.api_domain_name]
  }
}

resource "google_compute_region_network_endpoint_group" "api_edge" {
  count = local.api_edge_throttling_enabled ? 1 : 0

  name                  = "pulsechecks-api-edge-neg-${var.environment}"
  region                = var.gcp_region
  project               = var.gcp_project_id
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_service.pulsechecks_api.name
  }
}

resource "google_compute_security_policy" "api_edge" {
  count = local.api_edge_throttling_enabled ? 1 : 0

  name = "pulsechecks-api-edge-policy-${var.environment}"

  # All rate rules key on client IP (enforce_on_key = "IP").
  # Without it Cloud Armor defaults to "ALL" — one shared bucket for every
  # client — so a single flooder would exhaust the budget and legitimate
  # ping traffic would be the collateral damage. Per-IP keying is what
  # makes the limiter protect availability instead of threatening it.

  # Stricter per-IP limit for the management API (everything except /ping/
  # and /health). Dashboards don't need hundreds of requests per minute.
  rule {
    priority = 900
    action   = "throttle"

    match {
      expr {
        expression = "!request.path.startsWith('/ping/') && request.path != '/health'"
      }
    }

    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"

      rate_limit_threshold {
        count        = var.edge_throttle_api_requests_per_minute
        interval_sec = 60
      }
    }
  }

  # Per-IP short-window throttle (protects against bursts)
  rule {
    priority = 1000
    action   = "throttle"

    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }

    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"

      rate_limit_threshold {
        count        = var.edge_throttle_requests_per_second
        interval_sec = 1
      }
    }
  }

  # Per-IP sustained-rate ban: clients far above the budget for a full
  # minute get banned outright for a cool-down instead of retrying 429s.
  rule {
    priority = 1010
    action   = "rate_based_ban"

    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }

    rate_limit_options {
      conform_action   = "allow"
      exceed_action    = "deny(429)"
      enforce_on_key   = "IP"
      ban_duration_sec = var.edge_throttle_ban_duration_seconds

      rate_limit_threshold {
        count        = var.edge_throttle_burst
        interval_sec = 60
      }
    }
  }
}

resource "google_compute_backend_service" "api_edge" {
  count = local.api_edge_throttling_enabled ? 1 : 0

  name                  = "pulsechecks-api-edge-bs-${var.environment}"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30
  security_policy       = google_compute_security_policy.api_edge[0].self_link

  backend {
    group = google_compute_region_network_endpoint_group.api_edge[0].id
  }
}

resource "google_compute_url_map" "api_edge" {
  count = local.api_edge_throttling_enabled ? 1 : 0

  name            = "pulsechecks-api-edge-map-${var.environment}"
  default_service = google_compute_backend_service.api_edge[0].id
}

resource "google_compute_target_https_proxy" "api_edge" {
  count = local.api_edge_throttling_enabled ? 1 : 0

  name             = "pulsechecks-api-edge-proxy-${var.environment}"
  url_map          = google_compute_url_map.api_edge[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.api_edge[0].self_link]
}

resource "google_compute_global_forwarding_rule" "api_edge" {
  count = local.api_edge_throttling_enabled ? 1 : 0

  name                  = "pulsechecks-api-edge-fr-${var.environment}"
  ip_address            = google_compute_global_address.api_edge[0].address
  ip_protocol           = "TCP"
  port_range            = "443"
  target                = google_compute_target_https_proxy.api_edge[0].id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_dns_record_set" "api_domain_a" {
  count = local.api_edge_throttling_enabled && local.create_dns_records ? 1 : 0

  managed_zone = var.dns_managed_zone_name
  name         = "${var.api_domain_name}."
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.api_edge[0].address]
}
