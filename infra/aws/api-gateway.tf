# API Gateway HTTP API
resource "aws_apigatewayv2_api" "main" {
  name          = "${var.project_name}-api-${var.environment}"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
    max_age       = 300
  }

  tags = {
    Name = "${var.project_name}-api"
  }
}

# API Gateway Stage
resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  default_route_settings {
    throttling_rate_limit  = 1000
    throttling_burst_limit = 2000
  }

  tags = {
    Name = "${var.project_name}-api-stage"
  }
}

resource "aws_apigatewayv2_domain_name" "api" {
  domain_name = "api.${var.domain_name}"

  domain_name_configuration {
    certificate_arn = module.acm_certificate.acm_certificate_arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }
}

resource "aws_apigatewayv2_api_mapping" "api" {
  api_id      = aws_apigatewayv2_api.main.id
  domain_name = aws_apigatewayv2_domain_name.api.id
  stage       = aws_apigatewayv2_stage.main.id
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}"
  retention_in_days = 7
}

# Lambda integration for ping handler
resource "aws_apigatewayv2_integration" "ping_handler" {
  api_id           = aws_apigatewayv2_api.main.id
  integration_type = "AWS_PROXY"

  integration_uri        = aws_lambda_function.ping.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

# Lambda integration for API handler
resource "aws_apigatewayv2_integration" "api_handler" {
  api_id           = aws_apigatewayv2_api.main.id
  integration_type = "AWS_PROXY"

  integration_uri        = aws_lambda_function.api.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

# Route definitions using locals for better organization
locals {
  routes = {
    # Public routes
    health = { method = "GET", path = "/health", integration = "api_handler" }
    
    # Ping routes
    ping_get = { method = "GET", path = "/ping/{token}", integration = "ping_handler" }
    ping_post = { method = "POST", path = "/ping/{token}", integration = "ping_handler" }
    ping_fail_get = { method = "GET", path = "/ping/{token}/fail", integration = "ping_handler" }
    ping_fail_post = { method = "POST", path = "/ping/{token}/fail", integration = "ping_handler" }
    ping_start_get = { method = "GET", path = "/ping/{token}/start", integration = "ping_handler" }
    ping_start_post = { method = "POST", path = "/ping/{token}/start", integration = "ping_handler" }
    
    # User routes
    me = { method = "GET", path = "/me", integration = "api_handler" }
    me_subpaths = { method = "GET", path = "/me/{proxy+}", integration = "api_handler" }
    
    # Team routes
    teams_list = { method = "GET", path = "/teams", integration = "api_handler" }
    teams_create = { method = "POST", path = "/teams", integration = "api_handler" }
    teams_get = { method = "GET", path = "/teams/{team_id}", integration = "api_handler" }
    teams_delete = { method = "DELETE", path = "/teams/{team_id}", integration = "api_handler" }
    
    # Check routes
    checks_list = { method = "GET", path = "/teams/{team_id}/checks", integration = "api_handler" }
    checks_create = { method = "POST", path = "/teams/{team_id}/checks", integration = "api_handler" }
    check_get = { method = "GET", path = "/teams/{team_id}/checks/{check_id}", integration = "api_handler" }
    check_update = { method = "PATCH", path = "/teams/{team_id}/checks/{check_id}", integration = "api_handler" }
    check_pause = { method = "POST", path = "/teams/{team_id}/checks/{check_id}/pause", integration = "api_handler" }
    check_resume = { method = "POST", path = "/teams/{team_id}/checks/{check_id}/resume", integration = "api_handler" }
    check_rotate_token = { method = "POST", path = "/teams/{team_id}/checks/{check_id}/rotate-token", integration = "api_handler" }
    check_delete = { method = "DELETE", path = "/teams/{team_id}/checks/{check_id}", integration = "api_handler" }
    check_escalate = { method = "POST", path = "/teams/{team_id}/checks/{check_id}/escalate", integration = "api_handler" }
    check_suppress = { method = "POST", path = "/teams/{team_id}/checks/{check_id}/suppress", integration = "api_handler" }
    check_pings = { method = "GET", path = "/teams/{team_id}/checks/{check_id}/pings", integration = "api_handler" }
    # Bulk operations routes
    checks_bulk_pause = { method = "POST", path = "/teams/{team_id}/checks/bulk/pause", integration = "api_handler" }
    checks_bulk_resume = { method = "POST", path = "/teams/{team_id}/checks/bulk/resume", integration = "api_handler" }
    
    # Member routes
    members_list = { method = "GET", path = "/teams/{team_id}/members", integration = "api_handler" }
    members_add = { method = "POST", path = "/teams/{team_id}/members", integration = "api_handler" }
    members_remove = { method = "DELETE", path = "/teams/{team_id}/members/{user_id}", integration = "api_handler" }
    members_update = { method = "PATCH", path = "/teams/{team_id}/members/{user_id}", integration = "api_handler" }
    
    # Unified channel routes (replaces alerts + mattermost)
    channels_list = { method = "GET", path = "/teams/{team_id}/channels", integration = "api_handler" }
    channels_create = { method = "POST", path = "/teams/{team_id}/channels", integration = "api_handler" }
    channels_get = { method = "GET", path = "/teams/{team_id}/channels/{channel_id}", integration = "api_handler" }
    channels_update = { method = "PATCH", path = "/teams/{team_id}/channels/{channel_id}", integration = "api_handler" }
    channels_delete = { method = "DELETE", path = "/teams/{team_id}/channels/{channel_id}", integration = "api_handler" }
  }
}

# Create all routes using for_each
resource "aws_apigatewayv2_route" "routes" {
  for_each = local.routes
  
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "${each.value.method} ${each.value.path}"
  target    = "integrations/${each.value.integration == "api_handler" ? aws_apigatewayv2_integration.api_handler.id : aws_apigatewayv2_integration.ping_handler.id}"
}

# Lambda permissions for API Gateway
resource "aws_lambda_permission" "ping_handler" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ping.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "api_handler" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}


