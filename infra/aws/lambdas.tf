# Lambda execution role
resource "aws_iam_role" "lambda_exec" {
  name = "${var.project_name}-lambda-exec-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Attach SNS policy to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_sns" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.sns_publish.arn
}

# Lambda policy
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.pulsechecks.arn,
          "${aws_dynamodb_table.pulsechecks.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sns:CreateTopic",
          "sns:TagResource",
          "sns:DeleteTopic"
        ]
        Resource = "*"
      }
    ]
  })
}

# Placeholder Lambda package (will be updated by CI/CD)
data "archive_file" "lambda_placeholder" {
  type        = "zip"
  output_path = "/tmp/lambda_placeholder.zip"
  source {
    content  = "def handler(event, context): return {'statusCode': 200}"
    filename = "main.py"
  }
}

# Ping Handler Lambda
resource "aws_lambda_function" "ping" {
  function_name = "${var.project_name}-ping-${var.environment}"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "app.main.handler"
  runtime       = "python3.13"
  timeout       = 30
  memory_size   = 256

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.pulsechecks.name
      API_KEY        = var.api_key
    }
  }

  lifecycle {
    ignore_changes = [
      filename,
      source_code_hash
    ]
  }
}

# API Handler Lambda
resource "aws_lambda_function" "api" {
  function_name = "${var.project_name}-api-${var.environment}"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "app.main.handler"
  runtime       = "python3.13"
  timeout       = 30
  memory_size   = 256

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE        = aws_dynamodb_table.pulsechecks.name
      API_KEY               = var.api_key
      API_URL               = "https://${aws_apigatewayv2_api.main.id}.execute-api.${var.aws_region}.amazonaws.com"
      ALLOWED_EMAIL_DOMAINS = var.allowed_email_domains
      COGNITO_CLIENT_ID     = aws_cognito_user_pool_client.main.id
      COGNITO_USER_POOL_ID  = aws_cognito_user_pool.main.id
      SMTP_HOST             = var.smtp_host
      SMTP_PORT             = var.smtp_port
      SMTP_USERNAME         = var.smtp_username
      SMTP_PASSWORD         = var.smtp_password
      SMTP_FROM             = var.smtp_from
      AUTH_PROVIDER         = var.auth_provider
      FIREBASE_PROJECT_ID   = var.firebase_project_id
      STANDBY_MODE          = var.standby_mode ? "true" : "false"
      SYNC_TOKEN            = var.sync_token
      PRIMARY_EXPORT_URL    = var.primary_export_url
    }
  }

  lifecycle {
    ignore_changes = [
      filename,
      source_code_hash
    ]
  }
}

# Late Detector Lambda
resource "aws_lambda_function" "late_detector" {
  function_name = "${var.project_name}-late-detector-${var.environment}"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "app.handlers.late_detector_handler"
  runtime       = "python3.13"
  timeout       = 60
  memory_size   = 512

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.pulsechecks.name
      HEARTBEAT_URL  = var.heartbeat_url
      STANDBY_MODE   = var.standby_mode ? "true" : "false"
      SMTP_HOST      = var.smtp_host
      SMTP_PORT      = var.smtp_port
      SMTP_USERNAME  = var.smtp_username
      SMTP_PASSWORD  = var.smtp_password
      SMTP_FROM      = var.smtp_from
    }
  }

  lifecycle {
    ignore_changes = [
      filename,
      source_code_hash
    ]
  }
}


# Standby definition-sync Lambda: pulls teams/checks/channels from the
# primary cloud every few minutes so this deployment can take over
# ingestion + alerting on promotion. Only created in standby mode.
resource "aws_lambda_function" "standby_sync" {
  count = var.standby_mode ? 1 : 0

  function_name = "${var.project_name}-standby-sync-${var.environment}"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "app.standby_sync.standby_sync_handler"
  runtime       = "python3.13"
  timeout       = 120
  memory_size   = 512

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE     = aws_dynamodb_table.pulsechecks.name
      SYNC_TOKEN         = var.sync_token
      PRIMARY_EXPORT_URL = var.primary_export_url
    }
  }

  lifecycle {
    ignore_changes = [
      filename,
      source_code_hash
    ]
  }
}
