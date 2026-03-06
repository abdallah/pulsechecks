# Cloud Monitoring Dashboard
resource "google_monitoring_dashboard" "pulsechecks_dashboard" {
  dashboard_json = jsonencode({
    displayName = "Pulsechecks ${var.environment}"
    mosaicLayout = {
      columns = 12
      tiles = [
        # Cloud Run Request Count
        {
          xPos   = 0
          yPos   = 0
          width  = 6
          height = 4
          widget = {
            title = "Cloud Run Request Count"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${google_cloud_run_service.pulsechecks_api.name}\" metric.type=\"run.googleapis.com/request_count\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        # Cloud Run Error Rate
        {
          xPos   = 6
          yPos   = 0
          width  = 6
          height = 4
          widget = {
            title = "Cloud Run Error Rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${google_cloud_run_service.pulsechecks_api.name}\" metric.type=\"run.googleapis.com/request_count\" metric.labels.response_code_class=\"5xx\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        # Cloud Run Latency
        {
          xPos   = 0
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Cloud Run Request Latency"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${google_cloud_run_service.pulsechecks_api.name}\" metric.type=\"run.googleapis.com/request_latencies\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_DELTA"
                    }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        # Firestore Reads
        {
          xPos   = 6
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Firestore Read Operations"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"firestore_instance\" metric.type=\"firestore.googleapis.com/document/read_count\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        }
      ]
    }
  })

  depends_on = [
    google_project_service.required_apis,
    google_cloud_run_service.pulsechecks_api,
  ]
}

# Alert Policy for High Error Rate
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "Pulsechecks High Error Rate - ${var.environment}"
  combiner     = "OR"
  conditions {
    display_name = "Cloud Run Error Rate > 5%"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${google_cloud_run_service.pulsechecks_api.name}\" metric.type=\"run.googleapis.com/request_count\" metric.labels.response_code_class=\"5xx\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [] # Add notification channels if desired

  alert_strategy {
    auto_close = "1800s"
  }

  depends_on = [
    google_project_service.required_apis,
    google_cloud_run_service.pulsechecks_api,
  ]
}

# Alert Policy for High Latency
resource "google_monitoring_alert_policy" "high_latency" {
  display_name = "Pulsechecks High Latency - ${var.environment}"
  combiner     = "OR"
  conditions {
    display_name = "Cloud Run Latency > 2000ms"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${google_cloud_run_service.pulsechecks_api.name}\" metric.type=\"run.googleapis.com/request_latencies\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 2000
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
    }
  }

  notification_channels = [] # Add notification channels if desired

  alert_strategy {
    auto_close = "1800s"
  }

  depends_on = [
    google_project_service.required_apis,
    google_cloud_run_service.pulsechecks_api,
  ]
}

# Log-based metrics (optional - for custom business metrics)
# resource "google_logging_metric" "check_created" {
#   name   = "pulsechecks_check_created"
#   filter = "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${google_cloud_run_service.pulsechecks_api.name}\" jsonPayload.event=\"CHECK_CREATED\""
#   metric_descriptor {
#     metric_kind = "DELTA"
#     value_type  = "INT64"
#   }
# }
