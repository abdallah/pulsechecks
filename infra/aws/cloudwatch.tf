# CloudWatch Alarms and Dashboards for Pulsechecks

# SNS Topic for alarm notifications
resource "aws_sns_topic" "alarms" {
  name = "pulsechecks-alarms-${var.environment}"
}

# API Error Rate Alarm
resource "aws_cloudwatch_metric_alarm" "api_error_rate" {
  alarm_name          = "pulsechecks-api-error-rate-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "APIError"
  namespace           = "Pulsechecks"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors API error rate"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    Environment = var.environment
  }
}

# API Latency Alarm
resource "aws_cloudwatch_metric_alarm" "api_latency" {
  alarm_name          = "pulsechecks-api-latency-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "APILatency"
  namespace           = "Pulsechecks"
  period              = "300"
  statistic           = "Average"
  threshold           = "2000"
  alarm_description   = "This metric monitors API latency"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    Environment = var.environment
  }
}

# Lambda Error Rate Alarm
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "pulsechecks-lambda-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors Lambda function errors"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
}

# DynamoDB Throttling Alarm
resource "aws_cloudwatch_metric_alarm" "dynamodb_throttles" {
  alarm_name          = "pulsechecks-dynamodb-throttles-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "UserErrors"
  namespace           = "AWS/DynamoDB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors DynamoDB throttling"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    TableName = aws_dynamodb_table.pulsechecks.name
  }
}

# No Pings Received Alarm (business logic)
resource "aws_cloudwatch_metric_alarm" "no_pings" {
  alarm_name          = "pulsechecks-no-pings-${var.environment}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "PingReceived"
  namespace           = "Pulsechecks"
  period              = "600"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "No pings received in 30 minutes"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "breaching"

  dimensions = {
    Environment = var.environment
  }
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "Pulsechecks-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["Pulsechecks", "APIRequest"],
            [".", "APIError"],
            [".", "PingReceived"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "API Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["Pulsechecks", "APILatency"],
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.api.function_name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Performance Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["Pulsechecks", "CheckCreated"],
            [".", "CheckDeleted"],
            [".", "AlertSent"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Business Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", aws_dynamodb_table.pulsechecks.name],
            [".", "ConsumedWriteCapacityUnits", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "DynamoDB Metrics"
          period  = 300
        }
      }
    ]
  })
}
